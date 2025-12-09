import os
import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, 
    QHBoxLayout, QFrame, QMessageBox, QApplication, 
    QSystemTrayIcon, QMenu, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QFont, QPixmap, QIcon, QAction, QColor

from .dialogs import NetworkSelectionDialog, SettingsDialog
from .camera_widget import CameraWidget
from .server_thread import ServerThread
from .theme import Theme
from constants import get_resource_path
from utils.fallback_mode import FallbackMode

from constants import APP_VERSION, ICON_PATH as icon_path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self, fallback_mode=None, restore_session=False, last_state=None):
        super().__init__()

        self.fallback_mode = fallback_mode or FallbackMode()
        self.log_file_path = None # Will be set by main()
        
        # Setup settings
        self.settings = QSettings('Vickerdent Corporation', 'VideoStreamerServer')
        
        # Restore from crash or use defaults
        if restore_session and last_state:
            self.start_port = last_state.get('start_port', 5000)
            self.theme_mode = last_state.get('theme_mode', 'auto')
            # Restore network if available
            if last_state.get('network_ip'):
                self.network = {'ip': last_state['network_ip']}
        else:
            self.start_port = self.settings.value('start_port', 5000, type=int)
            self.theme_mode = self.settings.value('theme_mode', 'auto', type=str)
            self.network = None

        self.server_thread = None
        self.running = False
        self.theme = Theme(self.theme_mode)
        self.cameras = []
        self.tray_icon = None
        
        self.setup_ui()
        self.setup_tray()
        self.apply_theme()
        
        # Show network dialog after window is shown
        QTimer.singleShot(500, self.show_network_dialog)
    
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
        
        for i in range(1, 5):
            cam = CameraWidget(i, self.start_port + i - 1, self.theme)
            self.cameras.append(cam)
            self.tabs.addTab(cam, f"🔴 Camera {i}: {self.start_port + i - 1}")
        
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
            pixmap = QPixmap(str(icon_path)).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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
        
        self.camera_count = QLabel("0/4 cameras connected")
        layout.addWidget(self.camera_count)
        
        layout.addStretch()
        
        self.network_label = QLabel("Server IP Address: Not configured")
        layout.addWidget(self.network_label)
        
        return bar
    
    def create_footer(self):
        footer = QFrame()
        footer.setFixedHeight(40)
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 10, 20, 10)
        
        label = QLabel(f"Server listening on ports {self.start_port}-{self.start_port+3} • OMT Protocol")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
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
                appdata = os.getenv('APPDATA')
                if not appdata:
                    import tempfile
                    appdata = tempfile.gettempdir()
                log_dir = Path(appdata) / 'VideoStreamerServer' / 'logs'
            
            # Open folder in file explorer
            if sys.platform == 'win32':
                import subprocess
                subprocess.Popen(['explorer', str(log_dir)])
            elif sys.platform == 'darwin':  # macOS
                import subprocess
                subprocess.Popen(['open', str(log_dir)])
            else:  # Linux
                import subprocess
                subprocess.Popen(['xdg-open', str(log_dir)])
        except Exception as e:
            logger.error(f"Could not open logs folder: {e}")
            QMessageBox.information(
                self,
                "Logs Location",
                f"Logs are stored at:\n{log_dir if 'log_dir' in locals() else 'Unknown location'}"
            )
    
    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()
    
    def update_theme_button(self):
        """Update theme button icon"""
        if self.theme_mode == 'auto':
            self.theme_btn.setText(" 🌓 ")
        elif self.theme_mode == 'dark':
            self.theme_btn.setText(" 🌙 ")
        else:
            self.theme_btn.setText(" ☀️ ")
    
    def cycle_theme(self):
        """Cycle through theme modes"""
        if self.theme_mode == 'auto':
            self.theme_mode = 'dark'
        elif self.theme_mode == 'dark':
            self.theme_mode = 'light'
        else:
            self.theme_mode = 'auto'
        
        self.theme.mode = self.theme_mode
        self.settings.setValue('theme_mode', self.theme_mode)
        self.apply_theme()
        self.update_theme_button()
    
    def apply_theme(self):
        """Apply current theme to application"""
        self.setStyleSheet(self.theme.get_stylesheet())
    
    def show_network_dialog(self):
        if self.network:
            return
        
        dialog = NetworkSelectionDialog(self.theme, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.network = dialog.selected_network
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
            self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update port
            if dialog.new_port != self.start_port:
                self.start_port = dialog.new_port
                self.settings.setValue('start_port', self.start_port)
                
                # Update camera ports
                for i, cam in enumerate(self.cameras):
                    cam.port = self.start_port + i
                    cam.info_label.setText(f"Port {cam.port} • Waiting for connection")
                
                # Update footer
                footer_label = self.findChild(QLabel) # TODO: improve this lookup
                if footer_label:
                    footer_label.setText(f"Server listening on ports {self.start_port}-{self.start_port+3}  • OMT Protocol")
            
            # Update theme
            if dialog.new_theme_mode != self.theme_mode:
                self.theme_mode = dialog.new_theme_mode
                self.theme.mode = self.theme_mode
                self.settings.setValue('theme_mode', self.theme_mode)
                self.apply_theme()
                self.update_theme_button()
    
    def start_server(self):
        if self.running:
            return
        
        lib_path = str(get_resource_path("libraries/libomt.dll")) if os.name == 'nt' else str(get_resource_path("libraries/libomt.so"))
        
        if self.server_thread:
            try:
                self.server_thread.connection_changed.disconnect()
                self.server_thread.error_occurred.disconnect()
                self.server_thread.server_stopped.disconnect()
            except Exception:
                pass
        
        self.server_thread = ServerThread(
            self.network['ip'] if self.network else '0.0.0.0',
            self.start_port,
            'omt',
            lib_path
        )
        
        self.server_thread.connection_changed.connect(
            self.on_connection_changed,
            Qt.ConnectionType.QueuedConnection # type: ignore
        )

        self.server_thread.frame_received.connect(
            self.on_frame_received,
            Qt.ConnectionType.QueuedConnection # type: ignore
        )
        
        self.server_thread.error_occurred.connect(
            self.on_error,
            Qt.ConnectionType.QueuedConnection # type: ignore
        )
        self.server_thread.server_stopped.connect(
            self.on_server_stopped,
            Qt.ConnectionType.QueuedConnection # type: ignore
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
            if not self.network:
                self.show_network_dialog()
            else:
                self.start_server()
    
    def on_server_stopped(self):
        self.running = False
        self.server_status.setText("🔴 Stopped")
        self.toggle_btn.setText("▶️ Start Server")
        
        for cam in self.cameras:
            cam.set_connected(False)
        self.update_camera_count()
    
    def on_connection_changed(self, cam_id, connected, info):
        try:
            # Validate camera ID
            if not (1 <= cam_id <= 4):
                logger.warning(f"Invalid camera ID: {cam_id}")
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
                logger.error(f"Error in set_connected for camera {cam_id}: {e}", exc_info=True)
            
            # Update tab icon safely
            try:
                icon = "🟢" if connected else "🔴"
                self.tabs.setTabText(cam_id - 1, f"{icon} Camera {cam_id}: {self.start_port + cam_id - 1}")
            except Exception as e:
                logger.error(f"Error updating tab text for camera {cam_id}: {e}", exc_info=True)
            
            # Update connection count
            try:
                self.update_camera_count()
            except Exception as e:
                logger.error(f"Error updating camera count: {e}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Critical error in on_connection_changed for camera {cam_id}: {e}", exc_info=True)
            # Don't let the exception propagate - this would crash the app

    def on_frame_received(self, cam_id, frame):
        """Route frames to correct camera widget"""
        if 1 <= cam_id <= 4:
            self.cameras[cam_id - 1].display_frame(cam_id, frame)
    
    def update_camera_count(self):
        count = sum(1 for c in self.cameras if c.connected)
        self.camera_count.setText(f"{count}/4 cameras connected")
    
    def on_error(self, error):
        QMessageBox.critical(self, "Server Error", f"An error occurred:\n{error}")
    
    def quit_application(self):
        logger.info("Quitting application...")
        
        # Stop video receivers first
        for cam in self.cameras:
            try:
                if cam.video_receiver:
                    logger.debug(f"Stopping video receiver for camera {cam.cam_id}")
                    cam.stop_video_receiver()
            except Exception as e:
                logger.error(f"Error stopping video receiver: {e}")
        
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
        reply = QMessageBox.question(
            self,
            'Exit',
            "Do you want to minimize to tray or quit?\n\n"
            "Yes = Quit completely\n"
            "No = Minimize to tray\n"
            "Cancel = Stay open",
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No | 
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
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
                    2000
                )
        else:
            event.ignore()