from pathlib import Path
import logging
from PyQt6.QtWidgets import (
    QMessageBox
)

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