from PyQt6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QSpinBox, QWidget,
    QHBoxLayout, QFrame, QButtonGroup, QRadioButton, QCheckBox
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
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(cancel_btn)
    
    def select_network(self, network):
        self.selected_network = network
        self.accept()


class SettingsDialog(QDialog):
    """Settings dialog with theme and port configuration"""
    
    def __init__(self, current_port, current_theme_mode, theme, current_omt_quality, 
                 current_camera_count, server_running, auto_check_updates, test_network, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.current_port = current_port
        self.current_theme_mode = current_theme_mode
        self.current_omt_quality = current_omt_quality
        self.current_camera_count = current_camera_count
        self.server_running = server_running
        self.auto_check_updates = auto_check_updates

        self.new_port = current_port
        self.new_theme_mode = current_theme_mode
        self.new_omt_quality = current_omt_quality
        self.new_camera_count = current_camera_count
        self.test_network = test_network
        self.new_auto_check_updates = auto_check_updates
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumSize(650, 600)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title bar (fixed at top)
        title_bar = QFrame()
        title_bar.setFixedHeight(70)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(24, 16, 24, 16)
        
        title = QLabel("⚙️ Server Settings")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        main_layout.addWidget(title_bar)
        
        # Scrollable content area
        from PyQt6.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Content widget inside scroll area
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 16, 24, 16)
        
        # Font for section labels
        section_label_font = QFont()
        section_label_font.setBold(True)
        section_label_font.setPointSize(11)
        
        # ===================================================================
        # THEME SECTION
        # ===================================================================
        theme_label = QLabel("Appearance")
        theme_label.setFont(section_label_font)
        layout.addWidget(theme_label)
        
        theme_desc = QLabel("Choose your preferred color theme for the interface")
        layout.addWidget(theme_desc)
        
        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(12)
        
        self.theme_group = QButtonGroup(self)
        
        auto_btn = QRadioButton("🌓 Auto\n(System)")
        auto_btn.setMinimumHeight(50)
        auto_btn.setProperty('theme_mode', 'auto')
        if self.current_theme_mode == 'auto':
            auto_btn.setChecked(True)
        self.theme_group.addButton(auto_btn)
        theme_layout.addWidget(auto_btn)
        
        dark_btn = QRadioButton("🌙 Dark\n(Night)")
        dark_btn.setMinimumHeight(50)
        dark_btn.setProperty('theme_mode', 'dark')
        if self.current_theme_mode == 'dark':
            dark_btn.setChecked(True)
        self.theme_group.addButton(dark_btn)
        theme_layout.addWidget(dark_btn)
        
        light_btn = QRadioButton("☀️ Light\n(Day)")
        light_btn.setMinimumHeight(50)
        light_btn.setProperty('theme_mode', 'light')
        if self.current_theme_mode == 'light':
            light_btn.setChecked(True)
        self.theme_group.addButton(light_btn)
        theme_layout.addWidget(light_btn)
        
        layout.addLayout(theme_layout)
        
        # ===================================================================
        # OMT QUALITY SECTION
        # ===================================================================
        layout.addSpacing(8)
        
        quality_label = QLabel("OMT Stream Quality")
        quality_label.setFont(section_label_font)
        layout.addWidget(quality_label)
        
        quality_desc = QLabel("Higher quality increases bandwidth usage but improves video quality")
        layout.addWidget(quality_desc)
        
        quality_layout = QHBoxLayout()
        quality_layout.setSpacing(12)
        
        self.quality_group = QButtonGroup(self)
        
        low_btn = QRadioButton("⚡ Low\n(Faster)")
        low_btn.setMinimumHeight(50)
        low_btn.setProperty('quality', 'low')
        if self.current_omt_quality == 'low':
            low_btn.setChecked(True)
        self.quality_group.addButton(low_btn)
        quality_layout.addWidget(low_btn)
        
        medium_btn = QRadioButton("⚖️ Medium\n(Balanced)")
        medium_btn.setMinimumHeight(50)
        medium_btn.setProperty('quality', 'medium')
        if self.current_omt_quality == 'medium':
            medium_btn.setChecked(True)
        self.quality_group.addButton(medium_btn)
        quality_layout.addWidget(medium_btn)
        
        high_btn = QRadioButton("💎 High\n(Best)")
        high_btn.setMinimumHeight(50)
        high_btn.setProperty('quality', 'high')
        if self.current_omt_quality == 'high':
            high_btn.setChecked(True)
        self.quality_group.addButton(high_btn)
        quality_layout.addWidget(high_btn)
        
        layout.addLayout(quality_layout)
        
        # ===================================================================
        # CAMERA COUNT SECTION
        # ===================================================================
        layout.addSpacing(8)
        
        camera_count_label = QLabel("Number of Cameras")
        camera_count_label.setFont(section_label_font)
        layout.addWidget(camera_count_label)
        
        camera_desc = QLabel("Total number of phone connections to support (requires restart)")
        layout.addWidget(camera_desc)
        
        camera_count_layout = QHBoxLayout()
        camera_count_layout.setSpacing(16)
        
        camera_count_input_label = QLabel("Cameras:")
        camera_count_input_label.setMinimumWidth(80)
        camera_count_layout.addWidget(camera_count_input_label)
        
        self.camera_spin = QSpinBox()
        self.camera_spin.setRange(1, 8)
        self.camera_spin.setValue(self.current_camera_count)
        self.camera_spin.setMinimumWidth(100)
        self.camera_spin.setMaximumWidth(120)
        self.camera_spin.setMinimumHeight(36)
        self.camera_spin.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)
        self.camera_spin.setStyleSheet("""
            QSpinBox {
                padding: 6px 12px;
                font-size: 13px;
                font-family: 'Consolas', monospace;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 28px;
                height: 16px;
            }
        """)
        camera_count_layout.addWidget(self.camera_spin)
        camera_count_layout.addStretch()
        
        layout.addLayout(camera_count_layout)
        
        # ===================================================================
        # PORT CONFIGURATION SECTION
        # ===================================================================
        layout.addSpacing(8)
        
        port_label = QLabel("Port Configuration")
        port_label.setFont(section_label_font)
        layout.addWidget(port_label)
        
        port_desc = QLabel(
            "Set the starting port number for camera connections.\n"
            "Cameras will use sequential ports from this base number."
        )
        layout.addWidget(port_desc)
        
        # Warning if server is running
        if self.server_running:
            warning_frame = QFrame()
            warning_frame.setFrameStyle(QFrame.Shape.Box)
            warning_frame.setMinimumHeight(50)
            warning_frame.setStyleSheet(
                "background-color: rgba(255, 107, 107, 0.1); "
                "border: 1px solid #ff6b6b; "
                "border-radius: 4px; "
                "padding: 8px;"
            )
            warning_layout = QHBoxLayout(warning_frame)
            warning_layout.setContentsMargins(12, 8, 12, 8)
            
            warning_icon = QLabel("⚠️")
            warning_icon.setFont(QFont("Segoe UI Emoji", 16))
            warning_icon.setMinimumHeight(30)
            warning_layout.addWidget(warning_icon)
            
            warning_text = QLabel("Server is running. Stop the server before changing ports.")
            warning_text.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            warning_text.setWordWrap(True)
            warning_layout.addWidget(warning_text)
            warning_layout.addStretch()
            
            layout.addWidget(warning_frame)
        
        # Port configuration frame
        port_config_frame = QFrame()
        port_config_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        port_config_frame.setMinimumHeight(100)
        port_config_layout = QVBoxLayout(port_config_frame)
        port_config_layout.setSpacing(12)
        port_config_layout.setContentsMargins(12, 12, 12, 12)
        
        # Base port input
        base_port_layout = QHBoxLayout()
        base_port_layout.setSpacing(16)
        
        base_port_label = QLabel("Base Port:")
        base_port_label.setMinimumWidth(80)
        base_port_layout.addWidget(base_port_label)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(2000, 65530)
        self.port_spin.setValue(self.current_port)
        self.port_spin.setMinimumWidth(120)
        self.port_spin.setMaximumWidth(150)
        self.port_spin.setMinimumHeight(36)
        self.port_spin.setEnabled(not self.server_running)
        self.port_spin.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)
        self.port_spin.setStyleSheet("""
            QSpinBox {
                padding: 6px 12px;
                font-size: 13px;
                font-family: 'Consolas', monospace;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 28px;
                height: 16px;
            }
        """)
        base_port_layout.addWidget(self.port_spin)
        base_port_layout.addStretch()
        
        port_config_layout.addLayout(base_port_layout)
        
        # Port range display
        port_range_frame = QFrame()
        port_range_frame.setFrameStyle(QFrame.Shape.Box)
        port_range_frame.setMinimumHeight(60)
        port_range_layout = QHBoxLayout(port_range_frame)
        port_range_layout.setContentsMargins(12, 8, 12, 8)
        
        port_range_icon = QLabel("📡")
        port_range_icon.setFont(QFont("Segoe UI Emoji", 18))
        port_range_icon.setMinimumHeight(40)
        port_range_layout.addWidget(port_range_icon)
        
        self.port_range_label = QLabel()
        self.port_range_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.port_range_label.setMinimumHeight(40)
        self.port_range_label.setWordWrap(True)
        self.update_port_range_display(self.current_port, self.current_camera_count)
        port_range_layout.addWidget(self.port_range_label)
        port_range_layout.addStretch()
        
        port_config_layout.addWidget(port_range_frame)
        
        layout.addWidget(port_config_frame)
        
        # Connect signals
        self.port_spin.valueChanged.connect(
            lambda v: self.update_port_range_display(v, self.camera_spin.value())
        )
        self.camera_spin.valueChanged.connect(
            lambda v: self.update_port_range_display(self.port_spin.value(), v)
        )
        
        # ===================================================================
        # OUTPUT PROTOCOL SECTION
        # ===================================================================
        layout.addSpacing(8)
        
        output_label = QLabel("Output Protocol")
        output_label.setFont(section_label_font)
        layout.addWidget(output_label)
        
        output_info = QFrame()
        output_info.setFrameStyle(QFrame.Shape.Box)
        output_info.setMinimumHeight(60)
        output_layout = QHBoxLayout(output_info)
        output_layout.setContentsMargins(12, 8, 12, 8)
        
        output_icon = QLabel("🖥️")
        output_icon.setFont(QFont("Segoe UI Emoji", 18))
        output_icon.setMinimumHeight(40)
        output_layout.addWidget(output_icon)
        
        output_text = QLabel(
            "<b>OMT (vMix/OBS)</b><br>"
            "<small>Streams to vMix and OBS via OMT protocol</small>"
        )
        output_text.setMinimumHeight(40)
        output_layout.addWidget(output_text)
        output_layout.addStretch()
        
        layout.addWidget(output_info)
        
        # ===================================================================
        # AUTO-UPDATE SECTION
        # ===================================================================
        layout.addSpacing(8)
        
        update_label = QLabel("Updates")
        update_label.setFont(section_label_font)
        layout.addWidget(update_label)
        
        self.auto_update_checkbox = QCheckBox("Automatically check for updates on startup")
        self.auto_update_checkbox.setChecked(self.auto_check_updates)
        self.auto_update_checkbox.setMinimumHeight(32)
        layout.addWidget(self.auto_update_checkbox)
        
        # Add stretch at the end to push everything up
        layout.addStretch()
        
        # Set the content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # ===================================================================
        # BUTTON BAR (fixed at bottom)
        # ===================================================================
        button_bar = QFrame()
        button_bar.setFixedHeight(70)
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(24, 12, 24, 12)
        button_layout.addStretch()

        test_btn = QPushButton("Test Network")
        test_btn.setMinimumSize(110, 36)
        test_btn.clicked.connect(self.test_network)
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(test_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply Changes")
        apply_btn.setMinimumSize(120, 36)
        apply_btn.clicked.connect(self.apply_settings)
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_layout.addWidget(apply_btn)
        
        main_layout.addWidget(button_bar)

    def update_port_range_display(self, base_port, camera_count):
        """Update the port range display"""
        port_list = ", ".join(str(base_port + i) for i in range(min(camera_count, 4)))
        if camera_count > 4:
            port_list += f", ... {base_port + camera_count - 1}"
        
        self.port_range_label.setText(
            f"Camera ports: {port_list}\n"
            f"Range: {base_port} - {base_port + camera_count - 1}"
        )
    
    def apply_settings(self):
        checked_btn = self.theme_group.checkedButton()
        if checked_btn:
            self.new_theme_mode = checked_btn.property('theme_mode')

        quality_btn = self.quality_group.checkedButton()
        if quality_btn:
            self.new_omt_quality = quality_btn.property('quality')

        self.new_camera_count = self.camera_spin.value()

        if not self.server_running:
            self.new_port = self.port_spin.value()

        self.new_auto_check_updates = self.auto_update_checkbox.isChecked()

        self.accept()