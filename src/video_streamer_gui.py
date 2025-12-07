"""
Enhanced Video Streamer GUI - Complete PyQt6 Implementation
Modern GUI with theme switching, network selection, and comprehensive features

Install requirements:
    pip install PyQt6 opencv-python numpy pillow

Usage:
    python enhanced_omt_bridge_gui.py
"""

from datetime import datetime
import os
import sys
import asyncio
import cv2
import numpy as np
import traceback
import ctypes
from pathlib import Path
import logging
from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, 
    QHBoxLayout, QFrame, QMessageBox, QApplication, 
    QSystemTrayIcon, QMenu, QButtonGroup, QRadioButton,
    QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QFont, QPixmap, QImage, QIcon, QAction, QPalette, QColor

# Import existing bridge components
from omt_bridge_tcp import OMTBridgeServer, PhoneStreamHandler, logger
from network_diagnostics import get_all_interfaces

def get_resource_path(relative_path: str) -> Path:
    """
    Get absolute path to resource, works for dev and for PyInstaller bundle.
    
    When PyInstaller bundles files, it extracts them to a temp folder (_MEIPASS).
    This function finds the correct path in both scenarios.
    
    Args:
        relative_path: Path relative to the script (e.g., "logo.png", "libraries/libomt.dll")
    
    Returns:
        Absolute Path object
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS) # type: ignore
        logger.debug(f"Running in PyInstaller bundle: {base_path}")
    except AttributeError:
        # Running in normal Python environment
        base_path = Path(__file__).resolve().parent
        logger.debug(f"Running in development mode: {base_path}")
    
    resource_path = base_path / relative_path
    logger.debug(f"Resource path for '{relative_path}': {resource_path}")
    
    return resource_path


icon_path = get_resource_path("app_logo.png")
APP_VERSION = "1.0.0"

class Theme:
    """Theme manager for light/dark modes"""
    
    def __init__(self, mode='auto'):
        self.mode = mode  # 'auto', 'dark', 'light'
        self.system_dark = self.is_system_dark()
        
    def is_system_dark(self):
        """Detect system dark mode preference"""
        palette = QApplication.palette()
        bg_color = palette.color(QPalette.ColorRole.Window)
        return bg_color.lightness() < 128
    
    @property
    def is_dark(self):
        """Current effective dark mode state"""
        if self.mode == 'auto':
            return self.system_dark
        return self.mode == 'dark'
    
    def get_stylesheet(self):
        """Generate complete stylesheet for current theme"""
        if self.is_dark:
            return self._dark_stylesheet()
        else:
            return self._light_stylesheet()
    
    def _dark_stylesheet(self):
        return """
            QMainWindow, QDialog, QWidget {
                background-color: #0d1117;
                color: #e6edf3;
            }
            QLabel {
                color: #e6edf3;
            }
            QPushButton {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #484f58;
            }
            QPushButton:pressed {
                background-color: #282e35;
            }
            QPushButton:disabled {
                background-color: #161b22;
                color: #484f58;
            }
            QFrame {
                border: none;
            }
            QTabWidget::pane {
                border: 1px solid #30363d;
                background-color: #161b22;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #21262d;
                color: #8b949e;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #30363d;
            }
            QTabBar::tab:selected {
                background-color: #161b22;
                color: #e6edf3;
                border-bottom-color: #161b22;
            }
            QTabBar::tab:hover:!selected {
                background-color: #30363d;
            }
            QSpinBox {
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid #30363d;
                padding: 6px;
                border-radius: 6px;
            }
            QSpinBox:focus {
                border-color: #58a6ff;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QRadioButton {
                color: #e6edf3;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #30363d;
                background-color: #0d1117;
            }
            QRadioButton::indicator:checked {
                background-color: #58a6ff;
                border-color: #58a6ff;
            }
            QProgressBar {
                border: 1px solid #30363d;
                border-radius: 4px;
                text-align: center;
                background-color: #161b22;
                color: #e6edf3;
            }
            QProgressBar::chunk {
                background-color: #238636;
                border-radius: 3px;
            }
        """
    
    def _light_stylesheet(self):
        return """
            QMainWindow, QDialog, QWidget {
                background-color: #ffffff;
                color: #24292f;
            }
            QLabel {
                color: #24292f;
            }
            QPushButton {
                background-color: #f6f8fa;
                color: #24292f;
                border: 1px solid #d0d7de;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
                border-color: #d0d7de;
            }
            QPushButton:pressed {
                background-color: #e1e4e8;
            }
            QPushButton:disabled {
                background-color: #f6f8fa;
                color: #6e7781;
            }
            QFrame {
                border: none;
            }
            QTabWidget::pane {
                border: 1px solid #d0d7de;
                background-color: #ffffff;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #f6f8fa;
                color: #57606a;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #d0d7de;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #24292f;
                border-bottom-color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #f3f4f6;
            }
            QSpinBox {
                background-color: #f6f8fa;
                color: #24292f;
                border: 1px solid #d0d7de;
                padding: 6px;
                border-radius: 6px;
            }
            QSpinBox:focus {
                border-color: #0969da;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QRadioButton {
                color: #24292f;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #d0d7de;
                background-color: #ffffff;
            }
            QRadioButton::indicator:checked {
                background-color: #0969da;
                border-color: #0969da;
            }
            QProgressBar {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                text-align: center;
                background-color: #f6f8fa;
                color: #24292f;
            }
            QProgressBar::chunk {
                background-color: #2da44e;
                border-radius: 3px;
            }
        """

class DLLChecker:
    """Check for required DLLs before starting the application."""
    
    @staticmethod
    def check_dll_exists(dll_path: Path) -> bool:
        """Check if a DLL file exists."""
        return dll_path.exists() and dll_path.is_file()
    
    @staticmethod
    def check_dll_loadable(dll_path: Path) -> tuple[bool, str]:
        """
        Try to load a DLL and check for missing dependencies.
        
        Returns:
            (success: bool, error_message: str)
        """
        if not dll_path.exists():
            return False, f"File not found: {dll_path}"
        
        try:
            # Try to load the DLL
            _ = ctypes.CDLL(str(dll_path))
            return True, ""
        except OSError as e:
            error_str = str(e)
            
            # Parse Windows error codes
            if "0xc000007b" in error_str.lower():
                return False, "DLL architecture mismatch (32-bit vs 64-bit)"
            elif "0xc0000135" in error_str.lower():
                return False, "Missing dependency DLLs"
            elif "126" in error_str:  # ERROR_MOD_NOT_FOUND
                return False, "Dependent DLL not found"
            else:
                return False, f"Cannot load: {error_str}"
    
    @staticmethod
    def check_all_dependencies(base_path: Path) -> dict:
        """
        Check all required DLLs.
        
        Returns:
            Dictionary with check results
        """
        results = {
            'all_ok': True,
            'missing': [],
            'unloadable': [],
            'details': {}
        }
        
        # List of required DLLs
        required_dlls = [
            'libraries/libomt.dll',
            'libraries/libvmx.dll',
        ]
        
        logger = logging.getLogger(__name__)
        logger.info("Checking DLL dependencies...")
        
        for dll_rel_path in required_dlls:
            dll_path = base_path / dll_rel_path
            dll_name = Path(dll_rel_path).name
            
            # Check existence
            if not DLLChecker.check_dll_exists(dll_path):
                results['all_ok'] = False
                results['missing'].append(dll_name)
                results['details'][dll_name] = 'File not found'
                logger.error(f"❌ {dll_name}: NOT FOUND at {dll_path}")
                continue
            
            # Check if loadable
            loadable, error_msg = DLLChecker.check_dll_loadable(dll_path)
            if not loadable:
                results['all_ok'] = False
                results['unloadable'].append(dll_name)
                results['details'][dll_name] = error_msg
                logger.error(f"❌ {dll_name}: {error_msg}")
            else:
                results['details'][dll_name] = 'OK'
                logger.info(f"✅ {dll_name}: OK")
        
        return results
    
    @staticmethod
    def show_dll_error_dialog(check_results: dict):
        """Show detailed error dialog for DLL issues."""
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Missing Dependencies")
        
        # Build error message
        error_parts = []
        
        if check_results['missing']:
            error_parts.append("Missing DLL files:")
            for dll in check_results['missing']:
                error_parts.append(f"  • {dll}")
        
        if check_results['unloadable']:
            error_parts.append("\nDLLs with errors:")
            for dll in check_results['unloadable']:
                error = check_results['details'].get(dll, 'Unknown error')
                error_parts.append(f"  • {dll}: {error}")
        
        msg_box.setText("The application cannot start due to missing components.")
        msg_box.setInformativeText("\n".join(error_parts))
        
        # Add recovery suggestions
        suggestions = (
            "Possible solutions:\n\n"
            "1. Reinstall the application\n"
            "2. Install Visual C++ Redistributable:\n"
            "   https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
            "3. Check antivirus hasn't quarantined files\n"
            "4. Contact support@vickerdent.com for help"
        )
        msg_box.setDetailedText(suggestions)
        
        msg_box.setStandardButtons(QMessageBox.StandardButton.Close)
        msg_box.exec()

class FallbackMode:
    """Manage fallback behavior when features are unavailable."""
    
    def __init__(self):
        self.omt_available = False
        self.network_available = False
        self.features_disabled = []
    
    def check_omt_availability(self, lib_path: Path) -> bool:
        """Check if OMT library is available."""
        try:
            if not lib_path.exists():
                self.features_disabled.append("OMT streaming (library not found)")
                return False
            
            # Try to load
            loadable, error = DLLChecker.check_dll_loadable(lib_path)
            if not loadable:
                self.features_disabled.append(f"OMT streaming ({error})")
                return False
            
            self.omt_available = True
            return True
        except Exception as e:
            self.features_disabled.append(f"OMT streaming (error: {e})")
            return False
    
    def check_network_availability(self) -> bool:
        """Check if network features are available."""
        try:
            import netifaces
            interfaces = netifaces.interfaces()
            self.network_available = len(interfaces) > 0
            return self.network_available
        except Exception as e:
            self.features_disabled.append(f"Network detection ({e})")
            return False
    
    def show_degraded_mode_warning(self):
        """Show warning about disabled features."""
        if not self.features_disabled:
            return
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Limited Functionality")
        msg_box.setText(
            "Some features are unavailable and have been disabled:\n\n" +
            "\n".join(f"• {feature}" for feature in self.features_disabled)
        )
        msg_box.setInformativeText(
            "The application will continue with reduced functionality."
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()


def validate_startup_environment():
    """
    Validate the environment before starting the application.
    
    Returns:
        (success: bool, fallback_mode: FallbackMode)
    """
    logger = logging.getLogger(__name__)
    logger.info("Validating startup environment...")
    
    fallback = FallbackMode()
    
    # Get base path
    try:
        base_path = Path(sys._MEIPASS)  # type: ignore
    except AttributeError:
        base_path = Path(__file__).resolve().parent
    
    # Check DLLs
    dll_results = DLLChecker.check_all_dependencies(base_path)
    
    if not dll_results['all_ok']:
        logger.error("DLL dependency check failed")
        DLLChecker.show_dll_error_dialog(dll_results)
        return False, fallback
    
    # Check OMT availability (non-fatal)
    lib_path = base_path / 'libraries' / 'libomt.dll'
    fallback.check_omt_availability(lib_path)
    
    # Check network (non-fatal)
    fallback.check_network_availability()
    
    # Show warnings if degraded
    if fallback.features_disabled:
        logger.warning(f"Running in degraded mode: {fallback.features_disabled}")
        fallback.show_degraded_mode_warning()
    
    logger.info("✅ Startup validation complete")
    return True, fallback

class CrashRecovery:
    """Handle crash recovery and state restoration."""
    
    @staticmethod
    def save_state(state_data: dict):
        """Save application state for recovery."""
        try:
            import json
            import os
            
            appdata = os.getenv('APPDATA')
            if not appdata:
                # Fallback to temp directory if APPDATA not available
                import tempfile
                appdata = tempfile.gettempdir()
            
            state_file = Path(appdata) / 'VideoStreamerServer' / 'last_state.json'
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save state: {e}")
    
    @staticmethod
    def load_last_state() -> dict:
        """Load last saved state."""
        try:
            import json
            import os
            appdata = os.getenv('APPDATA')
            if not appdata:
                # Fallback to temp directory if APPDATA not available
                import tempfile
                appdata = tempfile.gettempdir()
            
            state_file = Path(appdata) / 'VideoStreamerServer' / 'last_state.json'
            
            if state_file.exists():
                with open(state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load last state: {e}")
        
        return {}
    
    @staticmethod
    def offer_recovery(last_state: dict) -> bool:
        """Ask user if they want to restore last session."""
        if not last_state:
            return False
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle("Restore Previous Session")
        msg_box.setText("The application closed unexpectedly last time.")
        msg_box.setInformativeText("Would you like to restore your previous settings?")
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        return msg_box.exec() == QMessageBox.StandardButton.Yes

class ServerThread(QThread):
    """Thread to run asyncio server"""
    connection_changed = pyqtSignal(int, bool, dict)
    frame_received = pyqtSignal(int, np.ndarray) 
    error_occurred = pyqtSignal(str)
    server_stopped = pyqtSignal()
    
    def __init__(self, bind_ip, start_port, output_type='omt', lib_path='libomt.dll'):
        super().__init__()
        self.bind_ip = bind_ip
        self.start_port = start_port
        self.output_type = output_type
        self.lib_path = lib_path
        self.server = None
        self.loop = None
        self.running = False
        self.shutdown_in_progress = False
        
    def run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            self.server = OMTBridgeServer(self.output_type, self.lib_path, self.bind_ip)
            
            for i, config in enumerate(self.server.configs):
                config.port = self.start_port + i
            
            self._patch_handlers()
            
            self.running = True
            logger.info(f"Server starting on {self.bind_ip}:{self.start_port}")
            
            self.loop.run_until_complete(self._run_server())
            
        except asyncio.CancelledError:
            logger.info("Server cancelled")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            if not self.shutdown_in_progress:  # Only emit if not shutting down
                self.error_occurred.emit(str(e))
        finally:
            self.running = False
            self.cleanup_loop()
            self.server_stopped.emit()
    
    async def _run_server(self):
        try:
            await self.server.start() # type: ignore
        except asyncio.CancelledError:
            await self.server.stop() # type: ignore
            raise
    
    def _patch_handlers(self):
        """Patch handlers to emit Qt signals with robust error handling"""
        original_handle = PhoneStreamHandler.handle_client
        thread = self
        
        async def patched_handle(handler, reader, writer):
            try:
                # Initial connection signal
                try:
                    thread.connection_changed.emit(handler.config.phone_id, True, {})
                except Exception as e:
                    logger.error(f"Error emitting initial connection signal: {e}")
                
                orig_config = handler.receive_config
                async def patched_config(r):
                    result = await orig_config(r)
                    if result:
                        try:
                            info = {
                                'device_model': handler.device_model,
                                'battery': handler.battery_percent,
                                'temperature': handler.cpu_temperature_celsius,
                                'resolution': f"{handler.current_width}x{handler.current_height}",
                                'fps': handler.current_fps,
                                'handler': handler
                            }
                            thread.connection_changed.emit(handler.config.phone_id, True, info)
                        except Exception as e:
                            logger.error(f"Error emitting config signal: {e}")
                    return result
                
                handler.receive_config = patched_config

                orig_process_video = handler.process_video_frame
                async def patched_process_video(data, flags, receive_time):
                    result = await orig_process_video(data, flags, receive_time)
                    
                    # Send RGB frame to GUI - but DON'T re-decode, handler already did it
                    if result and thread.running and not (flags & 0x2):
                        try:
                            # Handler already has the decoded frame in NV12 format
                            # Just convert the last NV12 data to RGB
                            if hasattr(handler, '_last_nv12_frame'):
                                rgb_frame = handler.nv12_to_rgb(
                                    handler._last_nv12_frame,
                                    handler.current_width,
                                    handler.current_height
                                )
                                thread.frame_received.emit(handler.config.phone_id, rgb_frame)
                        except Exception as e:
                            logger.debug(f"GUI frame error: {e}")  # Don't let GUI errors affect streaming
                    
                    return result
                
                handler.process_video_frame = patched_process_video

                await original_handle(handler, reader, writer)
                
            except asyncio.CancelledError:
                logger.info(f"Handler for phone {handler.config.phone_id} cancelled")
                raise
            except Exception as e:
                logger.error(f"Handler error for phone {handler.config.phone_id}: {e}", exc_info=True)
            finally:
                # Always emit disconnect signal, with error handling
                try:
                    # Check if thread/loop is still valid before emitting
                    if thread.running and thread.loop and not thread.loop.is_closed():
                        thread.connection_changed.emit(handler.config.phone_id, False, {})
                    else:
                        logger.debug(f"Skipping disconnect signal for phone {handler.config.phone_id} - thread stopping")
                except RuntimeError as e:
                    # This can happen if Qt has already been cleaned up
                    logger.debug(f"Could not emit disconnect signal (Qt already cleaned up): {e}")
                except Exception as e:
                    logger.error(f"Error emitting disconnect signal: {e}", exc_info=True)
        
        PhoneStreamHandler.handle_client = patched_handle # type: ignore

    def cleanup_loop(self):
        """Properly cleanup asyncio loop"""
        if self.loop and not self.loop.is_closed():
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                
                # Give tasks a moment to cancel
                if pending:
                    self.loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                
                self.loop.close()
                logger.debug("Asyncio loop cleaned up successfully")
            except Exception as e:
                logger.warning(f"Error cleaning up loop: {e}")
    
    def stop(self):
        """Stop server gracefully with improved error handling"""
        if not self.running or self.shutdown_in_progress:
            return
        
        logger.info("Stopping server...")
        self.shutdown_in_progress = True  # Prevent new signals
        self.running = False  # Set this FIRST to prevent new signals
        
        if self.loop and self.server:
            try:
                future = asyncio.run_coroutine_threadsafe(self._async_stop(), self.loop)
                future.result(timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Server stop timed out after 5 seconds")
            except Exception as e:
                logger.error(f"Error during stop: {e}", exc_info=True)
        
        # Wait for thread to finish
        self.quit()
        if not self.wait(3000):
            logger.warning("Thread didn't stop gracefully, terminating")
            self.terminate()
            self.wait(1000)  # Give it a moment after terminate

    async def _async_stop(self):
        try:
            if self.server:
                await self.server.stop()
        except Exception as e:
            logger.error(f"Error stopping: {e}")


class NetworkSelectionDialog(QDialog):
    """Initial network selection dialog"""
    
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.selected_network = None
        self.networks = self.get_networks()
        self.setup_ui()
        
    def get_networks(self):
        """Get available networks, filtering out virtual adapters"""
        all_networks = get_all_interfaces()
        networks = [iface for iface in all_networks 
                   if not ('Virtual' in iface['network_type'] or 
                          'WSL' in iface['network_type'] or
                          'Hyper-V' in iface['network_type'])]
        
        if not networks:
            networks = [{
                'interface': 'All',
                'friendly_name': 'All Interfaces',
                'ip': '0.0.0.0',
                'netmask': 'N/A',
                'network_type': '🌐 All Networks'
            }]
        
        return networks
    
    def setup_ui(self):
        self.setWindowTitle("Select Network Interface")
        self.setModal(True)
        self.setMinimumSize(550, 400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Title
        title = QLabel("🌐 Select Network Interface")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Choose the network interface for streaming.\n"
            "Your phone must be on the same network."
        )
        desc.setWordWrap(True)
        desc_font = QFont()
        desc_font.setPointSize(10)
        desc.setFont(desc_font)
        layout.addWidget(desc)
        
        layout.addSpacing(8)
        
        # Network options
        for net in self.networks:
            btn = QPushButton(
                f"📡 {net['friendly_name']}\n"
                f"IP: {net['ip']}\n"
                f"{net['network_type']}"
            )
            btn.setMinimumHeight(70)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=net: self.select_network(n))
            layout.addWidget(btn)
        
        layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
    
    def select_network(self, network):
        self.selected_network = network
        self.accept()


class SettingsDialog(QDialog):
    """Settings dialog with theme and port configuration"""
    
    def __init__(self, current_port, current_theme_mode, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.current_port = current_port
        self.current_theme_mode = current_theme_mode
        self.new_port = current_port
        self.new_theme_mode = current_theme_mode
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Title
        title_layout = QHBoxLayout()
        title = QLabel("⚙️ Server Settings")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # Theme section
        theme_label = QLabel("Appearance")
        theme_label_font = QFont()
        theme_label_font.setBold(True)
        theme_label_font.setPointSize(11)
        theme_label.setFont(theme_label_font)
        layout.addWidget(theme_label)
        
        theme_desc = QLabel("Choose your preferred color theme for the interface")
        layout.addWidget(theme_desc)
        
        # Theme buttons
        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(12)
        
        self.theme_group = QButtonGroup(self)
        
        # Auto theme
        auto_btn = QRadioButton("🌓 Auto\n(System)")
        auto_btn.setProperty('theme_mode', 'auto')
        if self.current_theme_mode == 'auto':
            auto_btn.setChecked(True)
        self.theme_group.addButton(auto_btn)
        theme_layout.addWidget(auto_btn)
        
        # Dark theme
        dark_btn = QRadioButton("🌙 Dark\n(Night)")
        dark_btn.setProperty('theme_mode', 'dark')
        if self.current_theme_mode == 'dark':
            dark_btn.setChecked(True)
        self.theme_group.addButton(dark_btn)
        theme_layout.addWidget(dark_btn)
        
        # Light theme
        light_btn = QRadioButton("☀️ Light\n(Day)")
        light_btn.setProperty('theme_mode', 'light')
        if self.current_theme_mode == 'light':
            light_btn.setChecked(True)
        self.theme_group.addButton(light_btn)
        theme_layout.addWidget(light_btn)
        
        layout.addLayout(theme_layout)
        
        layout.addSpacing(8)
        
        # Port section - issue is, it replaces the logo, and server needs to be restarted to apply so disable if running and warn
        # port_label = QLabel("Base Port Number")
        # port_label.setFont(theme_label_font)
        # layout.addWidget(port_label)
        
        # port_desc = QLabel(
        #     "Cameras will listen on sequential ports starting from this base port.\n"
        #     "Example: Base port 5000 → Cameras on 5000, 5001, 5002, 5003"
        # )
        # layout.addWidget(port_desc)
        
        # port_input_layout = QHBoxLayout()
        # self.port_spin = QSpinBox()
        # self.port_spin.setRange(2000, 65530)
        # self.port_spin.setValue(self.current_port)
        # self.port_spin.setMinimumWidth(150)
        # port_spin_font = QFont("Consolas")
        # port_spin_font.setPointSize(11)
        # self.port_spin.setFont(port_spin_font)
        # port_input_layout.addWidget(self.port_spin)
        
        # port_range_label = QLabel()
        # port_range_label.setText(f"Ports: {self.current_port} - {self.current_port + 3}")
        # self.port_spin.valueChanged.connect(
        #     lambda v: port_range_label.setText(f"Ports: {v} - {v + 3}")
        # )
        # port_input_layout.addWidget(port_range_label)
        # port_input_layout.addStretch()
        
        # layout.addLayout(port_input_layout)
        
        # layout.addSpacing(8)
        
        # Output protocol info
        output_label = QLabel("Output Protocol")
        output_label.setFont(theme_label_font)
        layout.addWidget(output_label)
        
        output_info = QFrame()
        output_info.setFrameStyle(QFrame.Shape.Box)
        output_layout = QHBoxLayout(output_info)
        output_icon = QLabel("🖥️")
        output_icon.setFont(QFont("Segoe UI Emoji", 16))
        output_layout.addWidget(output_icon)
        
        output_text = QLabel(
            "<b>OMT (vMix/OBS)</b><br>"
            "<small>Streams to vMix and OBS via OMT protocol</small>"
        )
        output_layout.addWidget(output_text)
        output_layout.addStretch()
        
        layout.addWidget(output_info)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
    
    def apply_settings(self):
        # self.new_port = self.port_spin.value()
        checked_btn = self.theme_group.checkedButton()
        if checked_btn:
            self.new_theme_mode = checked_btn.property('theme_mode')
        self.accept()


class CameraWidget(QWidget):
    """Camera display widget with preview and stats"""
    
    def __init__(self, cam_id, port, theme, parent=None):
        super().__init__(parent)
        self.cam_id = cam_id
        self.port = port
        self.theme = theme
        self.connected = False
        self.handler = None
        self.video_receiver = None
        self.frame_count = 0
        self.last_pixmap = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QFrame()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 12)
        
        self.name_label = QLabel(f"Camera {self.cam_id}")
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        h_layout.addWidget(self.name_label)
        h_layout.addStretch()
        
        self.status_label = QLabel("🔴 Disconnected")
        status_font = QFont()
        status_font.setBold(True)
        status_font.setPointSize(9)
        self.status_label.setFont(status_font)
        h_layout.addWidget(self.status_label)
        
        layout.addWidget(header)
        
        # Preview
        self.preview = QLabel()
        self.preview.setMinimumHeight(400)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setScaledContents(False)
        self.set_no_signal()
        
        layout.addWidget(self.preview)
        
        # Info bar
        info_bar = QFrame()
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(16, 10, 16, 10)
        
        self.info_label = QLabel(f"Port {self.port} • Waiting for connection")
        info_font = QFont()
        info_font.setPointSize(9)
        self.info_label.setFont(info_font)
        info_layout.addWidget(self.info_label)
        
        info_layout.addStretch()
        
        self.stats_label = QLabel("")
        self.stats_label.setFont(info_font)
        info_layout.addWidget(self.stats_label)
        
        layout.addWidget(info_bar)
    
    def set_no_signal(self):
        """Display no signal placeholder"""
        width, height = 640, 360
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img.fill(30)
        
        text = "No Signal"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 1.5, 2)[0]
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2
        cv2.putText(img, text, (text_x, text_y), font, 1.5, (80, 80, 80), 2)
        
        q_image = QImage(img.data, width, height, width * 3, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.preview.setPixmap(scaled)
    
    def set_connected(self, connected, info=None):
        """Update connection status"""
        try:
            self.connected = connected
            
            if connected:
                self.status_label.setText("🟢 Live")
                
                if info:
                    try:
                        self.update_info(info)
                    except Exception as e:
                        logger.error(f"Error updating info for camera {self.cam_id}: {e}")
                    
                    if 'handler' in info:
                        self.handler = info['handler']
                        # try:
                        #     self.start_video_receiver()
                        # except Exception as e:
                        #     logger.error(f"Error starting video receiver for camera {self.cam_id}: {e}")
            else:
                self.status_label.setText("🔴 Disconnected")
                self.info_label.setText(f"Port {self.port} • Waiting for connection")
                self.stats_label.setText("")
                
                # Stop video receiver safely
                try:
                    self.stop_video_receiver()
                except Exception as e:
                    logger.error(f"Error stopping video receiver for camera {self.cam_id}: {e}")

                # Clear handler reference
                self.handler = None
                self.frame_count = 0
                
                # Show no signal
                try:
                    self.set_no_signal()
                except Exception as e:
                    logger.error(f"Error setting no signal for camera {self.cam_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Critical error in set_connected for camera {self.cam_id}: {e}", exc_info=True)
    
    # def start_video_receiver(self):
    #     if self.video_receiver:
    #         self.stop_video_receiver()
        
    #     if self.handler:
    #         self.video_receiver = VideoFrameReceiver(self.cam_id, self.handler)
    #         self.video_receiver.frame_ready.connect(self.display_frame)
    #         self.video_receiver.start()
    
    def stop_video_receiver(self):
        if self.video_receiver:
            self.video_receiver.stop()
            self.video_receiver.wait(2000)
            self.video_receiver.deleteLater()  # Schedule for deletion
            self.video_receiver = None

        # Clear last pixmap
        if self.last_pixmap:
            del self.last_pixmap
            self.last_pixmap = None
    
    def display_frame(self, cam_id, frame):
        """Display incoming video frame from server thread"""
        if cam_id != self.cam_id:
            return
        
        try:
            self.frame_count += 1
            
            # Convert numpy array to QImage
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            
            pixmap = QPixmap.fromImage(q_image)
            scaled = pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Set new pixmap
            self.preview.setPixmap(scaled)
            
            # CRITICAL: Delete old pixmap to free memory
            if self.last_pixmap is not None:
                del self.last_pixmap
            
            self.last_pixmap = scaled
            
            # Update frame count in stats
            if self.handler:
                stats_parts = []
                # stats_parts.append(f"Frames: {self.frame_count}")
                
                if hasattr(self.handler, 'battery_percent') and self.handler.battery_percent >= 0:
                    battery_icon = "🔋" if self.handler.battery_percent > 20 else "🪫"
                    stats_parts.append(f"{battery_icon} {self.handler.battery_percent}%")
                
                if hasattr(self.handler, 'cpu_temperature_celsius') and self.handler.cpu_temperature_celsius > 0:
                    temp = self.handler.cpu_temperature_celsius
                    temp_icon = "❄️" if temp < 50 else "🌡️" if temp < 70 else "🔥"
                    stats_parts.append(f"{temp_icon} {temp:.1f}°C")
                
                if stats_parts:
                    self.stats_label.setText(" • ".join(stats_parts))

            # Explicitly delete to help garbage collector
            del pixmap
            del q_image
                    
        except Exception as e:
            logger.error(f"Error displaying frame for camera {self.cam_id}: {e}", exc_info=True)
    
    def update_info(self, info):
        parts = []
        if 'device_model' in info:
            parts.append(info['device_model'])
        if 'resolution' in info:
            parts.append(info['resolution'])
        
        if parts:
            self.info_label.setText(" • ".join(parts))
        
        stats_parts = []
        if 'battery' in info and info['battery'] >= 0:
            battery_icon = "🔋" if info['battery'] > 20 else "🪫"
            stats_parts.append(f"{battery_icon} {info['battery']}%")
        
        if 'temperature' in info and info['temperature'] > 0:
            temp = info['temperature']
            if temp < 50:
                temp_icon = "❄️"
            elif temp < 70:
                temp_icon = "🌡️"
            else:
                temp_icon = "🔥"
            stats_parts.append(f"{temp_icon} {temp:.1f}°C")
        
        if stats_parts:
            self.stats_label.setText(" • ".join(stats_parts))


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
        self.theme_btn.clicked.connect(self.cycle_theme)
        layout.addWidget(self.theme_btn)
        
        # Settings button
        settings_btn = QPushButton(" ⚙️ ")
        settings_btn.setFixedSize(60, 42)
        settings_btn.clicked.connect(self.show_settings)
        layout.addWidget(settings_btn)

        # About button
        about_btn = QPushButton(" ℹ️ ")
        about_btn.setFixedSize(60, 42)
        about_btn.clicked.connect(self.show_about)
        layout.addWidget(about_btn)
        
        # Start/Stop button
        self.toggle_btn = QPushButton("▶️ Start Server")
        self.toggle_btn.setFixedSize(142, 42)
        toggle_font = QFont()
        toggle_font.setBold(True)
        self.toggle_btn.setFont(toggle_font)
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
            © 2024 Vickerdent Corporation
            
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

def setup_logging():
    """
    Setup comprehensive logging to both file and console.
    Creates logs directory if it doesn't exist.
    """
    # Get logs directory (works in both dev and bundled)
    try:
        # For bundled app, write logs to user's AppData
        import os
        appdata = os.getenv('APPDATA')
        if not appdata:
            # Fallback: use temp directory next to the executable
            import tempfile
            appdata = tempfile.gettempdir()
        log_dir = Path(appdata) / 'VideoStreamerServer' / 'logs'
    except AttributeError:
        # For development, write to project directory
        log_dir = Path(__file__).resolve().parent / 'logs'
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create log filename with timestamp
    log_file = log_dir / f"video_streamer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,  # Capture everything
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler - detailed logging
            logging.FileHandler(log_file, encoding='utf-8'),
            # Console handler - important messages only
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set console handler to INFO level
    console_handler = logging.getLogger().handlers[-1]
    console_handler.setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 70)
    logger.info("Video Streamer Server Starting")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info("=" * 70)
    
    # Keep only last 10 log files
    cleanup_old_logs(log_dir, keep=10)
    
    return log_file

def cleanup_old_logs(log_dir: Path, keep: int = 10):
    """Delete old log files, keeping only the most recent ones."""
    try:
        log_files = sorted(log_dir.glob("video_streamer_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_log in log_files[keep:]:
            old_log.unlink()
            logging.debug(f"Deleted old log: {old_log.name}")
    except Exception as e:
        logging.warning(f"Could not cleanup old logs: {e}")

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    Global handler for uncaught exceptions.
    Logs the error and shows user-friendly dialog.
    """
    # Don't catch KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Format the exception
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    # Log it
    logger = logging.getLogger(__name__)
    logger.critical("Uncaught exception occurred!")
    logger.critical(error_msg)
    
    # Show user-friendly dialog
    try:
        show_crash_dialog(exc_type, exc_value, error_msg)
    except Exception:
        # If dialog fails, at least print to console
        print(f"CRITICAL ERROR: {error_msg}", file=sys.stderr)


