import logging
import requests
from packaging import version
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal

from constants import APP_VERSION, UPDATE_CHECK_URL, IS_DEVELOPMENT, APP_CODE

logger = logging.getLogger(__name__)

class UpdateCheckThread(QThread):
    """Background thread for checking updates"""
    update_available = pyqtSignal(str, str)  # latest_version, download_url
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.api_url = UPDATE_CHECK_URL

        if IS_DEVELOPMENT:
            logger.info(f"🔧 Development mode: Using API at {self.api_url}")
    
    def run(self):
        try:
            response = requests.get(
                self.api_url,
                timeout=10,
                params={
                    'app_code': APP_CODE,
                    'current_version': APP_VERSION,
                    'platform': 'windows'
                }
            )
            
            if response.status_code == 200:
                res = response.json()
                data = res.get('data')
                latest_version = data.get('latest_version')
                download_url = data.get('download_url')

                logger.info(f"Current: {APP_VERSION}, Latest: {latest_version}")
                
                if version.parse(latest_version) > version.parse(APP_VERSION):
                    self.update_available.emit(latest_version, download_url)
                else:
                    self.no_update.emit()
            else:
                logger.info(f"Current: {APP_VERSION}, Could not get it")
                self.error_occurred.emit(f"Server returned {response.status_code}")
                
        except requests.RequestException as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.error(f"Update check error: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


def show_update_dialog(parent, latest_version, download_url):
    """Show update available dialog"""
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.setWindowTitle("Update Available")
    msg_box.setText(f"Version {latest_version} is available!")
    msg_box.setInformativeText(
        f"You are currently running version {APP_VERSION}.\n"
        f"Would you like to download the update?"
    )
    msg_box.setStandardButtons(
        QMessageBox.StandardButton.Yes | 
        QMessageBox.StandardButton.No
    )
    
    if msg_box.exec() == QMessageBox.StandardButton.Yes:
        import webbrowser
        webbrowser.open(download_url)