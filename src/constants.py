
"""
Application Constants and Configuration
Shared constants used across the application
"""
from pathlib import Path
import sys

# Application metadata
APP_VERSION = "1.0.1"
APP_NAME = "Video Streamer Server"
ORGANIZATION_NAME = "Vickerdent Corporation"

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
        base_path = Path(sys._MEIPASS)  # type: ignore
    except AttributeError:
        # Running in normal Python environment
        base_path = Path(__file__).resolve().parent
    
    resource_path = base_path / relative_path
    return resource_path

# Pre-compute commonly used paths
ICON_PATH = get_resource_path("assets/app_logo.png")
ICON_ICO_PATH = get_resource_path("assets/app_logo.ico")
LIBOMT_DLL_PATH = get_resource_path("libraries/libomt.dll")
LIBVMX_DLL_PATH = get_resource_path("libraries/libvmx.dll")