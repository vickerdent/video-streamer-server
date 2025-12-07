# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# Get the project directory
project_dir = Path.cwd()

# ============================================================================
# Analysis - Gather all Python files and dependencies
# ============================================================================

a = Analysis(
    # Main entry point
    ['video_streamer_gui.py'],
    
    # Additional search paths (if needed)
    pathex=[str(project_dir)],
    
    # Binary files (DLLs) to include
    # Format: (source_path, destination_folder_in_bundle)
    binaries=[
        (str(project_dir / 'libraries' / 'libomt.dll'), 'libraries'),
        (str(project_dir / 'libraries' / 'libvmx.dll'), 'libraries'),
    ],
    
    # Data files (non-Python files) to include
    # Format: (source_path, destination_folder_in_bundle)
    datas=[
        (str(project_dir / 'app_logo.png'), '.'),  # Logo in root of bundle
    ],
    
    # Hidden imports that PyInstaller might miss
    hiddenimports=[
        # Qt6 modules
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        
        # Video processing
        'av',
        'av.audio',
        'av.codec',
        'av.container',
        'av.frame',
        'av.packet',
        'cv2',
        
        # Numeric computing
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        
        # Network
        'netifaces',
        'asyncio',
        'socket',
        
        # Standard library (sometimes needed explicitly)
        'struct',
        'ctypes',
        'json',
        'logging',
        'traceback',
        'pathlib',
        'datetime',
    ],
    
    # Hook paths (custom PyInstaller hooks if needed)
    hookspath=[],
    
    # Hook configuration
    hooksconfig={},
    
    # Runtime hooks
    runtime_hooks=[],
    
    # Modules to exclude (reduces bundle size)
    excludes=[
        'tkinter',           # We use PyQt6, not tkinter
        'matplotlib',        # Not used
        'scipy',            # Not used
        'pandas',           # Not used
        'PIL',              # Not used (we use cv2)
        'PyQt5',            # We use PyQt6
        'PySide2',          # Not used
        'PySide6',          # Not used
        'wx',               # Not used
        'setuptools',       # Not needed at runtime
        'pip',              # Not needed at runtime
        'distutils',        # Not needed at runtime
    ],
    
    # Windows-specific options
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    
    # Encryption (leave as None for no encryption)
    cipher=block_cipher,
    
    # Don't create archive (False = faster startup, larger size)
    noarchive=False,
)

# ============================================================================
# PYZ - Create Python archive
# ============================================================================

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# ============================================================================
# EXE - Create executable
# ============================================================================

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,      # Include binaries in single exe
    a.zipfiles,
    a.datas,         # Include data files in single exe
    [],
    
    # Output filename
    name='VideoStreamerServer',
    
    # Debug options
    debug=False,                          # Set to True for debugging
    bootloader_ignore_signals=False,
    strip=False,                          # Don't strip symbols (for debugging)
    upx=True,                            # Compress with UPX (smaller size)
    upx_exclude=[],
    
    # Runtime temp directory
    runtime_tmpdir=None,
    
    # Console window
    console=False,                        # False = No console (GUI app only)
    # Set to True during development to see print statements
    
    # Windows-specific
    disable_windowed_traceback=False,
    target_arch=None,                     # None = current architecture
    codesign_identity=None,               # For code signing (add later)
    entitlements_file=None,               # For macOS (not used on Windows)
    
    # Application icon
    icon=str(project_dir / 'app_logo.ico'),  # ICO file for Windows
    
    # Version info (optional, for Windows properties)
    version='version_info.txt',
)