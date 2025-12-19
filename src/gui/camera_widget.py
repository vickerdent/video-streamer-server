import cv2
import numpy as np
import logging
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, 
    QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QImage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

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
        self.preview_paused = False
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

    def pause_preview(self):
        """Pause video preview updates to save resources"""
        self.preview_paused = True
        logger.debug(f"Camera {self.cam_id}: Preview paused")

    def resume_preview(self):
        """Resume video preview updates"""
        self.preview_paused = False
        logger.debug(f"Camera {self.cam_id}: Preview resumed")
    
    def display_frame(self, cam_id, frame):
        """Display incoming video frame from server thread"""
        if cam_id != self.cam_id:
            return
        
        # Skip frame processing if paused
        if self.preview_paused:
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