import numpy as np
import ctypes
from pathlib import Path
import logging

from omt.types import (
    OMTMediaFrame, OMTFrameType, OMTCodec, OMTQuality, OMTVideoFlags, OMTColorSpace
)
from constants import get_resource_path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

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