"""
PDF Image Extraction Package

A robust PDF figure extraction tool for scientific documents.
Supports multiple extraction modes (safe, normal, unsafe) with corruption handling.

Author: Joao Phillipe Cardenuto - University of Campinas (UNICAMP)
Email: phillipe.cardenuto@gmail.com
"""

__version__ = "1.0.0"

from .core.extractor import PDFExtractor
from .core.image_embedded import ImageEmbedded

__all__ = [
    "PDFExtractor",
    "ImageEmbedded",
]