def show_crash_dialog(exc_type, exc_value, error_msg):
    """Show crash dialog with error details and recovery options."""
    
    # Create minimal QApplication if needed
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle("Application Error")
    msg_box.setText(
        "An unexpected error occurred.\n\n"
        "The application may need to close."
    )
    
    # Simplified error for user
    user_error = f"{exc_type.__name__}: {str(exc_value)}"
    msg_box.setInformativeText(user_error)
    
    # Full traceback in details
    msg_box.setDetailedText(error_msg)
    
    # Add buttons
    msg_box.setStandardButtons(
        QMessageBox.StandardButton.Close | 
        QMessageBox.StandardButton.Ignore
    )
    msg_box.setDefaultButton(QMessageBox.StandardButton.Close)
    
    result = msg_box.exec()
    
    if result == QMessageBox.StandardButton.Close:
        sys.exit(1)

def main():
    # Step 1: Setup logging FIRST
    log_file = setup_logging()
    logger = logging.getLogger(__name__)
    
    # Step 2: Install global exception handler
    sys.excepthook = global_exception_handler
    
    try:
        # Step 3: Validate environment
        success, fallback_mode = validate_startup_environment()
        if not success:
            logger.critical("Startup validation failed, exiting")
            logger.critical(f"See log file for details: {log_file}")
            return 1
        
        # Step 4: Create QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("Video Streamer Server")
        app.setOrganizationName("Vickerdent Corporation")

        # Set default font
        font = QFont("Segoe UI", 10)
        app.setFont(font)
        
        # Step 5: Check for crash recovery
        last_state = CrashRecovery.load_last_state()
        restore_session = CrashRecovery.offer_recovery(last_state) if last_state else False
        
        # Step 6: Create main window
        window = MainWindow(fallback_mode, restore_session, last_state)
        window.setWindowIcon(QIcon(str(icon_path)) if icon_path.exists() else QIcon())
        window.show()
        
        # Step 7: Setup auto-save state (every 30 seconds)
        auto_save_timer = QTimer()
        auto_save_timer.timeout.connect(lambda: CrashRecovery.save_state({
            'start_port': window.start_port,
            'theme_mode': window.theme_mode,
            'network_ip': window.network['ip'] if window.network else None,
        }))
        auto_save_timer.start(30000)  # 30 seconds
        
        # Step 8: Run application
        logger.info("Application started successfully")
        exit_code = app.exec()
        
        # Step 9: Clean shutdown
        logger.info(f"Application exiting with code {exit_code}")
        CrashRecovery.save_state({})  # Clear state on clean exit
        
        return exit_code
        
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        logger.critical(f"See log file for details: {log_file}")
        return 1


if __name__ == '__main__':
    sys.exit(main())