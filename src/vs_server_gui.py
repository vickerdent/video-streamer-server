"""
Video Streamer Server - Complete PyQt6 Implementation
Modern GUI with theme switching, network selection, and comprehensive features

Install requirements:
    pip install PyQt6 opencv-python numpy pillow

Usage:
    python video_streamer_gui.py
"""

from datetime import datetime
import sys
import traceback
from pathlib import Path
import logging
from PyQt6.QtWidgets import (
    QMessageBox, QApplication
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QIcon

from gui.main_window import MainWindow
from utils.crash_recovery import CrashRecovery
from utils.dll_checker import DLLChecker
from utils.fallback_mode import FallbackMode

from constants import ICON_PATH as icon_path


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