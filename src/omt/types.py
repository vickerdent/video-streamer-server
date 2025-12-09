import ctypes

# Frame type constants (must match Android)
FRAME_TYPE_VIDEO = 0x01
FRAME_TYPE_AUDIO = 0x02
FRAME_TYPE_CONFIG = 0x03
FRAME_TYPE_METADATA = 0x04

# OMT Constants (from libomt.h)
class OMTFrameType(ctypes.c_int):
    Video = 2
    Audio = 4

class OMTCodec(ctypes.c_int):
    NV12 = 0x3231564E  # NV12 format
    FPA1 = 0x31415046   # Floating point planar audio ('FPA1')

class OMTQuality(ctypes.c_int):
    Default = 0
    Low = 1
    Medium = 50
    High = 100

class OMTColorSpace(ctypes.c_int):
    Undefined = 0
    BT601 = 601
    BT709 = 709

class OMTVideoFlags(ctypes.c_int):
    None_ = 0
    Interlaced = 1
    Alpha = 2

class OMTMediaFrame(ctypes.Structure):
    _fields_ = [
        ("Type", ctypes.c_int),
        ("Timestamp", ctypes.c_int64),
        ("Codec", ctypes.c_int),
        ("Width", ctypes.c_int),
        ("Height", ctypes.c_int),
        ("Stride", ctypes.c_int),
        ("Flags", ctypes.c_int),
        ("FrameRateN", ctypes.c_int),
        ("FrameRateD", ctypes.c_int),
        ("AspectRatio", ctypes.c_float),
        ("ColorSpace", ctypes.c_int),
        ("SampleRate", ctypes.c_int),
        ("Channels", ctypes.c_int),
        ("SamplesPerChannel", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("DataLength", ctypes.c_int),
        ("CompressedData", ctypes.c_void_p),
        ("CompressedLength", ctypes.c_int),
        ("FrameMetadata", ctypes.c_void_p),
        ("FrameMetadataLength", ctypes.c_int),
    ]