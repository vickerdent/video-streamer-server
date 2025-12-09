from PyQt6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, 
    QHBoxLayout, QFrame, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# Import existing bridge components
from network_diagnostics import get_all_interfaces

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