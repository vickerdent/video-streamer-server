# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# Get the project root directory (one level up from build/)
project_root = Path.cwd().parent if Path.cwd().name == 'build' else Path.cwd()
src_dir = project_root / 'src'

# ============================================================================
# Analysis - Gather all Python files and dependencies
# ============================================================================

a = Analysis(
    # Main entry point (relative to spec file location)
    [str(src_dir / 'vs_server_gui.py')],
    
    # Additional search paths
    pathex=[
        str(src_dir),           # Add src directory to Python path
        str(project_root),
    ],
    
    # Binary files (DLLs) to include
    # Format: (source_path, destination_folder_in_bundle)
    binaries=[
        (str(src_dir / 'libraries' / 'libomt.dll'), 'libraries'),
        (str(src_dir / 'libraries' / 'libvmx.dll'), 'libraries'),
    ],
    
    # Data files (non-Python files) to include
    # Format: (source_path, destination_folder_in_bundle)
    datas=[
        (str(src_dir / 'assets' / 'app_logo.png'), 'assets'),
        (str(src_dir / 'assets' / 'app_logo.ico'), 'assets'),
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
        
        # Your modules (main modules)
        'constants',
        'omt_bridge_tcp',
        'network_diagnostics',
        
        # GUI modules (if split)
        'gui',
        'gui.main_window',
        'gui.camera_widget',
        'gui.dialogs',
        'gui.theme',
        'gui.server_thread',
        
        # Server modules (if split)
        'server',
        'server.bridge',
        'server.handler',
        'server.config',
        'server.outputs',
        
        # OMT modules (if split)
        'omt',
        'omt.sender',
        'omt.types',
        
        # Utils modules (if split)
        'utils',
        'utils.fallback_mode',
        'utils.dll_checker',
        'utils.crash_recovery',
        
        # Standard library
        'struct',
        'ctypes',
        'json',
        'logging',
        'traceback',
        'pathlib',
        'datetime',
        'collections',
        'time',
        'dataclasses',
        'typing',
    ],
    
    # Hook paths (custom PyInstaller hooks if needed)
    hookspath=[],
    
    # Hook configuration
    hooksconfig={},
    
    # Runtime hooks
    runtime_hooks=[],
    
    # Modules to exclude (reduces bundle size)
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'PIL',
        'PyQt5',
        'PySide2',
        'PySide6',
        'wx',
        'setuptools',
        'pip',
        'distutils',
        'test',
        'unittest',
        'ipython',
        'jupyter',
    ],
    
    # Windows-specific options
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    
    # Encryption (leave as None for no encryption)
    cipher=block_cipher,
    
    # Don't create archive for debugging
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
# EXE - Create executable (ONE-FOLDER mode)
# ============================================================================

exe = EXE(
    pyz,
    a.scripts,
    [],                              # Empty - don't bundle everything in exe
    exclude_binaries=True,           # KEY: This creates one-folder bundle
    
    # Output filename
    name='VideoStreamerServer',
    
    # Debug options
    debug=False,                     # Set to True to see console during debugging
    bootloader_ignore_signals=False,
    strip=False,                     # Don't strip symbols (for debugging)
    upx=True,                        # Compress with UPX (smaller size)
    upx_exclude=[],
    
    # Runtime temp directory
    runtime_tmpdir=None,
    
    # Console window (set to True during development for debugging)
    console=False,                   # False = GUI-only, True = shows console
    
    # Windows-specific
    disable_windowed_traceback=False,
    target_arch=None,                # None = current architecture
    codesign_identity=None,          # For code signing (add later)
    entitlements_file=None,          # For macOS (not used on Windows)
    
    # Application icon
    icon=str(src_dir / 'assets' / 'app_logo.ico'),
)

# ============================================================================
# COLLECT - Gather all files into distribution folder
# ============================================================================

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VideoStreamerServer',      # Output folder name in dist/
)