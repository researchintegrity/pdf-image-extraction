"""
Service layer for PDF image extraction.

Provides a clean API for integration with Docker and other services.
"""

import os
from pdf_image_extraction.core import PDFExtractor


class ImageExtractorService:
    """
    Service wrapper for PDF image extraction.

    Provides a clean API for extracting images from PDFs with error handling.
    """

    def __init__(self, extraction_mode='normal'):
        """
        Initialize the service.

        Parameters
        ----------
        extraction_mode : str, optional
            Default extraction mode ('safe', 'normal', or 'unsafe').
            Default is 'normal'.
        """
        if extraction_mode not in ['safe', 'normal', 'unsafe']:
            raise ValueError(f"Invalid extraction_mode: {extraction_mode}")

        self.extraction_mode = extraction_mode

    def extract_images(self, pdf_path, output_folder, mode=None):
        """
        Extract images from a single PDF file.

        Parameters
        ----------
        pdf_path : str
            Path to the PDF file.
        output_folder : str
            Output folder where extracted images will be saved.
        mode : str, optional
            Override default extraction mode.

        Returns
        -------
        list
            List of extracted image file paths.

        Raises
        ------
        IOError
            If PDF file not found or output folder not accessible.
        ValueError
            If extraction mode is invalid.
        """
        if not os.path.isfile(pdf_path):
            raise IOError(f"PDF file not found: {pdf_path}")

        if not os.path.isdir(output_folder):
            raise IOError(f"Output folder not found: {output_folder}")

        extraction_mode = mode or self.extraction_mode

        try:
            # Extract PDF ID from filename
            pdf_id = os.path.basename(pdf_path).split('.')[0]

            # Create output subdirectory for this PDF
            pdf_output_dir = os.path.join(output_folder, pdf_id)

            # Perform extraction
            extractor = PDFExtractor(input_path=pdf_path)
            extractor.extract_all(out_name=output_folder, mode=extraction_mode)

            # Collect extracted images
            image_list = self._collect_images(pdf_output_dir)

            return image_list

        except Exception as e:
            raise IOError(f"Extraction failed for {pdf_path}: {str(e)}")

    def extract_images_batch(self, pdf_list, output_folder, mode=None):
        """
        Extract images from multiple PDF files.

        Parameters
        ----------
        pdf_list : list
            List of PDF file paths.
        output_folder : str
            Output folder where extracted images will be saved.
        mode : str, optional
            Override default extraction mode.

        Returns
        -------
        dict
            Dictionary mapping PDF paths to lists of extracted image paths.
        """
        results = {}

        for pdf_path in pdf_list:
            try:
                images = self.extract_images(pdf_path, output_folder, mode)
                results[pdf_path] = images
            except IOError as e:
                print(f"Error processing {pdf_path}: {e}")
                results[pdf_path] = []

        return results

    @staticmethod
    def _collect_images(output_dir):
        """
        Collect all extracted PNG images from output directory.

        Parameters
        ----------
        output_dir : str
            Directory containing extracted images.

        Returns
        -------
        list
            List of absolute paths to extracted images.
        """
        if not os.path.isdir(output_dir):
            return []

        images = []
        for filename in os.listdir(output_dir):
            if filename.lower().endswith('.png'):
                full_path = os.path.abspath(os.path.join(output_dir, filename))
                images.append(full_path)

        return sorted(images)
