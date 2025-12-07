# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-07

### Added
- Initial release
- Support for up to 4 simultaneous Android camera connections
- OMT protocol integration for vMix and OBS Studio
- H.264 video streaming with configurable resolution and bitrate
- AAC audio streaming with automatic synchronization
- Modern PyQt6 interface with live camera previews
- Automatic network interface detection
- Real-time device monitoring (battery, temperature, frame count)
- Dark and light theme support
- System tray integration
- Comprehensive error handling and logging
- Local-only operation with no external data transmission

### Known Issues
- Windows SmartScreen may show warnings (expected for new releases)
- High CPU usage with 4 cameras at 1080p (hardware decoding in development)

## [Unreleased]

### Planned
- Linux support
- macOS support
- NDI protocol support
- Virtual camera support