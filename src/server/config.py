from dataclasses import dataclass

@dataclass
class StreamConfig:
    """Configuration for a phone stream"""
    phone_id: int
    port: int
    name: str
    width: int = 1280
    height: int = 720
    fps: int = 30
    video_bitrate: int = 4_000_000  # 4 Mbps
    audio_enabled: bool = False      # Whether audio is enabled
    audio_sample_rate: int = 48000  # Audio sample rate in Hz
    audio_channels: int = 2         # Number of audio channels
    audio_bitrate: int = 128_000    # Audio bitrate in bps
    device_model: str = "Unknown"
    battery_percent: int = -1
    cpu_temperature_celsius: float = -1.0