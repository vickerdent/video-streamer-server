import asyncio
import struct
import av
import cv2
import numpy as np
from collections import deque
import time
import json
import logging

from .config import StreamConfig
from .outputs import FrameOutput, OMTOutput
from omt.types import (
    FRAME_TYPE_AUDIO, FRAME_TYPE_VIDEO, FRAME_TYPE_CONFIG, FRAME_TYPE_METADATA
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

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

        self.writer = None
        self.reader = None
        self._force_stop = False
        self._disconnect_callback = None

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

        self.writer = writer
        self.reader = reader
        self._force_stop = False

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
                # Reconfigure OMT sender with received settings
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
            while self.running and not self._force_stop:
                # Update last frame time
                self.last_frame_time = time.time()

                # Read frame header
                try:
                    header = await asyncio.wait_for(
                        reader.readexactly(17),  # 1 byte type + 16 bytes header
                        timeout=10.0
                    )
                except asyncio.IncompleteReadError:
                    if self._force_stop:
                        logger.info(f"🛑 Phone {self.config.phone_id}: Server initiated disconnect")
                    else:
                        logger.info(f"📵 Phone {self.config.phone_id}: Connection ended (client disconnect)")
                    break
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Phone {self.config.phone_id}: No data after 10s")
                    break
                except asyncio.CancelledError:
                    logger.info(f"🛑 Phone {self.config.phone_id}: Connection cancelled by server")
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
                except asyncio.CancelledError:
                    logger.info(f"🛑 Phone {self.config.phone_id}: Read cancelled")
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

            # Check if force stopped
            if self._force_stop:
                logger.info(f"🛑 Phone {self.config.phone_id}: Force stopped by server shutdown")
            else:
                logger.info(f"📵 Phone {self.config.phone_id}: Normal disconnect")

        except asyncio.CancelledError:
            logger.info(f"🛑 Phone {self.config.phone_id}: Handler cancelled")
            raise
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

            # Properly close the connection
            try:
                if writer and not writer.is_closing():
                    writer.close()
                    await writer.wait_closed()
                    logger.debug(f"Phone {self.config.phone_id}: Connection closed")
            except Exception as e:
                logger.warning(f"Error closing writer for phone {self.config.phone_id}: {e}")

            # Call disconnect callback for GUI update
            if self._disconnect_callback:
                try:
                    self._disconnect_callback(self.config.phone_id)
                except Exception as e:
                    logger.error(f"Error in disconnect callback: {e}")
            
            # Clear references
            self.writer = None
            self.reader = None
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

    async def force_disconnect(self):
        """Force disconnect this client (called during server shutdown)"""
        logger.info(f"🔌 Force disconnecting phone {self.config.phone_id}...")
        
        self._force_stop = True
        self.running = False
        
        # Close writer to signal client
        if self.writer and not self.writer.is_closing():
            try:
                # Send a "server closing" notification if possible
                # (optional - client will detect connection close anyway)
                self.writer.close()
                await asyncio.wait_for(self.writer.wait_closed(), timeout=2.0)
                logger.debug(f"Phone {self.config.phone_id}: Connection closed gracefully")
            except asyncio.TimeoutError:
                logger.warning(f"Phone {self.config.phone_id}: Close timeout, forcing")
            except Exception as e:
                logger.warning(f"Phone {self.config.phone_id}: Error closing connection: {e}")