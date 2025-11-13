"""
ImageEmbedded class for managing PDF embedded image metadata and state.

Author: Joao Phillipe Cardenuto - University of Campinas (UNICAMP)
"""

import fitz
from .constants import MIN_IMAGE_WIDTH, MIN_IMAGE_HEIGHT


class ImageEmbedded:
    """
    Manages all data from a PDF embedded image including metadata and processing state.
    
    This class organizes information about images extracted from PDF documents,
    including their location, colorspace, alpha channel information, and actual image data.
    """

    def __init__(self, xref=None, bbox=None, image_setting=None, width=None, height=None,
                 alt_colorspace=None, doc=None):
        """
        Initialize ImageEmbedded object.

        Parameters
        ----------
        xref : int, optional
            Cross-reference number of the image in the PDF.
        bbox : tuple, optional
            Bounding box coordinates (x0, y0, x1, y1) of the image in the PDF page.
        image_setting : dict, optional
            Dictionary containing image metadata from PDF extraction.
        width : int, optional
            Image width in pixels.
        height : int, optional
            Image height in pixels.
        alt_colorspace : str, optional
            Alternative colorspace name.
        doc : fitz.Document, optional
            PyMuPDF document object for image extraction.
        """
        if image_setting:
            self.xref = xref
            self.ext = image_setting["ext"]
            self.smask = image_setting['smask']
            self.colorspace = image_setting['colorspace']
            self.image = None
            
            # Get filter from xref object definition (PyMuPDF 1.26.6 compatible)
            try:
                xref_str = doc.xref_object(xref) if doc else ""
                configs = xref_str.split("/") if xref_str else []
                self.filter = configs[configs.index("Filter") + 1] if "Filter" in configs else None
            except:
                self.filter = None

            self.width = image_setting['width']
            self.height = image_setting['height']
            self.alt_colorspace = alt_colorspace
        else:
            self.xref = None
            self.ext = None
            self.smask = None
            self.colorspace = None
            self.image = None
            self.filter = None
            self.width = width
            self.height = height
            self.alt_colorspace = alt_colorspace

        # Set bounding box information
        if bbox:
            x0, y0, x1, y1 = bbox
            self.bbox = fitz.Rect(bbox)
            self.x0 = x0
            self.y0 = y0
            self.x1 = x1
            self.y1 = y1
        else:
            self.bbox = None

    def copy(self):
        """
        Create a copy of this ImageEmbedded object.

        Returns
        -------
        ImageEmbedded
            A new ImageEmbedded object with copied attributes (xref set to None).
        """
        copy_obj = ImageEmbedded(None, None)
        copy_obj.ext = self.ext
        copy_obj.smask = self.smask
        copy_obj.colorspace = self.colorspace
        copy_obj.image = self.image
        copy_obj.filter = self.filter
        copy_obj.width = self.width
        copy_obj.height = self.height
        copy_obj.alt_colorspace = self.alt_colorspace
        
        if self.bbox:
            copy_obj.bbox = fitz.Rect(self.bbox)
        
        return copy_obj

    def has_alpha(self):
        """
        Check if image has an alpha channel (stencil mask).

        Returns
        -------
        bool
            True if image has alpha/stencil mask, False otherwise.
        """
        return bool(self.smask)

    def is_valid_size(self):
        """
        Check if image dimensions are above minimum threshold.

        Returns
        -------
        bool
            True if both width and height exceed minimum thresholds.
        """
        if self.image:
            return self.image.size[0] >= MIN_IMAGE_WIDTH and self.image.size[1] >= MIN_IMAGE_HEIGHT
        return self.width >= MIN_IMAGE_WIDTH and self.height >= MIN_IMAGE_HEIGHT

    def __repr__(self):
        """String representation of ImageEmbedded object."""
        return (f"ImageEmbedded(xref={self.xref}, "
                f"size=({self.width}x{self.height}), "
                f"colorspace={self.colorspace}, "
                f"has_alpha={self.has_alpha()})")
