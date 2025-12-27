import logging
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from constants import APP_VERSION, get_resource_path
from constants import ICON_PATH as icon_path
from utils.fallback_mode import FallbackMode

from .camera_widget import CameraWidget
from .dialogs import NetworkSelectionDialog, SettingsDialog
from .server_thread import ServerThread
from .theme import Theme

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, fallback_mode=None, restore_session=False, last_state=None):
        super().__init__()

        self.fallback_mode = fallback_mode or FallbackMode()
        self.log_file_path = None  # Will be set by main()
        self.is_restarting = False  # Add this flag

        # Setup settings
        self.settings = QSettings("Vickerdent Corporation", "VideoStreamerServer")

        # Restore from crash or use defaults
        if restore_session and last_state:
            self.start_port = last_state.get("start_port", 5000)
            self.theme_mode = last_state.get("theme_mode", "auto")
            # Restore network if available
            if last_state.get("network_ip"):
                self.network = {"ip": last_state["network_ip"]}
        else:
            self.start_port = self.settings.value("start_port", 5000, type=int)
            self.theme_mode = self.settings.value("theme_mode", "auto", type=str)
            self.network = None

        self.network_available = True  # Track network status
        self.server_thread = None
        self.running = False
        self.theme = Theme(self.theme_mode)
        self.cameras: list[CameraWidget] = []
        self.tray_icon = None
        self.omt_quality = self.settings.value("omt_quality", "medium", type=str)
        self.camera_count = self.settings.value("camera_count", 4, type=int)
        self.running_camera_count = self.camera_count

        # Check for updates setting
        self.auto_check_updates = self.settings.value(
            "auto_check_updates", True, type=bool
        )

        self.setup_ui()
        self.setup_tray()
        self.apply_theme()

        # Show network dialog after window is shown
        QTimer.singleShot(500, self.show_network_dialog)

        # Check for updates on startup if enabled
        if self.auto_check_updates:
            QTimer.singleShot(2000, self.check_for_updates)  # Check after 2 seconds

    def setup_ui(self):
        self.setWindowTitle("Video Streamer Server")
        self.setMinimumSize(1100, 750)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.create_top_bar())
        layout.addWidget(self.create_status_bar())

        # Camera tabs
        self.tabs = QTabWidget()

        # Create cameras based on saved camera_count
        self.cameras = []
        self.create_camera_tabs()

        layout.addWidget(self.tabs)
        layout.addWidget(self.create_footer())

    def create_top_bar(self):
        bar = QFrame()
        bar.setFixedHeight(70)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 12, 20, 12)

        # Title section
        super_layout = QHBoxLayout()
        super_layout.setContentsMargins(0, 0, 0, 0)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        title_icon_layout = QHBoxLayout()
        title_icon_layout.setContentsMargins(0, 0, 0, 0)
        if icon_path.exists():
            icon_label = QLabel()
            pixmap = QPixmap(str(icon_path)).scaled(
                50,
                50,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(pixmap)
            super_layout.addWidget(icon_label)

        title = QLabel("Video Streamer Server")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)

        title_layout.addWidget(title)

        subtitle = QLabel("Multi-camera streaming hub for vMix & OBS")
        subtitle_font = QFont()
        subtitle_font.setPointSize(9)
        subtitle.setFont(subtitle_font)
        title_layout.addWidget(subtitle)

        super_layout.addLayout(title_layout)
        layout.addLayout(super_layout)

        layout.addStretch()

        # Theme toggle button
        self.theme_btn = QPushButton()
        self.update_theme_button()
        self.theme_btn.setFixedSize(60, 42)
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self.cycle_theme)
        layout.addWidget(self.theme_btn)

        # Settings button
        settings_btn = QPushButton(" ⚙️ ")
        settings_btn.setFixedSize(60, 42)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.show_settings)
        layout.addWidget(settings_btn)

        # Minimize button
        minimize_btn = QPushButton(" ➖ ")
        minimize_btn.setFixedSize(60, 42)
        minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        minimize_btn.setToolTip("Minimize to tray (Ctrl+H)")
        minimize_btn.clicked.connect(self.minimize_to_tray)
        layout.addWidget(minimize_btn)

        # About button
        about_btn = QPushButton(" ℹ️ ")
        about_btn.setFixedSize(60, 42)
        about_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        about_btn.clicked.connect(self.show_about)
        layout.addWidget(about_btn)

        # Start/Stop button
        self.toggle_btn = QPushButton("▶️ Start Server")
        self.toggle_btn.setFixedSize(142, 42)
        toggle_font = QFont()
        toggle_font.setBold(True)
        self.toggle_btn.setFont(toggle_font)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_server)
        layout.addWidget(self.toggle_btn)

        return bar

    def create_status_bar(self):
        bar = QFrame()
        bar.setFixedHeight(50)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)

        self.server_status = QLabel("🔴 Stopped")
        status_font = QFont()
        status_font.setBold(True)
        self.server_status.setFont(status_font)
        layout.addWidget(self.server_status)

        self.camera_count_label = QLabel(f"0/{self.camera_count} cameras connected")
        layout.addWidget(self.camera_count_label)

        layout.addStretch()

        self.network_label = QLabel("Server IP Address: Not configured")
        layout.addWidget(self.network_label)

        return bar

    def create_camera_tabs(self):
        """Create camera tabs based on camera_count setting"""
        # Clear existing tabs
        self.tabs.clear()
        self.cameras.clear()

        # Create new tabs
        for i in range(1, self.camera_count + 1):
            cam = CameraWidget(i, self.start_port + i - 1, self.theme)
            self.cameras.append(cam)
            self.tabs.addTab(cam, f"🔴 Camera {i}: {self.start_port + i - 1}")

    def create_footer(self):
        footer = QFrame()
        footer.setFixedHeight(40)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 10, 20, 10)

        # Store reference to footer label for updates
        self.footer_label = QLabel(
            f"Server listening on ports {self.start_port}-{self.start_port + self.camera_count - 1} • OMT Protocol"
        )
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.footer_label)

        return footer

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)

        if icon_path.exists():
            # Set application icon with size
            icon = QIcon(str(icon_path))
        else:
            # Create a simple colored icon
            pixmap = QPixmap(64, 64)
            pixmap.fill(QColor(79, 70, 229))
            icon = QIcon(pixmap)

        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()

        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        logs_action = QAction("View Logs Folder", self)
        logs_action.triggered.connect(self.open_logs_folder)
        tray_menu.addAction(logs_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def open_logs_folder(self):
        """Open the logs folder in file explorer"""
        try:
            if self.log_file_path:
                log_dir = self.log_file_path.parent
            else:
                # Fallback if log_file_path not set
                import os

                appdata = os.getenv("APPDATA")
                if not appdata:
                    import tempfile

                    appdata = tempfile.gettempdir()
                log_dir = Path(appdata) / "VideoStreamerServer" / "logs"

            # Open folder in file explorer
            if sys.platform == "win32":
                import subprocess

                subprocess.Popen(["explorer", str(log_dir)])
            elif sys.platform == "darwin":  # macOS
                import subprocess

                subprocess.Popen(["open", str(log_dir)])
            else:  # Linux
                import subprocess

                subprocess.Popen(["xdg-open", str(log_dir)])
        except Exception as e:
            logger.error(f"Could not open logs folder: {e}")
            QMessageBox.information(
                self,
                "Logs Location",
                f"Logs are stored at:\n{log_dir if 'log_dir' in locals() else 'Unknown location'}",
            )

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()

    def update_theme_button(self):
        """Update theme button icon"""
        if self.theme_mode == "auto":
            self.theme_btn.setText(" 🌓 ")
        elif self.theme_mode == "dark":
            self.theme_btn.setText(" 🌙 ")
        else:
            self.theme_btn.setText(" ☀️ ")

    def cycle_theme(self):
        """Cycle through theme modes"""
        if self.theme_mode == "auto":
            self.theme_mode = "dark"
        elif self.theme_mode == "dark":
            self.theme_mode = "light"
        else:
            self.theme_mode = "auto"

        self.theme.mode = self.theme_mode
        self.settings.setValue("theme_mode", self.theme_mode)
        self.apply_theme()
        self.update_theme_button()

    def apply_theme(self):
        """Apply current theme to application"""
        self.setStyleSheet(self.theme.get_stylesheet())

    def show_network_dialog(self):
        if self.network and self.network_available:
            return

        dialog = NetworkSelectionDialog(self.theme, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.network = dialog.selected_network
            self.network_available = True
            if self.network:
                self.network_label.setText(f"Server IP Address: {self.network['ip']}")
                # Auto-start server
                self.start_server()

    def show_about(self):
        about_text = f"""
            Video Streamer Server v{APP_VERSION}
            © 2025 Vickerdent Corporation

            Log file: {self.log_file_path}
        """
        QMessageBox.about(self, "About", about_text)

    def show_settings(self):
        dialog = SettingsDialog(
            self.start_port,
            self.theme_mode,
            self.theme,
            self.omt_quality,
            self.camera_count,
            self.running,  # server_running
            self.auto_check_updates,
            self.test_network_callback,
            self,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            restart_needed = False
            port_changed = False

            # Update port
            if dialog.new_port != self.start_port and not self.running:
                self.start_port = dialog.new_port
                self.settings.setValue("start_port", self.start_port)
                port_changed = True

            # Check if camera count changed
            if dialog.new_camera_count != self.camera_count:
                # Save to settings for next restart, but don't update self.camera_count yet
                self.settings.setValue("camera_count", dialog.new_camera_count)
                restart_needed = True

                logger.info(
                    f"Camera count will change from {self.camera_count} to {dialog.new_camera_count} after restart\n"
                    f"Server currently running with {self.running_camera_count} cameras"
                )

            # Update OMT quality
            if dialog.new_omt_quality != self.omt_quality:
                self.omt_quality = dialog.new_omt_quality
                self.settings.setValue("omt_quality", self.omt_quality)
                # Apply to server if running
                if self.running and self.server_thread:
                    self.apply_omt_quality_change()

            # Update auto-check updates
            if dialog.new_auto_check_updates != self.auto_check_updates:
                self.auto_check_updates = dialog.new_auto_check_updates
                self.settings.setValue("auto_check_updates", self.auto_check_updates)

            # Update theme
            if dialog.new_theme_mode != self.theme_mode:
                self.theme_mode = dialog.new_theme_mode
                self.theme.mode = self.theme_mode
                self.settings.setValue("theme_mode", self.theme_mode)
                self.apply_theme()
                self.update_theme_button()

            # Update UI if port changed
            if port_changed:
                self.update_all_camera_displays()

            # Show restart prompt if needed
            if restart_needed:
                self.offer_app_restart()

    def start_server(self):
        if self.running:
            return

        lib_path = (
            str(get_resource_path("libraries/libomt.dll"))
            if os.name == "nt"
            else str(get_resource_path("libraries/libomt.so"))
        )

        if self.server_thread:
            try:
                self.server_thread.connection_changed.disconnect()
                self.server_thread.error_occurred.disconnect()
                self.server_thread.server_stopped.disconnect()
                self.server_thread.network_status_changed.disconnect()
            except Exception:
                pass

        self.server_thread = ServerThread(
            self.network["ip"] if self.network else "0.0.0.0",
            self.start_port,
            "omt",
            lib_path,
            self.camera_count,
            self.omt_quality,
        )

        # Track what the server is actually running
        self.running_camera_count = self.camera_count

        self.server_thread.connection_changed.connect(
            self.on_connection_changed,
            Qt.ConnectionType.QueuedConnection,  # type: ignore
        )

        self.server_thread.frame_received.connect(
            self.on_frame_received,
            Qt.ConnectionType.QueuedConnection,  # type: ignore
        )

        self.server_thread.error_occurred.connect(
            self.on_error,
            Qt.ConnectionType.QueuedConnection,  # type: ignore
        )
        self.server_thread.server_stopped.connect(
            self.on_server_stopped,
            Qt.ConnectionType.QueuedConnection,  # type: ignore
        )

        self.server_thread.network_status_changed.connect(
            self.on_network_status_changed,
            Qt.ConnectionType.QueuedConnection,  # type: ignore
        )

        self.server_thread.start()

        self.running = True
        self.server_status.setText("🟢 Running")
        self.toggle_btn.setText("⏹️ Stop Server")

        logger.info("Server started from GUI")

    def toggle_server(self):
        if self.running:
            if self.server_thread:
                self.server_thread.stop()
        else:
            # Check if network is available before starting
            if not self.network or not self.network_available:
                logger.warning("Got here")
                logger.info(f"Network is {self.network}")

                # Show network selection dialog
                self.show_network_dialog()

                # After dialog, check if network was selected
                if not self.network or not self.network_available:
                    QMessageBox.warning(
                        self,
                        "No viable Network Selected",
                        "Please connect to an available network and try again.\n\n"
                        "Make sure you have an active WiFi or Ethernet connection.",
                    )
                    return
            else:
                self.start_server()

    def on_server_stopped(self):
        self.running = False
        self.server_status.setText("🔴 Stopped")
        self.toggle_btn.setText("▶️ Start Server")

        for cam in self.cameras:
            cam.set_connected(False)
        self.update_camera_count()
        self.update_all_camera_displays()

    def on_connection_changed(self, cam_id: int, connected: bool, info: dict[str, Any]):
        try:
            # Validate camera ID
            if not (1 <= cam_id <= self.running_camera_count):  # Use dynamic count
                logger.warning(
                    f"Invalid camera ID: {cam_id} (max: {self.running_camera_count})"
                )
                return

            # Validate cameras list is initialized
            if not self.cameras or len(self.cameras) < cam_id:
                logger.warning(f"Cameras not initialized yet for ID {cam_id}")
                return

            # Get camera widget safely
            camera_widget = self.cameras[cam_id - 1]
            if not camera_widget:
                logger.error(f"Camera widget {cam_id} is None")
                return

            # Update camera connection state
            try:
                camera_widget.set_connected(connected, info if connected else None)
            except Exception as e:
                logger.error(
                    f"Error in set_connected for camera {cam_id}: {e}", exc_info=True
                )

            # Update tab icon safely
            try:
                icon = "🟢" if connected else "🔴"
                port = self.start_port + cam_id - 1
                tab_text = f"{icon} Camera {cam_id}: {port}"

                self.tabs.setTabText(cam_id - 1, tab_text)
            except Exception as e:
                logger.error(
                    f"Error updating tab text for camera {cam_id}: {e}", exc_info=True
                )

            # Update connection count
            try:
                self.update_camera_count()
            except Exception as e:
                logger.error(f"Error updating camera count: {e}", exc_info=True)

        except Exception as e:
            logger.error(
                f"Critical error in on_connection_changed for camera {cam_id}: {e}",
                exc_info=True,
            )

    def on_frame_received(self, cam_id: int, frame: np.ndarray):
        """Route frames to correct camera widget"""
        # Use actual widget count (not self.camera_count which may be pending change)
        max_camera_id = self.running_camera_count if self.running else len(self.cameras)

        if 1 <= cam_id <= max_camera_id and cam_id <= len(self.cameras):
            self.cameras[cam_id - 1].display_frame(cam_id, frame)
        else:
            logger.debug(
                f"Frame for camera {cam_id} ignored (have {max_camera_id} widgets)"
            )

    def update_camera_count(self):
        count = sum(1 for c in self.cameras if c.connected)
        if hasattr(self, "camera_count_label") and hasattr(self, "camera_count"):
            self.camera_count_label.setText(
                f"{count}/{self.camera_count} cameras connected"
            )

    def on_error(self, error):
        """Display user-friendly error messages"""
        # Parse error for user-friendly message
        error_str = str(error)

        if "port" in error_str.lower() and "use" in error_str.lower():
            user_message = (
                "Port already in use.\n\n"
                "Please stop the server and try again, or change the port in Settings."
            )
        elif "bind" in error_str.lower():
            user_message = (
                "Cannot bind to network interface.\n\n"
                "The selected network may be unavailable. Please check your network settings."
            )
        elif "connection" in error_str.lower():
            user_message = (
                "Connection error.\n\n"
                "Please check that both devices are on the same network."
            )
        elif "omt" in error_str.lower():
            user_message = (
                "OMT streaming error.\n\n"
                "Please check that vMix is running and OMT inputs are configured."
            )
        else:
            user_message = f"Server Error:\n\n{error}"

        QMessageBox.critical(self, "Server Error", user_message)

    def on_network_status_changed(self, available: bool, ip: str):
        """Handle network status changes"""
        logger.info(f"🔔 GUI received network status: available={available}, ip={ip}")

        self.update_network_status(available, ip if available else None)

        if not available:
            logger.warning(f"Showing network disconnected dialog for {ip}")
            QMessageBox.warning(
                self,
                "Network Disconnected",
                f"The network interface ({ip}) is no longer available.\n\n"
                "All connected cameras have been disconnected.\n"
                "The server will resume when the network is restored.",
            )
        else:
            logger.info(f"Network {ip} restored")

    def quit_application(self):
        logger.info("Quitting application...")

        # Stop server thread
        if self.running and self.server_thread:
            try:
                logger.debug("Stopping server thread...")
                self.server_thread.stop()
                if not self.server_thread.wait(5000):  # 5 second timeout
                    logger.warning("Server thread didn't stop, terminating")
                    self.server_thread.terminate()
                    self.server_thread.wait(1000)
            except Exception as e:
                logger.error(f"Error stopping server thread: {e}")

        # Clear camera references
        for cam in self.cameras:
            cam.handler = None
            cam.last_pixmap = None

        # Hide tray icon
        if self.tray_icon:
            self.tray_icon.hide()

        # Force garbage collection
        import gc

        gc.collect()

        # Quit Qt application
        QApplication.quit()

    def closeEvent(self, event):
        # If restarting, just accept and close without dialog
        if self.is_restarting:
            logger.info("Closing for restart...")
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Exit",
            "Do you want to minimize to tray or quit?\n\n"
            "Yes = Quit completely\n"
            "No = Minimize to tray\n"
            "Cancel = Stay open",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.quit_application()
            event.accept()
        elif reply == QMessageBox.StandardButton.No:
            event.ignore()
            self.hide()
            if self.tray_icon:
                self.tray_icon.showMessage(
                    "Video Streamer Server",
                    "Application minimized to tray",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
        else:
            event.ignore()

    def update_network_status(self, available: bool, ip: str | None = None):
        """Update network status in UI"""
        self.network_available = available

        if not available:
            self.network_label.setText("Server IP Address: Network Disconnected")
            self.network_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            logger.warning("Network disconnected")
        elif ip:
            self.network_label.setText(f"Server IP Address: {ip}")
            self.network_label.setStyleSheet("")  # Reset style
        else:
            self.network_label.setText("Server IP Address: Not configured")
            self.network_label.setStyleSheet("")

    def test_network_callback(self):
        """Test network status callback manually"""
        logger.info("Testing network status callback...")
        self.on_network_status_changed(False, "192.168.0.198")

        QTimer.singleShot(
            3000, lambda: self.on_network_status_changed(True, "192.168.0.198")
        )

    def check_for_updates(self, silent=True):
        """Check for application updates"""
        from utils.update_checker import UpdateCheckThread, show_update_dialog

        self.update_thread = UpdateCheckThread()

        def on_update_available(latest_version, download_url):
            show_update_dialog(self, latest_version, download_url)

        def on_error(error_msg):
            if not silent:
                QMessageBox.warning(
                    self,
                    "Update Check Failed",
                    f"Could not check for updates:\n{error_msg}",
                )

        self.update_thread.update_available.connect(on_update_available)
        self.update_thread.error_occurred.connect(on_error)
        self.update_thread.start()

    def minimize_to_tray(self):
        """Minimize window to system tray and reduce resource usage"""
        # Pause video frame updates for all cameras
        for cam in self.cameras:
            cam.pause_preview()

        self.hide()
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Video Streamer Server",
                "Application minimized to tray. Video previews paused to save resources.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeySequence

        # Ctrl+H to minimize
        if event.matches(
            QKeySequence.StandardKey.HelpContents
        ):  # This is Ctrl+H on most systems
            pass
        elif (
            event.key() == Qt.Key.Key_H
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ):
            self.minimize_to_tray()
            event.accept()
            return

        super().keyPressEvent(event)

    def showEvent(self, event):
        """Resume video updates when window is shown"""
        super().showEvent(event)

        # Resume video frame updates
        for cam in self.cameras:
            cam.resume_preview()

    def update_port_display(self):
        """Update port display in footer"""
        if hasattr(self, "footer_label"):
            self.footer_label.setText(
                f"Server listening on ports {self.start_port}-{self.start_port + self.camera_count - 1} • OMT Protocol"
            )

    def apply_omt_quality_change(self):
        """Apply OMT quality change to running server"""
        quality_map = {"low": 1, "medium": 50, "high": 100}

        if self.server_thread and hasattr(self.server_thread, "update_omt_quality"):
            self.server_thread.update_omt_quality(quality_map[self.omt_quality])

    def update_all_camera_displays(self):
        """Update all camera tab labels and port displays"""
        # Update tab labels
        for i, cam in enumerate(self.cameras):
            cam.port = self.start_port + i
            # Update info label
            cam.info_label.setText(f"Port {cam.port} • Waiting for connection")

            # Update tab text
            icon = "🟢" if cam.connected else "🔴"
            self.tabs.setTabText(i, f"{icon} Camera {cam.cam_id}: {cam.port}")

        # Update footer
        self.update_port_display()

    def offer_app_restart(self):
        """Offer to restart the application automatically"""
        from PyQt6.QtWidgets import QMessageBox

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Restart Required")
        msg_box.setText("Application Restart Required")
        msg_box.setInformativeText(
            "The camera count setting has changed and requires an application restart.\n\n"
            "Would you like to restart now?"
        )

        restart_btn = msg_box.addButton(
            "Restart Now", QMessageBox.ButtonRole.AcceptRole
        )
        msg_box.addButton("Restart Later", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(restart_btn)

        msg_box.exec()

        if msg_box.clickedButton() == restart_btn:
            self.restart_application()

    def restart_application(self):
        """Restart the application with new settings"""
        logger.info("Restarting application...")

        # Set restart flag to bypass close dialog
        self.is_restarting = True

        # Stop server gracefully
        if self.running and self.server_thread:
            try:
                logger.info("Stopping server for restart...")
                # Stop streaming first
                self.server_thread.stop()

                # Wait longer for complete shutdown
                if not self.server_thread.wait(5000):  # Increased to 5 seconds
                    logger.warning("Server thread didn't stop gracefully, terminating")
                    self.server_thread.terminate()
                    self.server_thread.wait(2000)

                # Give the OS time to release the ports
                import time

                time.sleep(1)
            except Exception as e:
                logger.error(f"Error stopping server during restart: {e}")

        # Clear camera references
        for cam in self.cameras:
            cam.handler = None
            cam.last_pixmap = None

        # Hide tray icon
        if self.tray_icon:
            self.tray_icon.hide()

        # Get the executable path
        import subprocess
        import sys

        try:
            if getattr(sys, "frozen", False):
                # Running as compiled executable
                executable = sys.executable
                logger.info(f"Restarting executable: {executable}")
                subprocess.Popen([executable])
            else:
                # Running as script
                executable = sys.executable
                script = sys.argv[0]
                logger.info(f"Restarting script: {executable} {script}")
                subprocess.Popen([executable, script])

            # Force close without dialog
            QApplication.quit()

        except Exception as e:
            logger.error(f"Failed to restart application: {e}")
            QMessageBox.critical(
                self,
                "Restart Failed",
                f"Could not restart automatically:\n{e}\n\n"
                "Please close and restart the application manually.",
            )
