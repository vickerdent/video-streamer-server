"""
OMT Bridge Server - LOW LATENCY VERSION with Audio Support
Receives H.264 video + AAC audio streams from Android phones and converts to OMT for vMix

Requirements:
    pip install av numpy

Also needs:
    - libomt.dll (Windows) or libomt.so (Linux)
    - libvmx.dll (Windows) or libvmx.so (Linux)
"""

import asyncio
import struct
import ctypes
import logging
import av
import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from collections import deque
import time
import sys
import argparse
import json
import netifaces

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Frame type constants (must match Android)
FRAME_TYPE_VIDEO = 0x01
FRAME_TYPE_AUDIO = 0x02
FRAME_TYPE_CONFIG = 0x03
FRAME_TYPE_METADATA = 0x04

# OMT Constants (from libomt.h)
class OMTFrameType(ctypes.c_int):
    Video = 2
    Audio = 4

class OMTCodec(ctypes.c_int):
    NV12 = 0x3231564E  # NV12 format
    FPA1 = 0x31415046   # Floating point planar audio ('FPA1')

class OMTQuality(ctypes.c_int):
    Default = 0
    Low = 1
    Medium = 50
    High = 100

class OMTColorSpace(ctypes.c_int):
    Undefined = 0
    BT601 = 601
    BT709 = 709

class OMTVideoFlags(ctypes.c_int):
    None_ = 0
    Interlaced = 1
    Alpha = 2

# Output abstraction layer
class FrameOutput:
    """Base class for frame output targets"""
    def send_video_frame(self, frame: np.ndarray, width: int, height: int, timestamp: int = -1) -> bool:
        raise NotImplementedError
    
    def send_audio_frame(self, audio_frame: av.AudioFrame) -> bool:
        raise NotImplementedError
    
    def destroy(self):
        pass

class NativeWindowsOutput(FrameOutput):
    """Output to native Windows camera/audio via VirtualCameraWrapper.exe"""
    
    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30, stream_id: int = 1):
        self.width = width
        self.height = height
        self.fps = fps
        self.stream_id = stream_id
        self.frame_count = 0
    
    def send_video_frame(self, frame: np.ndarray, width: int, height: int) -> bool:
        """Send NV12 frame to native Windows camera via wrapper"""
        # TODO: Implement TCP communication to VirtualCameraWrapper.exe
        # For now, return False to indicate no active connection
        # This will be properly implemented in Phase 2
        return False
    
    def send_audio_frame(self, audio_frame: av.AudioFrame) -> bool:
        """Send audio frame to native Windows audio via wrapper"""
        # TODO: Implement TCP communication to VirtualCameraWrapper.exe
        # For now, return False to indicate no active connection
        # This will be properly implemented in Phase 2
        return False
    
    def destroy(self):
        """Cleanup native camera resources"""
        pass


