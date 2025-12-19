"""
Configuration management for development and production environments
"""
import sys
from pathlib import Path
import os

class Config:
    """Application configuration"""
    
    def __init__(self):
        # Detect if running in development mode
        self._is_development = self._detect_development()
        
        # API URLs
        if self._is_development:
            self.api_base_url = os.getenv('API_BASE_URL', "http://127.0.0.1:8000")  # Django dev server # type: ignore # Django dev server
        else:
            self.api_base_url = "https://vickerdentstudios.com"  # Production API
        
        # Update check endpoint
        self.update_check_url = f"{self.api_base_url}/vickerdent_api/check_update/"
        
        # Logging level
        self.log_level = "DEBUG" if self._is_development else "INFO"
    
    def _detect_development(self) -> bool:
        """
        Detect if running in development environment
        
        Returns True if DEBUG environment variable is set
        """
        # Method 1: Check if frozen (PyInstaller/cx_Freeze)
        if getattr(sys, 'frozen', False):
            # Running as compiled executable - check DEBUG override
            debug_env = os.getenv('DEBUG', '').lower()
            if debug_env in ('1', 'true', 'yes'):
                return True
            # Otherwise, it's production
            return False
        
        # Method 2: Check DEBUG environment variable (with default)
        debug_env = os.getenv('DEBUG', '').lower()
        if debug_env in ('1', 'true', 'yes'):
            return True
        
        # Method 3: Check if running from src directory
        try:
            current_file = Path(__file__).resolve()
            if 'src' in current_file.parts:
                return True
        except Exception:
            pass
        
        # Method 4: Check for .git directory (development repo)
        try:
            project_root = Path(__file__).resolve().parent.parent
            if (project_root / '.git').exists():
                return True
        except Exception:
            pass
        
        # Default to production if uncertain
        return False
    
    @property
    def is_development(self) -> bool:
        """Check if in development mode"""
        return self._is_development
    
    @property
    def is_production(self) -> bool:
        """Check if in production mode"""
        return not self._is_development

# Global config instance
config = Config()