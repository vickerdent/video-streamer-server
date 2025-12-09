import ctypes
import av
import numpy as np
import logging

from omt.sender import OMTSender
from omt.types import OMTCodec, OMTQuality, OMTMediaFrame, OMTFrameType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

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