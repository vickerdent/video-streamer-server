"""
Application Constants and Configuration
Shared constants used across the application
"""

import sys
from pathlib import Path

# Import config
from config import config as app_config

# Application metadata
APP_VERSION = "2.0.1"
APP_NAME = "Video Streamer Server"
APP_CODE = "VSServer"
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

# API Configuration
API_BASE_URL = app_config.api_base_url
UPDATE_CHECK_URL = app_config.update_check_url
IS_DEVELOPMENT = app_config.is_development
