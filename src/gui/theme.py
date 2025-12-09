from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

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