from pathlib import Path
from PyQt6.QtWidgets import QMessageBox
from .dll_checker import DLLChecker

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