# OMT Libraries

This folder should contain the required OMT (Open Media Transfer) protocol libraries for Video Streamer Server to function.

## ⚠️ Important: DLLs Not Included

**These DLL files are NOT included in this repository** due to licensing restrictions.

## Required Files

You need these two files in this folder:

```
libraries/
├── libomt.dll    (OMT protocol library)
└── libvmx.dll    (vMix communication library)
```

---

## How to Get the Libraries

### Option 1: From vMix Installation (Easiest)

If you have vMix installed:

1. Navigate to vMix installation folder:
   ```
   C:\Program Files (x86)\vMix\
   ```

2. Copy both files to this `libraries/` folder:
   - `libomt.dll`
   - `libvmx.dll`

### Option 2: From vMix Trial

1. Download vMix Trial from: https://www.vmix.com/software/download.aspx
2. Install vMix (trial is free)
3. Find DLLs in installation folder
4. Copy to this `libraries/` folder
5. You can uninstall vMix after copying if you don't need it

### Option 3: From Open Media Transport

1. Download Open Media Transport Releases: https://github.com/openmediatransport/libomtnet/releases
2. Extract the downloaded file
3. Find `libomt.dll` and `libvmx.dll` in the Libraries/Winx64 folder
4. Copy to this `libraries/` folder


---

## Verification

After copying the files, verify they're present:

### Check Files Exist

**Windows PowerShell:**
```powershell
ls libraries/

# Should show:
# libomt.dll
# libvmx.dll
```

**Command Prompt:**
```cmd
dir libraries\

# Should show both DLL files
```

### Verify File Sizes

Typical sizes (may vary by version):
- **libomt.dll**: 5 MB - 7 MB
- **libvmx.dll**: 400 KB - 1 MB

If files are much smaller or larger, they may be incorrect.

### Check File Hash (Optional)

```powershell
Get-FileHash libraries\libomt.dll -Algorithm SHA256
Get-FileHash libraries\libvmx.dll -Algorithm SHA256
```

Save these hashes for future verification.

---

## Troubleshooting

### "DLL not found" Error

**Problem:** Application says "libomt.dll not found"

**Solutions:**

1. **Verify files are in correct location:**
   ```
   video-streamer-server/
   └── libraries/
       ├── libomt.dll  ← Must be here
       └── libvmx.dll  ← Must be here
   ```

2. **Unblock files (Windows security):**
   - Right-click each DLL
   - Properties → General tab
   - Check "Unblock" if present
   - Click Apply → OK

3. **Install Visual C++ Redistributable:**
   - Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Install and restart PC
   - DLLs depend on these runtime libraries

### "Failed to load DLL" Error

**Problem:** DLL exists but won't load

**Possible causes:**

1. **Missing dependencies:**
   - DLLs require other system DLLs
   - Install Visual C++ Redistributable (see above)
   - Update Windows to latest version

2. **Corrupted file:**
   - Re-download from source
   - Verify file size is correct
   - Check antivirus didn't modify file

### Antivirus Blocks DLLs

**Problem:** Antivirus quarantines DLL files

**Solution:**
1. Add exception for `libraries/` folder
2. Add exception for `libomt.dll` and `libvmx.dll`
3. Restore from quarantine
4. Verify files exist again

---

## For Developers

### Building from Source

When building the executable with PyInstaller, the spec file automatically includes these DLLs:

```python
# From video_streamer.spec
binaries=[
    ('libraries/libomt.dll', 'libraries'),
    ('libraries/libvmx.dll', 'libraries'),
],
```

Make sure DLLs are present before running:
```bash
pyinstaller build/video_streamer.spec
```

### Using in Code

The application loads DLLs dynamically:

```python
import ctypes
from pathlib import Path

# Load library
lib_path = Path("libraries/libomt.dll")
omt_lib = ctypes.CDLL(str(lib_path))
```

For bundled executables, the path resolution is handled by `get_resource_path()`.

---

## License Information

**Important:** These libraries are free software as permissible by the MIT license included here: https://github.com/openmediatransport/libomtnet?tab=MIT-1-ov-file



## Need Help?

**For Video Streamer Server:**
- GitHub Issues: https://github.com/vickerdent/video-streamer-server/issues
- Email: support@vickerdent.com

---

## Quick Checklist

Before running or building:

- [ ] `libomt.dll` exists in `libraries/` folder
- [ ] `libvmx.dll` exists in `libraries/` folder
- [ ] Files are not blocked (check Properties)
- [ ] Visual C++ Redistributable installed
- [ ] Antivirus not blocking files
- [ ] Both DLLs are 64-bit versions

<!-- If all boxes checked and still having issues, see the [Troubleshooting Guide](../docs/troubleshooting.md). -->
