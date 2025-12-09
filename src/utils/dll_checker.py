import sys
import ctypes
from pathlib import Path
import logging
from PyQt6.QtWidgets import (
    QMessageBox, QApplication
)

class DLLChecker:
    """Check for required DLLs before starting the application."""
    
    @staticmethod
    def check_dll_exists(dll_path: Path) -> bool:
        """Check if a DLL file exists."""
        return dll_path.exists() and dll_path.is_file()
    
    @staticmethod
    def check_dll_loadable(dll_path: Path) -> tuple[bool, str]:
        """
        Try to load a DLL and check for missing dependencies.
        
        Returns:
            (success: bool, error_message: str)
        """
        if not dll_path.exists():
            return False, f"File not found: {dll_path}"
        
        try:
            # Try to load the DLL
            _ = ctypes.CDLL(str(dll_path))
            return True, ""
        except OSError as e:
            error_str = str(e)
            
            # Parse Windows error codes
            if "0xc000007b" in error_str.lower():
                return False, "DLL architecture mismatch (32-bit vs 64-bit)"
            elif "0xc0000135" in error_str.lower():
                return False, "Missing dependency DLLs"
            elif "126" in error_str:  # ERROR_MOD_NOT_FOUND
                return False, "Dependent DLL not found"
            else:
                return False, f"Cannot load: {error_str}"
    
    @staticmethod
    def check_all_dependencies(base_path: Path) -> dict:
        """
        Check all required DLLs.
        
        Returns:
            Dictionary with check results
        """
        results = {
            'all_ok': True,
            'missing': [],
            'unloadable': [],
            'details': {}
        }
        
        # List of required DLLs
        required_dlls = [
            'libraries/libomt.dll',
            'libraries/libvmx.dll',
        ]
        
        logger = logging.getLogger(__name__)
        logger.info("Checking DLL dependencies...")
        
        for dll_rel_path in required_dlls:
            dll_path = base_path / dll_rel_path
            dll_name = Path(dll_rel_path).name
            
            # Check existence
            if not DLLChecker.check_dll_exists(dll_path):
                results['all_ok'] = False
                results['missing'].append(dll_name)
                results['details'][dll_name] = 'File not found'
                logger.error(f"❌ {dll_name}: NOT FOUND at {dll_path}")
                continue
            
            # Check if loadable
            loadable, error_msg = DLLChecker.check_dll_loadable(dll_path)
            if not loadable:
                results['all_ok'] = False
                results['unloadable'].append(dll_name)
                results['details'][dll_name] = error_msg
                logger.error(f"❌ {dll_name}: {error_msg}")
            else:
                results['details'][dll_name] = 'OK'
                logger.info(f"✅ {dll_name}: OK")
        
        return results
    
    @staticmethod
    def show_dll_error_dialog(check_results: dict):
        """Show detailed error dialog for DLL issues."""
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Missing Dependencies")
        
        # Build error message
        error_parts = []
        
        if check_results['missing']:
            error_parts.append("Missing DLL files:")
            for dll in check_results['missing']:
                error_parts.append(f"  • {dll}")
        
        if check_results['unloadable']:
            error_parts.append("\nDLLs with errors:")
            for dll in check_results['unloadable']:
                error = check_results['details'].get(dll, 'Unknown error')
                error_parts.append(f"  • {dll}: {error}")
        
        msg_box.setText("The application cannot start due to missing components.")
        msg_box.setInformativeText("\n".join(error_parts))
        
        # Add recovery suggestions
        suggestions = (
            "Possible solutions:\n\n"
            "1. Reinstall the application\n"
            "2. Install Visual C++ Redistributable:\n"
            "   https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
            "3. Check antivirus hasn't quarantined files\n"
            "4. Contact support@vickerdent.com for help"
        )
        msg_box.setDetailedText(suggestions)
        
        msg_box.setStandardButtons(QMessageBox.StandardButton.Close)
        msg_box.exec()