class OMTMediaFrame(ctypes.Structure):
    _fields_ = [
        ("Type", ctypes.c_int),
        ("Timestamp", ctypes.c_int64),
        ("Codec", ctypes.c_int),
        ("Width", ctypes.c_int),
        ("Height", ctypes.c_int),
        ("Stride", ctypes.c_int),
        ("Flags", ctypes.c_int),
        ("FrameRateN", ctypes.c_int),
        ("FrameRateD", ctypes.c_int),
        ("AspectRatio", ctypes.c_float),
        ("ColorSpace", ctypes.c_int),
        ("SampleRate", ctypes.c_int),
        ("Channels", ctypes.c_int),
        ("SamplesPerChannel", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("DataLength", ctypes.c_int),
        ("CompressedData", ctypes.c_void_p),
        ("CompressedLength", ctypes.c_int),
        ("FrameMetadata", ctypes.c_void_p),
        ("FrameMetadataLength", ctypes.c_int),
    ]

class OMTSender:
    """Wrapper for OMT sender"""
    
    def __init__(self, lib_path: str = "libomt.dll"):
        """Initialize OMT library"""
        # Add the directory containing libomt to the DLL search path
        lib_path_obj = Path(lib_path)

        # If relative path, make it absolute using resource path
        if not lib_path_obj.is_absolute():
            lib_path_obj = get_resource_path(str(lib_path_obj))
        
        lib_dir = str(lib_path_obj.parent)
        
        # On Windows, add to PATH so dependent DLLs (libvmx.dll, etc.) can be found
        import os
        if lib_dir not in os.environ.get('PATH', ''):
            os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
        
        # Load library with absolute path
        self.lib = ctypes.CDLL(lib_path_obj)
        
        # Define function signatures
        self.lib.omt_send_create.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.lib.omt_send_create.restype = ctypes.c_void_p
        
        self.lib.omt_send_destroy.argtypes = [ctypes.c_void_p]
        self.lib.omt_send_destroy.restype = None
        
        self.lib.omt_send.argtypes = [ctypes.c_void_p, ctypes.POINTER(OMTMediaFrame)]
        self.lib.omt_send.restype = ctypes.c_int
        
        self.lib.omt_send_connections.argtypes = [ctypes.c_void_p]
        self.lib.omt_send_connections.restype = ctypes.c_int
        
        self.lib.omt_send_getaddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.omt_send_getaddress.restype = ctypes.c_int
        
        self.sender = None
        logger.info(f"OMT library loaded from: {lib_path_obj}")
        logger.info(f"Library search path includes: {lib_dir}")
    
    def create_sender(self, name: str, quality: int = OMTQuality.Medium) -> bool:
        """Create an OMT sender"""
        try:
            self.sender = self.lib.omt_send_create(name.encode('utf-8'), quality)
            if self.sender:
                address_buf = ctypes.create_string_buffer(1024)
                self.lib.omt_send_getaddress(self.sender, address_buf, 1024)
                address = address_buf.value.decode('utf-8')
                logger.info(f"OMT Sender created: {address}")
                return True
            else:
                logger.error("Failed to create OMT sender")
                return False
        except Exception as e:
            logger.error(f"Error creating OMT sender: {e}")
            return False
    
    def send_video_frame(self, frame_data: np.ndarray, width: int, height: int, 
                    codec: int = OMTCodec.NV12, fps: int = 30, timestamp: int = -1) -> bool:
        """Send a video frame via OMT"""
        if not self.sender:
            return False
        
        try:
            # Ensure frame data is contiguous in memory for C library
            frame_data = np.ascontiguousarray(frame_data, dtype=np.uint8)
            
            omt_frame = OMTMediaFrame()
            omt_frame.Type = OMTFrameType.Video
            omt_frame.Codec = codec
            omt_frame.Width = width
            omt_frame.Height = height
            omt_frame.Stride = width  # For NV12 Y-plane, stride = width (1 byte per pixel)
            omt_frame.Flags = OMTVideoFlags.None_
            
            # Frame rate: numerator/denominator format (e.g., 30000/1000 = 30fps)
            omt_frame.FrameRateN = fps * 1000
            omt_frame.FrameRateD = 1000
            
            omt_frame.AspectRatio = 16.0 / 9.0
            omt_frame.ColorSpace = OMTColorSpace.BT709
            
            omt_frame.Timestamp = timestamp
            
            omt_frame.Data = frame_data.ctypes.data_as(ctypes.c_void_p)
            omt_frame.DataLength = frame_data.nbytes
            
            # Zero out compressed/metadata fields (C++ code does this explicitly)
            omt_frame.CompressedData = None
            omt_frame.CompressedLength = 0
            omt_frame.FrameMetadata = None
            omt_frame.FrameMetadataLength = 0
            
            result = self.lib.omt_send(self.sender, ctypes.byref(omt_frame))
            
            if result >= 0:
                # Success: result indicates bytes sent (or 0 if buffered)
                return True
            else:
                logger.warning(f"⚠️ OMT rejected frame (error code: {result})")
                return False
                
        except Exception as e:
            logger.error(f"Error sending video frame: {e}")
            return False
    
    def destroy(self):
        """Destroy OMT sender"""
        if self.sender:
            self.lib.omt_send_destroy(self.sender)
            self.sender = None
            logger.info("OMT Sender destroyed")

class OMTOutput(FrameOutput):
    """OMT output wrapper with dynamic reconfiguration"""
    
    def __init__(self, name: str, lib_path: str = "libomt.dll"):
        self.name = name
        self.lib_path = lib_path
        self.sender = OMTSender(lib_path)
        if not self.sender.create_sender(name, OMTQuality.Medium):
            raise RuntimeError("Failed to create OMT sender")
        
        # Track current configuration
        self.current_width = 1280
        self.current_height = 720
        self.current_fps = 30

        self.video_frame_count = 0
        self.audio_frame_count = 0

    def reconfigure(self, width: int, height: int, fps: int):
        """Recreate OMT sender with new resolution/fps"""
        if width == self.current_width and height == self.current_height and fps == self.current_fps:
            logger.debug(f"OMT config unchanged: {width}x{height}@{fps}fps")
            return True
        
        logger.info(f"🔄 Reconfiguring OMT sender: {self.current_width}x{self.current_height}@{self.current_fps}fps → {width}x{height}@{fps}fps")
        
        try:
            # Destroy old sender
            self.sender.destroy()
            
            # Create new sender with same name
            self.sender = OMTSender(self.lib_path)
            if not self.sender.create_sender(self.name, OMTQuality.Medium):
                logger.error("Failed to recreate OMT sender")
                return False
            
            # Update tracked config
            self.current_width = width
            self.current_height = height
            self.current_fps = fps

            # Reset frame counters
            self.video_frame_count = 0
            self.audio_frame_count = 0
            
            logger.info("✅ OMT sender reconfigured successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to reconfigure OMT: {e}")
            return False
    
    def send_video_frame(self, frame: np.ndarray, width: int, height: int, timestamp: int = -1) -> bool:
        """Send NV12 video frame to OMT"""
        # Use current_fps from our tracked config
        success = self.sender.send_video_frame(frame, width, height, OMTCodec.NV12, self.current_fps, timestamp)
        if success:
            self.video_frame_count += 1
        return success
    
    def send_audio_frame(self, audio_frame: av.AudioFrame) -> bool:
        """Send Floating Point Planar audio to OMT"""
        try:
            pcm_data = audio_frame.to_ndarray()
            num_channels = len(audio_frame.layout.channels)
            
            # DEBUG: Log actual shape on first frame
            if self.audio_frame_count == 0:
                logger.info(f"🔊 Audio shape: {pcm_data.shape}, dtype: {pcm_data.dtype}, layout: {audio_frame.layout.name}")
            
            # Ensure float32 format
            if pcm_data.dtype == np.int16:
                pcm_data = pcm_data.astype(np.float32) / 32768.0
            elif pcm_data.dtype == np.int32:
                pcm_data = pcm_data.astype(np.float32) / 2147483648.0
            elif pcm_data.dtype not in [np.float32, np.float64]:
                pcm_data = pcm_data.astype(np.float32)
            
            if pcm_data.dtype == np.float64:
                pcm_data = pcm_data.astype(np.float32)
            
            # CRITICAL FIX: OMT FPA1 expects PLANAR format [L,L,L...][R,R,R...]
            # PyAV already gives us (channels, samples) which IS planar - DON'T transpose!
            # Just flatten it directly to get [L,L,L...][R,R,R...] layout
            
            if len(pcm_data.shape) == 2:
                # Shape is (channels, samples_per_channel) - this is ALREADY planar!
                # Just flatten in C-order to get [ch0_samples][ch1_samples]
                logger.debug(f"Audio shape {pcm_data.shape} is already planar (channels, samples)")
                pcm_data = np.ascontiguousarray(pcm_data, dtype=np.float32).flatten('C')
            else:
                # If 1D, assume it's already interleaved and needs deinterleaving
                total_samples = len(pcm_data)
                samples_per_channel = total_samples // num_channels
                
                # Reshape to (samples, channels) then transpose to (channels, samples)
                pcm_data = pcm_data.reshape(samples_per_channel, num_channels).T
                pcm_data = np.ascontiguousarray(pcm_data, dtype=np.float32).flatten('C')
            
            # Calculate samples per channel
            total_samples = len(pcm_data)
            samples_per_channel = total_samples // num_channels
            
            # CRITICAL: Verify the math
            assert total_samples == samples_per_channel * num_channels, \
                f"Sample count mismatch: {total_samples} != {samples_per_channel} * {num_channels}"
            
            if self.audio_frame_count == 0:
                logger.info("🔊 Audio frame config (PLANAR format):")
                logger.info(f"   Total samples: {total_samples}")
                logger.info(f"   Samples per channel: {samples_per_channel}")
                logger.info(f"   Channels: {num_channels}")
                logger.info(f"   Data size: {pcm_data.nbytes} bytes")
                logger.info(f"   Sample rate: {audio_frame.sample_rate} Hz")
                logger.info("   Layout: [CH0 samples...][CH1 samples...]")
            
            omt_frame = OMTMediaFrame()
            omt_frame.Type = OMTFrameType.Audio
            omt_frame.SampleRate = audio_frame.sample_rate
            omt_frame.Channels = num_channels
            omt_frame.SamplesPerChannel = samples_per_channel
            omt_frame.Timestamp = -1  # Auto-increment
            
            omt_frame.Codec = OMTCodec.FPA1  # Floating Point Planar Audio
            
            omt_frame.Data = pcm_data.ctypes.data_as(ctypes.c_void_p)
            omt_frame.DataLength = pcm_data.nbytes
            
            # Zero out unused fields
            omt_frame.CompressedData = None
            omt_frame.CompressedLength = 0
            omt_frame.FrameMetadata = None
            omt_frame.FrameMetadataLength = 0
            
            result = self.sender.lib.omt_send(self.sender.sender, ctypes.byref(omt_frame))
            
            if result >= 0:
                self.audio_frame_count += 1
                return True
            else:
                logger.warning(f"⚠️ OMT audio rejected (error code: {result})")
                return False
        except Exception as e:
            logger.error(f"Error sending audio via OMT: {e}", exc_info=True)
            return False
    
    def destroy(self):
        """Cleanup OMT"""
        self.sender.destroy()

@dataclass
class StreamConfig:
    """Configuration for a phone stream"""
    phone_id: int
    port: int
    name: str
    width: int = 1280
    height: int = 720
    fps: int = 30
    video_bitrate: int = 4_000_000  # 4 Mbps
    audio_enabled: bool = False      # Whether audio is enabled
    audio_sample_rate: int = 48000  # Audio sample rate in Hz
    audio_channels: int = 2         # Number of audio channels
    audio_bitrate: int = 128_000    # Audio bitrate in bps
    device_model: str = "Unknown"
    battery_percent: int = -1
    cpu_temperature_celsius: float = -1.0

class PhoneStreamHandler:
    """Handles a single phone's H.264 + AAC stream"""
    
    def __init__(self, config: StreamConfig, output: FrameOutput):
        self.config = config
        self.output = output
        self.video_frame_signal = None  # To be set by GUI if needed
        self.video_decoder = None
        self.audio_decoder = None
        self.video_frame_count = 0
        self.audio_frame_count = 0
        self.running = False
        self.video_frame_pts = 0
        self.pts_increment = 90000 // config.fps

        self.last_frame_time = time.time()
        self.connection_timeout = 30.0  # Disconnect if no data for 30 seconds
        self.watchdog_task = None

        # Dynamic configuration (updated from client)
        self.current_width = config.width
        self.current_height = config.height
        self.current_fps = config.fps
        self.audio_enabled = config.audio_enabled

        # Device info
        self.device_model = "Unknown"
        self.battery_percent = -1
        self.cpu_temperature_celsius = -1.0
        
        # AAC configuration (populated from codec config)
        self.aac_sample_rate_index = 3  # 48000 Hz
        self.aac_channel_config = 2      # Stereo
        
        # Latency tracking
        self.latency_samples = deque(maxlen=30)
        self.average_latency = 0.0
        self.bytes_received = 0
        
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming connection from phone"""
        addr = writer.get_extra_info('peername')
        logger.info(f"📱 Phone {self.config.phone_id} connected from {addr[0]}:{addr[1]}")

        sock = writer.get_extra_info('socket')
        if sock:
            try:
                import socket
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)  # 256KB receive buffer
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # Disable Nagle
                logger.debug(f"Phone {self.config.phone_id}: Socket configured for low latency")
            except Exception as e:
                logger.warning(f"Could not configure socket: {e}")
        
        self.running = True
        self.last_frame_time = time.time()
        
        # Start connection watchdog
        self.watchdog_task = asyncio.create_task(self.connection_watchdog())
        
        try:
            # Wait for configuration packet FIRST
            config_received = await self.receive_config(reader)
            
            if config_received:
                # NEW: Reconfigure OMT sender with received settings
                if isinstance(self.output, OMTOutput):
                    success = self.output.reconfigure(
                        self.current_width,
                        self.current_height,
                        self.current_fps
                    )
                    if not success:
                        logger.error("❌ Failed to reconfigure OMT, using default settings")
            else:
                logger.warning(f"⚠️ Phone {self.config.phone_id}: No config received, using defaults")
            
            # Initialize decoders AFTER receiving config
            self.video_decoder = av.CodecContext.create('h264', 'r')
            self.video_decoder.thread_type = 'NONE'
            self.video_decoder.thread_count = 1

            # Ultra low latency options
            self.video_decoder.options = {
                'flags': 'low_delay',           # Enable low delay mode
                'flags2': 'fast',               # Fast decoding
                'fflags': 'nobuffer',           # Don't buffer frames
                'analyzeduration': '0',         # Don't analyze stream
                'probesize': '32',              # Minimal probe
                'sync': 'ext',                  # External sync
            }
            
            if self.audio_enabled:
                self.audio_decoder = av.CodecContext.create('aac', 'r')
                logger.info(f"🔊 Phone {self.config.phone_id}: Audio enabled")
            else:
                logger.info(f"🔇 Phone {self.config.phone_id}: Audio disabled")

            frames_received = 0
            video_frames_decoded = 0
            audio_frames_decoded = 0

             # Build status string with device info
            status_parts = [f"{self.device_model}", f"{self.current_width}x{self.current_height}@{self.current_fps}fps"]
            if self.battery_percent >= 0:
                status_parts.append(f"🔋{self.battery_percent}%")
            if self.cpu_temperature_celsius > 0:
                if self.cpu_temperature_celsius < 50:
                    temp_icon = "❄️"
                elif self.cpu_temperature_celsius < 70:
                    temp_icon = "🌡️"
                elif self.cpu_temperature_celsius < 85:
                    temp_icon = "🔥"
                else:
                    temp_icon = "💥"
                status_parts.append(f"{temp_icon}{self.cpu_temperature_celsius:.1f}°C")
            
            logger.info(f"⏳ Phone {self.config.phone_id}: Ready for streaming ({', '.join(status_parts)})")
            
            # Main streaming loop
            while self.running:
                # Update last frame time
                self.last_frame_time = time.time()

                # Read frame header
                try:
                    header = await asyncio.wait_for(
                        reader.readexactly(17),  # 1 byte type + 16 bytes header
                        timeout=10.0
                    )
                except asyncio.IncompleteReadError:
                    logger.info(f"📵 Phone {self.config.phone_id}: Connection ended")
                    break
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Phone {self.config.phone_id}: No data after 10s")
                    break
                except Exception as e:
                    logger.error(f"❌ Phone {self.config.phone_id}: Error reading header: {e}")
                    break
                
                # Unpack header with frame type
                try:
                    frame_type = header[0]
                    size, flags, timestamp = struct.unpack('>IIQ', header[1:])
                except struct.error as e:
                    logger.error(f"📦 Phone {self.config.phone_id}: Bad header. Error: {e}")
                    break
                
                # First frame notification
                if frames_received == 0:
                    frame_type_str = {
                        FRAME_TYPE_VIDEO: "Video",
                        FRAME_TYPE_AUDIO: "Audio",
                        FRAME_TYPE_CONFIG: "Config",
                        FRAME_TYPE_METADATA: "Metadata"
                    }.get(frame_type, f"Unknown(0x{frame_type:02x})")
                    logger.info(f"🎬 Phone {self.config.phone_id}: First frame! Type: {frame_type_str}")
                
                # Sanity check
                if size == 0 or size > 10_000_000:
                    logger.error(f"📦 Phone {self.config.phone_id}: Invalid frame size: {size} bytes")
                    break

                # Mark receive time for latency tracking
                receive_time = time.time()
                
                # Read frame data
                try:
                    data = await asyncio.wait_for(
                        reader.readexactly(size),
                        timeout=5.0
                    )
                except asyncio.IncompleteReadError as e:
                    logger.error(f"❌ Phone {self.config.phone_id}: Incomplete frame: {len(e.partial)}/{size} bytes")
                    break
                except asyncio.TimeoutError:
                    logger.error(f"⏰ Phone {self.config.phone_id}: Timeout reading {size} bytes")
                    break
                except Exception as e:
                    logger.error(f"❌ Phone {self.config.phone_id}: Error: {e}")
                    break
                
                frames_received += 1

                self.bytes_received += size
                self.average_latency = (self.average_latency * (frames_received - 1) + (time.time() - timestamp / 1_000_000_000)) / frames_received
                
                # Process based on frame type
                if frame_type == FRAME_TYPE_VIDEO:
                    decoded = await self.process_video_frame(data, flags, receive_time)
                    if decoded:
                        video_frames_decoded += 1
                elif frame_type == FRAME_TYPE_AUDIO and self.audio_enabled:
                    decoded = await self.process_audio_frame(data, flags, receive_time)
                    if decoded:
                        audio_frames_decoded += 1
                elif frame_type == FRAME_TYPE_METADATA and len(data) > 0:
                    try:
                        metadata = json.loads(data.decode('utf-8'))
                        if metadata.get('type') == 'misc':
                            self.battery_percent = metadata.get('batteryPercent', -1)
                            self.cpu_temperature_celsius = metadata.get('cpuTemperatureCelsius',
                                                                       metadata.get('temperatureCelsius', -1.0))
                            
                            # Log with appropriate icons
                            battery_icon = "🔋" if self.battery_percent > 20 else "🪫"
                            
                            if self.cpu_temperature_celsius > 0:
                                if self.cpu_temperature_celsius < 50:
                                    temp_icon = "❄️"
                                elif self.cpu_temperature_celsius < 70:
                                    temp_icon = "🌡️"
                                elif self.cpu_temperature_celsius < 85:
                                    temp_icon = "🔥"
                                else:
                                    temp_icon = "💥"
                            
                                logger.info(f"{battery_icon} Phone {self.config.phone_id}: Battery {self.battery_percent}%, {temp_icon} CPU {self.cpu_temperature_celsius:.1f}°C")
                            else:
                                logger.info(f"{battery_icon} Phone {self.config.phone_id}: Battery {self.battery_percent}%")
                    except Exception as e:
                        logger.warning(f"Failed to parse metadata: {e}")

                
                
                # Periodic logging (every 3 seconds)
                if frames_received % 90 == 0:
                    mb = self.bytes_received / 1_000_000
                    avg_latency = sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0
                    av_ratio = audio_frames_decoded / max(video_frames_decoded, 1)

                    logger.info(
                        f"📊 Phone {self.config.phone_id}: "
                        f"{video_frames_decoded}V/{audio_frames_decoded}A decoded (ratio: {av_ratio:.2f}), "
                        f"{mb:.2f} MB, {avg_latency*1000:.1f}ms latency"
                    )
                
        except Exception as e:
            logger.error(f"❌ Error handling Phone {self.config.phone_id}: {e}", exc_info=True)
        finally:
            self.running = False
            # Cancel watchdog
            if self.watchdog_task:
                self.watchdog_task.cancel()
                try:
                    await self.watchdog_task
                except asyncio.CancelledError:
                    pass

            writer.close()
            await writer.wait_closed()
            logger.info(f"📵 Phone {self.config.phone_id} disconnected")

    async def receive_config(self, reader: asyncio.StreamReader) -> bool:
        """Receive and parse initial configuration from client"""
        try:
            # Wait up to 5 seconds for config packet
            header = await asyncio.wait_for(reader.readexactly(5), timeout=5.0)
            
            frame_type = header[0]
            size = struct.unpack('>I', header[1:5])[0]
            
            if frame_type != FRAME_TYPE_CONFIG:
                logger.warning(f"⚠️ Expected config, got type {frame_type:02x}")
                return False
            
            # Read config JSON
            config_data = await asyncio.wait_for(reader.readexactly(size), timeout=2.0)
            config_json = json.loads(config_data.decode('utf-8'))
            
            # Parse configuration
            video_cfg = config_json.get('video', {})
            audio_cfg = config_json.get('audio', {})
            device_cfg = config_json.get('device', {})
            
            self.current_width = video_cfg.get('width', self.config.width)
            self.current_height = video_cfg.get('height', self.config.height)
            self.current_fps = video_cfg.get('fps', self.config.fps)
            video_bitrate = video_cfg.get('bitrate', 4_000_000)
            
            self.audio_enabled = audio_cfg.get('enabled', True)
            audio_sample_rate = audio_cfg.get('sampleRate', 48000)
            audio_channels = audio_cfg.get('channels', 2)
            audio_bitrate = audio_cfg.get('bitrate', 128000)

            self.device_model = device_cfg.get('model', 'Unknown')
            self.battery_percent = device_cfg.get('batteryPercent', -1)
            self.cpu_temperature_celsius = device_cfg.get('cpuTemperatureCelsius', -1.0)
            
            logger.info(f"📋 Phone {self.config.phone_id} Configuration:")
            logger.info(f"   📱 Device: {self.device_model}")
            logger.info(f"   📹 Video: {self.current_width}x{self.current_height}@{self.current_fps}fps, {video_bitrate/1_000_000:.1f}Mbps")
            logger.info(f"   🎤 Audio: {'Enabled' if self.audio_enabled else 'Disabled'}, {audio_sample_rate}Hz, {audio_channels}ch, {audio_bitrate/1000}kbps")

            if self.battery_percent >= 0:
                battery_icon = "🔋" if self.battery_percent > 20 else "🪫"
                logger.info(f"   {battery_icon} Battery: {self.battery_percent}%")
            
            # Display CPU temperature with appropriate icon
            if self.cpu_temperature_celsius > 0:
                if self.cpu_temperature_celsius < 50:
                    temp_icon = "❄️"   # Cool
                elif self.cpu_temperature_celsius < 70:
                    temp_icon = "🌡️"   # Normal
                elif self.cpu_temperature_celsius < 85:
                    temp_icon = "🔥"   # Hot
                else:
                    temp_icon = "💥"   # Very hot!
                logger.info(f"   {temp_icon} CPU Temperature: {self.cpu_temperature_celsius:.1f}°C")
            
            return True
            
        except asyncio.TimeoutError:
            logger.warning("⏰ Config packet timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Config parse error: {e}")
            return False
    
    async def process_video_frame(self, data: bytes, flags: int, receive_time: float) -> bool:
        """Decode H.264 and send to OMT"""
        try:
            # Check if codec config
            if flags & 0x2:  # BUFFER_FLAG_CODEC_CONFIG
                logger.info(f"🔧 Phone {self.config.phone_id}: Video codec config, size={len(data)}")
                packet = av.Packet(data)
                try:
                    list(self.video_decoder.decode(packet)) # type: ignore
                    logger.info(f"✅ Phone {self.config.phone_id}: Video codec configured")
                except Exception as e:
                    logger.warning(f"⚠️ Codec config decode warning: {e}")
                return False
            
            # Decode H.264
            packet = av.Packet(data)
            
            try:
                frames = list(self.video_decoder.decode(packet)) # type: ignore
            except (av.InvalidDataError, av.EOFError) as e:
                logger.debug(f"Video decode error: {e}")
                return False

            if not frames:
                return False
            
            for frame in frames:
                nv12_data = self.frame_to_nv12(frame)

                # Store for GUI access
                self._last_nv12_frame = nv12_data
                
                # Send to OMT IMMEDIATELY
                success = self.output.send_video_frame(
                    nv12_data,
                    self.current_width,
                    self.current_height,
                    self.video_frame_pts
                )
                
                if success:
                    self.video_frame_count += 1
                    self.video_frame_pts += self.pts_increment
                    
                    if self.video_frame_count == 1:
                        logger.info(f"✅ Phone {self.config.phone_id}: First video frame sent!")
            
            # Track latency
            end_time = time.time()
            latency = end_time - receive_time
            self.latency_samples.append(latency)
            
            return len(frames) > 0
        
        except Exception as e:
            logger.error(f"❌ Error processing video for Phone {self.config.phone_id}: {e}")
            return False
    
    async def process_audio_frame(self, data: bytes, flags: int, receive_time: float) -> bool:
        """Decode AAC and send to OMT"""
        try:
            # Check if codec config
            if flags & 0x2:  # BUFFER_FLAG_CODEC_CONFIG
                logger.info(f"🔧 Phone {self.config.phone_id}: Audio codec config, size={len(data)}, hex={data[:min(20, len(data))].hex()}")
                
                # Parse AAC config (AudioSpecificConfig)
                if len(data) >= 2:
                    self.aac_sample_rate_index = ((data[0] & 0x07) << 1) | ((data[1] >> 7) & 0x01)
                    self.aac_channel_config = (data[1] >> 3) & 0x0F
                    
                    sample_rates = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350]
                    sample_rate = sample_rates[self.aac_sample_rate_index] if self.aac_sample_rate_index < len(sample_rates) else 48000
                    
                    logger.info(f"✅ Phone {self.config.phone_id}: AAC config: {sample_rate}Hz, {self.aac_channel_config}ch (sr_idx={self.aac_sample_rate_index})")
                
                packet = av.Packet(data)
                try:
                    list(self.audio_decoder.decode(packet)) # type: ignore
                except Exception as e:
                    logger.warning(f"⚠️ Audio codec config warning: {e}")
                return False
            
            # Log first non-config audio frame
            if self.audio_frame_count == 0:
                logger.info(f"🎵 Phone {self.config.phone_id}: First audio data frame, size={len(data)}, flags={flags:04x}")
            
            # Add ADTS header to raw AAC frame
            aac_with_adts = self.add_adts_header(data)
            
            # Decode AAC
            packet = av.Packet(aac_with_adts)
            
            try:
                frames = list(self.audio_decoder.decode(packet)) # type: ignore
            except (av.InvalidDataError, av.EOFError) as e:
                if self.audio_frame_count == 0:
                    logger.error(f"❌ Audio decode error on first frame: {e}")
                return False

            if not frames:
                return False
            
            audio_frame = frames[0]
            
            if self.audio_frame_count == 0:
                logger.info(f"🔊 Decoded: {audio_frame.sample_rate}Hz, {audio_frame.layout.name}, {audio_frame.samples} samples, format={audio_frame.format.name}")
            
            # Send to OMT
            success = self.output.send_audio_frame(audio_frame)
            
            if success:
                self.audio_frame_count += 1
                if self.audio_frame_count == 1:
                    logger.info(f"✅ Phone {self.config.phone_id}: First audio frame sent to OMT!")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error processing audio for Phone {self.config.phone_id}: {e}")
            return False
    
    def frame_to_nv12(self, frame: av.VideoFrame) -> np.ndarray:
        """Convert AVFrame to NV12 format"""
        frame_yuv = frame.reformat(format='yuv420p')
        
        y_plane = np.frombuffer(frame_yuv.planes[0], dtype=np.uint8)
        u_plane = np.frombuffer(frame_yuv.planes[1], dtype=np.uint8)
        v_plane = np.frombuffer(frame_yuv.planes[2], dtype=np.uint8)

        height = self.config.height
        width = self.config.width
        
        y_data = y_plane.flatten()
        
        uv_data = np.empty(width * height // 2, dtype=np.uint8)
        uv_data[0::2] = u_plane.flatten()
        uv_data[1::2] = v_plane.flatten()
        
        nv12_data = np.concatenate([y_data, uv_data])
        
        return nv12_data
    
    def nv12_to_rgb(self, nv12_data, width, height):
        # Extract Y and UV planes
        y_size = width * height
        y_plane = nv12_data[:y_size].reshape(height, width)
        uv_plane = nv12_data[y_size:].reshape(height // 2, width)
        
        # Convert to RGB using OpenCV
        yuv = np.zeros((height * 3 // 2, width), dtype=np.uint8)
        yuv[:height, :] = y_plane
        yuv[height:, :] = uv_plane
        
        rgb = cv2.cvtColor(yuv, cv2.COLOR_YUV2RGB_NV12)
        return rgb
    
    def add_adts_header(self, aac_frame: bytes) -> bytes:
        """Add ADTS header to raw AAC frame"""
        frame_length = len(aac_frame) + 7  # 7 bytes for ADTS header
        
        # ADTS header (7 bytes)
        adts = bytearray(7)
        
        # Syncword (12 bits) = 0xFFF
        adts[0] = 0xFF
        adts[1] = 0xF1  # 0xF1 = MPEG-4, Layer 0, no CRC
        
        # Profile (2 bits) = AAC LC (1)
        # Sample rate index (4 bits)
        # Private bit (1 bit) = 0
        # Channel config (3 bits) - first bit
        adts[2] = ((1 << 6) |                              # Profile: AAC LC
                   (self.aac_sample_rate_index << 2) |     # Sample rate index
                   (self.aac_channel_config >> 2))         # Channel config (first bit)
        
        # Channel config (2 bits) - last 2 bits
        # Original/copy (1 bit) = 0
        # Home (1 bit) = 0
        # Copyright ID bit (1 bit) = 0
        # Copyright ID start (1 bit) = 0
        # Frame length (2 bits) - first 2 bits
        adts[3] = ((self.aac_channel_config & 0x3) << 6) | ((frame_length >> 11) & 0x3)
        
        # Frame length (8 bits) - middle 8 bits
        adts[4] = (frame_length >> 3) & 0xFF
        
        # Frame length (3 bits) - last 3 bits
        # Buffer fullness (5 bits)
        adts[5] = ((frame_length & 0x7) << 5) | 0x1F
        
        # Buffer fullness (6 bits)
        # Number of frames (2 bits) = 0 (1 frame)
        adts[6] = 0xFC
        
        return bytes(adts) + aac_frame
    
    async def connection_watchdog(self):
        """Monitor connection health and timeout if inactive"""
        try:
            while self.running:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                time_since_last_frame = time.time() - self.last_frame_time
                
                if time_since_last_frame > self.connection_timeout:
                    logger.warning(
                        f"📡 Phone {self.config.phone_id}: No data for {time_since_last_frame:.1f}s, "
                        f"disconnecting (timeout: {self.connection_timeout}s)"
                    )
                    self.running = False
                    break
                    
        except asyncio.CancelledError:
            logger.debug(f"Watchdog cancelled for phone {self.config.phone_id}")

class OMTBridgeServer:
    """Main server managing multiple phone streams"""
    
    def __init__(self, output_type: str = "omt", omt_lib_path: str = "libomt.dll", bind_ip: str | None = None):
        """
        Initialize bridge server
        
        Args:
            output_type: "omt" for vMix OMT protocol, "virtual" for virtual camera/mic
            omt_lib_path: Path to libomt.dll
            bind_ip: Specific IP to bind to (None = auto-detect)
        """
        self.output_type = output_type.lower()
        self.omt_lib_path = omt_lib_path
        self.bind_ip = bind_ip
        self.streams = {}
        self.servers = []
        self.outputs = {}  # Track all outputs for proper cleanup
        
        # Default configuration for 4 phones
        self.configs = [
            StreamConfig(1, 5000, "M-Camera 1", 1280, 720, 30),
            StreamConfig(2, 5001, "M-Camera 2", 1280, 720, 30),
            StreamConfig(3, 5002, "M-Camera 3", 1280, 720, 30),
            StreamConfig(4, 5003, "M-Camera 4", 1280, 720, 30),
        ]

    def get_local_ip_addresses(self):
        """Get all local IP addresses from all network interfaces"""
        ip_addresses = []
        
        try:
            # Get all network interfaces
            interfaces = netifaces.interfaces()
            
            for interface in interfaces:
                # Get addresses for this interface
                addrs = netifaces.ifaddresses(interface)
                
                # Check for IPv4 addresses
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        if ip and ip != '127.0.0.1':  # Skip loopback
                            # Get netmask if available
                            netmask = addr_info.get('netmask', '255.255.255.0')
                            ip_addresses.append({
                                'interface': interface,
                                'ip': ip,
                                'netmask': netmask
                            })
        except Exception as e:
            logger.warning(f"Error getting network interfaces: {e}")
        
        return ip_addresses
    
    def select_best_interface(self, ip_addresses):
        """Select the best IP address to bind to"""
        if not ip_addresses:
            return '0.0.0.0'  # Fallback to all interfaces
        
        # Prioritize non-virtual, non-VPN interfaces
        # Common patterns: "Ethernet", "Wi-Fi", "en0", "wlan0", "eth0"
        priority_patterns = ['ethernet', 'wi-fi', 'wlan', 'eth', 'en']
        
        for pattern in priority_patterns:
            for addr_info in ip_addresses:
                if pattern in addr_info['interface'].lower():
                    logger.info(f"Selected interface: {addr_info['interface']} ({addr_info['ip']})")
                    return addr_info['ip']
        
        # If no priority match, use first non-loopback
        if ip_addresses:
            logger.info(f"Using first available interface: {ip_addresses[0]['interface']} ({ip_addresses[0]['ip']})")
            return ip_addresses[0]['ip']
        
        return '0.0.0.0'
    
    async def start(self):
        """Start the bridge server"""
        logger.info("=" * 60)
        logger.info(f"🚀 Bridge Server Starting ({self.output_type.upper()})...")
        logger.info("=" * 60)

        # Determine which IP to bind to
        if self.bind_ip:
            bind_address = self.bind_ip
            logger.info(f"📡 Using specified bind address: {bind_address}")
        else:
            # Auto-detect network interfaces
            ip_addresses = self.get_local_ip_addresses()
            
            if ip_addresses:
                logger.info("📡 Available network interfaces:")
                for addr_info in ip_addresses:
                    logger.info(f"   - {addr_info['interface']}: {addr_info['ip']}/{addr_info['netmask']}")
                
                # Select best interface
                bind_address = self.select_best_interface(ip_addresses)
            else:
                logger.warning("⚠️ No network interfaces found, binding to all (0.0.0.0)")
                bind_address = '0.0.0.0'
        
        # Create servers for each phone
        for config in self.configs:
            try:
                # Create output based on selected type
                if self.output_type == "native":
                    output = NativeWindowsOutput(config.width, config.height, config.fps, config.phone_id)
                else:  # Default to OMT
                    output = OMTOutput(config.name, self.omt_lib_path)
                
                handler = PhoneStreamHandler(config, output)
                self.streams[config.phone_id] = handler
                self.outputs[config.phone_id] = output  # Track for cleanup
                
                # Bind to specific IP or all interfaces
                server = await asyncio.start_server(
                    handler.handle_client,
                    bind_address,  # Use selected IP instead of '0.0.0.0'
                    config.port,
                    reuse_address=True  # Allow quick restart
                )
                self.servers.append(server)
                
                # Get actual listening address
                addr = server.sockets[0].getsockname()
                logger.info(f"📱 Phone {config.phone_id} → {addr[0]}:{addr[1]}")
            except Exception as e:
                logger.error(f"❌ Failed to create output for Phone {config.phone_id}: {e}")
        
        logger.info("=" * 60)
        if self.output_type == "native":
            logger.info("✅ Bridge ready! Native Windows camera integration:")
            logger.info("   📹 Video: Connect VirtualCameraWrapper.exe on port 9999")
            logger.info("   🎤 Audio: Not yet implemented (Phase 2)")
            logger.info("")
            logger.info("   Usage: Start wrapper, then this bridge will send frames")
            logger.info("   Once running, cameras appear in Zoom, Teams, Meet, Discord, OBS, etc.")
        else:
            logger.info("✅ Bridge ready! Streaming to vMix via OMT protocol")
            logger.info("   Add OMT inputs to vMix: M-Camera 1, M-Camera 2, M-Camera 3, M-Camera 4")
        
        logger.info("")
        logger.info("📱 Connect your phone to these addresses:")
        if bind_address == '0.0.0.0':
            # Show all available IPs
            ip_addresses = self.get_local_ip_addresses()
            for addr_info in ip_addresses:
                logger.info(f"   - {addr_info['ip']} ({addr_info['interface']})")
        else:
            logger.info(f"   - {bind_address}")
        
        logger.info("=" * 60)
        
        try:
            await asyncio.gather(*[server.serve_forever() for server in self.servers])
        except KeyboardInterrupt:
            logger.info("\n👋 Shutting down...")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the server gracefully"""
        logger.info("\nStopping Bridge Server...")
        
        # Close all server sockets
        for server in self.servers:
            server.close()
            await server.wait_closed()
        
        # Cleanup all outputs and handlers
        for phone_id in list(self.streams.keys()):
            handler = self.streams[phone_id]
            handler.running = False  # Signal handler to stop
            
            # Give handler time to finish
            await asyncio.sleep(0.1)
        
        # Destroy all outputs (DirectShow or OMT)
        for phone_id, output in self.outputs.items():
            try:
                output.destroy()
            except Exception as e:
                logger.error(f"Error destroying output for Phone {phone_id}: {e}")
        
        logger.info("✅ Server stopped successfully")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Mobile Camera Bridge - OMT/Native Camera Streaming")
    parser.add_argument("--native-camera", action="store_true", help="Enable native Windows camera device")
    parser.add_argument("--omt", action="store_true", help="Use OMT protocol for vMix (default)")
    parser.add_argument("--bind-ip", type=str, help="Specific IP address to bind to (e.g., 192.168.1.100)")
    args = parser.parse_args()
    
    output_type = "native" if args.native_camera else "omt"
    
    if output_type == "omt":
        if sys.platform == "win32":
            lib_file = "libomt.dll"
        else:
            lib_file = "libomt.so"
        
        # Look for library in the libraries folder
        lib_path = get_resource_path(f"libraries/{lib_file}")
        
        if not lib_path.exists():
            logger.error(f"OMT library not found: {lib_path}")
            logger.error(f"Please ensure {lib_file} is in the libraries/ folder")
            return
        
        lib_path_full = str(lib_path)
    else:
        lib_path_full = ""
    
    server = OMTBridgeServer(
        output_type=output_type, 
        omt_lib_path=lib_path_full,
        bind_ip=args.bind_ip  # Allow specifying bind IP
    )
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")

if __name__ == "__main__":
    main()