"""
OMT Bridge Server
Receives H.264 video + AAC audio streams from Android phones and converts to OMT for vMix

Requirements:
    pip install av numpy

Also needs:
    - libomt.dll (Windows) or libomt.so (Linux)
    - libvmx.dll (Windows) or libvmx.so (Linux)
"""

import asyncio
import logging
import sys
import argparse

from server.bridge import OMTBridgeServer
from constants import get_resource_path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Mobile Camera Bridge - OMT/Native Camera Streaming")
    parser.add_argument("--native-camera", action="store_true", help="Enable native Windows camera device")
    parser.add_argument("--omt", action="store_true", help="Use OMT protocol for vMix (default)")
    parser.add_argument("--bind-ip", type=str, help="Specific IP address to bind to (e.g., 192.168.1.100)")
    parser.add_argument("--camera-count", type=int, default=4, help="Number of cameras, up to 8 (e.g., 4)")
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

    from server.config import StreamConfig
    server.configs = []
    for i in range(int(args.camera_count)):
        config = StreamConfig(
            i + 1, 
            5000 + i,  # Default ports starting at 5000
            f"Camera {i + 1}", 
            1280, 720, 30
        )
        server.configs.append(config)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")

if __name__ == "__main__":
    main()