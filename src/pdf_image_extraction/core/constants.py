"""Constants for PDF image extraction."""

# Extraction modes
EXTRACTION_MODES = {
    'safe': 'Safe mode - Extract only xreferred images',
    'normal': 'Normal mode - Extract with duplicate and corruption handling',
    'unsafe': 'Unsafe mode - Extract all images without warranty'
}

# Image size thresholds (in pixels)
MIN_IMAGE_WIDTH = 10
MIN_IMAGE_HEIGHT = 10

# Overlap detection parameters
OVERLAP_DISTANCE = 1.0
OVERLAP_DISTANCE_BBOX = 0.001

# Timeout for extraction (in seconds)
EXTRACTION_TIMEOUT = 600

# Default extraction output format
DEFAULT_IMAGE_FORMAT = 'PNG'

# Colorspace names
COLORSPACE_GRAY = 'DeviceGray'
COLORSPACE_RGB = 'DeviceRGB'
COLORSPACE_CMYK = 'DeviceCMYK'
