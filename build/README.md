# Building VideoStreamerServer Executable

## Prerequisites

```bash
pip install pyinstaller
```

## Building

### From project root:
```bash
cd build
pyinstaller video_streamer_server.spec
```

### From build directory:
```bash
pyinstaller video_streamer_server.spec
```

## Output

The executable will be in:
```
build/dist/VideoStreamerServer/
├── VideoStreamerServer.exe
├── libraries/
│   ├── libomt.dll
│   └── libvmx.dll
├── assets/
│   ├── app_logo.png
│   └── app_logo.ico
└── [many other DLLs and files]
```

## Debugging

To see console output during debugging, edit the spec file:
```python
console=True,  # Change False to True
debug=True,    # Change False to True
```

Then rebuild:
```bash
pyinstaller --clean video_streamer_server.spec
```

## Clean Build

To completely rebuild from scratch:
```bash
pyinstaller --clean --noconfirm video_streamer_server.spec
```

## Common Issues

### DLL not found
- Ensure `libomt.dll` and `libvmx.dll` are in `src/libraries/`
- Check the spec file binaries section

### Missing icon
- Ensure `app_logo.ico` is in `src/assets/`
- Convert PNG to ICO if needed

### Import errors
- Add missing modules to `hiddenimports` in spec file