# Build Configuration

This folder contains files needed to build Video Streamer Server from source code into a standalone executable.

## Files in This Folder

```
build/
├── video_streamer.spec       # PyInstaller build configuration
└── README.md                 # This file
```

---

## Building from Source

### Prerequisites

**Install Required Software:**

1. **Python 3.10 or higher**
   ```bash
   python --version
   # Should show Python 3.10 or higher
   ```

2. **Install Dependencies**
   ```bash
   pip install -r ../src/requirements.txt
   ```

3. **Install PyInstaller**
   ```bash
   pip install pyinstaller
   ```

4. **Get OMT Libraries**
   - See `../libraries/README.md` for instructions
   - Must have `libomt.dll` and `libvmx.dll` in `libraries/` folder

### Build Steps

**1. Navigate to Project Root**
```bash
cd video-streamer-server/
```

**2. Verify Structure**
```
video-streamer-server/
├── src/
│   ├── video_streamer_gui.py
│   ├── omt_bridge_tcp.py
│   └── network_diagnostics.py
├── libraries/
│   ├── libomt.dll     ← Must exist!
│   └── libvmx.dll     ← Must exist!
├── assets/
│   ├── app_logo.png
│   └── app_logo.ico
└── build/
    └── video_streamer.spec
```

**3. Build Executable**
```bash
pyinstaller build/video_streamer.spec
```

**4. Output Location**
```
dist/
└── VideoStreamerServer.exe    ← Your executable!
```

**5. Test the Build**
```bash
cd dist
VideoStreamerServer.exe
```

---

## Build Options

### One-File vs One-Folder

**Current Configuration: One-File** (single .exe)

To change to one-folder build, edit `video_streamer.spec`:

```python
# Find this section in the spec file:
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,      # Remove this line
    a.zipfiles,      # Remove this line
    a.datas,         # Remove this line
    [],
    # ... rest of config
    exclude_binaries=True,  # Add this line
)

# Add this section after EXE:
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VideoStreamerServer'
)
```

**One-File Pros:**
- ✅ Single executable
- ✅ Easier distribution
- ✅ Cleaner

**One-Folder Pros:**
- ✅ Faster startup
- ✅ Easier debugging
- ✅ Smaller individual files

### Debug Build

For debugging, enable console window:

Edit `video_streamer.spec`:
```python
exe = EXE(
    # ...
    console=True,  # Change from False to True
    # ...
)
```

This shows a console window with print statements and errors.

### Clean Build

Remove previous build artifacts:

```bash
# Windows
rmdir /s /q build dist
del *.spec

# Linux/Mac
rm -rf build dist *.spec
```

Then rebuild:
```bash
pyinstaller build/video_streamer.spec --clean
```

---

## Customization

### Change Application Name

Edit `video_streamer.spec`:
```python
exe = EXE(
    # ...
    name='MyCustomName',  # Change from 'VideoStreamerServer'
    # ...
)
```

### Change Icon

1. Place your icon file in `assets/` folder
2. Edit `video_streamer.spec`:
   ```python
   exe = EXE(
       # ...
       icon='assets/my_icon.ico',
       # ...
   )
   ```

### Add More Files

Edit `video_streamer.spec`:
```python
datas=[
    ('assets/app_logo.png', '.'),
    ('path/to/myfile.txt', '.'),      # Add this
    ('path/to/folder', 'folder_name'), # Or this
],
```

### Exclude Modules

To reduce file size, exclude unused modules:

Edit `video_streamer.spec`:
```python
excludes=[
    'tkinter',
    'matplotlib',
    'scipy',
    'pandas',
    'unittest',  # Add more here
],
```

---

## Troubleshooting Builds

### "Module not found" Error

**Problem:** PyInstaller can't find a module

**Solution:** Add to `hiddenimports` in spec file:
```python
hiddenimports=[
    'PyQt6.QtCore',
    'cv2',
    'missing_module',  # Add here
],
```

### "DLL not found" During Build

**Problem:** Can't find `libomt.dll` or `libvmx.dll`

**Solution:**
1. Verify DLLs exist in `libraries/` folder
2. Check path in spec file is correct:
   ```python
   binaries=[
       ('libraries/libomt.dll', 'libraries'),
       ('libraries/libvmx.dll', 'libraries'),
   ],
   ```

### Large Executable Size

**Problem:** .exe is >100 MB

**Solutions:**

1. **Enable UPX compression:**
   ```python
   exe = EXE(
       # ...
       upx=True,  # Make sure this is True
   )
   ```

2. **Exclude unused modules** (see Customization section)

3. **Use one-folder build** instead of one-file

4. **Analyze what's included:**
   ```bash
   pyinstaller --log-level=DEBUG build/video_streamer.spec 2>&1 | grep "Adding"
   ```

### Build Takes Too Long

**Problem:** Build takes 5+ minutes

**Normal:** First build is slow (5-10 minutes)

**For subsequent builds:**
```bash
pyinstaller build/video_streamer.spec --noconfirm
```

The `--noconfirm` flag skips confirmation prompts.

### Icon Not Showing

**Problem:** .exe has default Python icon

**Solutions:**

1. **Verify .ico file exists:**
   ```bash
   ls assets/app_logo.ico
   ```

2. **Convert PNG to ICO:**
   ```python
   from PIL import Image
   img = Image.open('assets/app_logo.png')
   img.save('assets/app_logo.ico', format='ICO', sizes=[(256, 256)])
   ```

3. **Check spec file path:**
   ```python
   icon='assets/app_logo.ico',  # Not .png!
   ```

---

## Build Optimization

### Best Practices

**For Distribution:**
```bash
# 1. Clean build
pyinstaller build/video_streamer.spec --clean

# 2. Test on clean VM
# Copy exe to Windows VM without Python
# Verify everything works

# 3. Sign executable (optional but recommended)
signtool sign /f cert.pfx /p PASSWORD /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist/VideoStreamerServer.exe

# 4. Create installer with Inno Setup
# Use installer/installer.iss
```

**For Development:**
```bash
# Fast builds with console output
pyinstaller build/video_streamer.spec --noconfirm
```
