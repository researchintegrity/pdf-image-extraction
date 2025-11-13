"""
Main PDF image extraction module.

This module provides the PDFExtractor class for extracting images from PDF documents
with support for multiple extraction modes (safe, normal, unsafe).

Requires: PyMuPDF >= 1.26.6
  - Supports Python 3.10-3.14
  - Uses MuPDF 1.26.11 for improved performance and bug fixes

Author: Joao Phillipe Cardenuto - University of Campinas (UNICAMP)
Email: phillipe.cardenuto@gmail.com
"""

import os
from glob import glob
import signal
import shutil
import io

import numpy as np
import fitz
from PIL import Image, ImageOps, ImageChops

from .image_embedded import ImageEmbedded
from .constants import (
    EXTRACTION_MODES, MIN_IMAGE_WIDTH, MIN_IMAGE_HEIGHT,
    OVERLAP_DISTANCE, OVERLAP_DISTANCE_BBOX, EXTRACTION_TIMEOUT,
    COLORSPACE_GRAY, COLORSPACE_RGB, COLORSPACE_CMYK
)


def handler_timeout(signum, frame):
    """Signal handler for extraction timeout."""
    raise TimeoutError("TIMEOUT!")


def get_rectangles_points(bbox):
    """Get corner points of a bounding box rectangle."""
    p0 = fitz.Point(bbox.x0, bbox.y0)
    p1 = fitz.Point(bbox.x1, bbox.y0)
    p2 = fitz.Point(bbox.x0, bbox.y1)
    p3 = fitz.Point(bbox.x1, bbox.y1)
    return p0, p1, p2, p3


def check_overlap(bboxi, bboxj, distance=OVERLAP_DISTANCE, distance_bbox=OVERLAP_DISTANCE_BBOX):
    """
    Check if there is overlapping between two bounding boxes.

    Parameters
    ----------
    bboxi : fitz.Rect
        First bounding box.
    bboxj : fitz.Rect
        Second bounding box.
    distance : float, optional
        Acceptable coordinate distance for overlap detection.
    distance_bbox : float, optional
        Acceptable bounding box distance for overlap detection.

    Returns
    -------
    bool
        True if bounding boxes overlap, False otherwise.
    """
    p0, p1, p2, p3 = get_rectangles_points(bboxi)
    q0, q1, q2, q3 = get_rectangles_points(bboxj)

    # Check if boxes are at the same location
    if (p0.distance_to(q0) == 0 and p1.distance_to(q1) == 0 and
            p2.distance_to(q2) == 0 and p3.distance_to(q3) == 0):
        return False

    # Check containment
    if bboxi in bboxj or bboxj in bboxi:
        return True

    # Check edge proximities
    if (p1.distance_to(q0) < distance and p3.distance_to(q2) < distance):
        return True
    if (p0.distance_to(q1) < distance and p2.distance_to(q3) < distance):
        return True
    if (p0.distance_to(q2) < distance and p1.distance_to(q3) < distance):
        return True
    if (p2.distance_to(q0) < distance and p3.distance_to(q1) < distance):
        return True

    # Check bbox distances
    if (p1.distance_to(bboxj) < distance_bbox and p3.distance_to(bboxj) < distance_bbox and
            (p1.distance_to(q0) < distance_bbox or p3.distance_to(q2) < distance_bbox)):
        return True
    if (p0.distance_to(bboxj) < distance_bbox and p2.distance_to(bboxj) < distance_bbox and
            (p0.distance_to(q1) < distance_bbox or p2.distance_to(q3) < distance_bbox)):
        return True
    if (p0.distance_to(bboxj) < distance_bbox and p1.distance_to(bboxj) < distance_bbox and
            (p0.distance_to(q2) < distance_bbox or p1.distance_to(q3) < distance_bbox)):
        return True
    if (p2.distance_to(bboxj) < distance_bbox and p3.distance_to(bboxj) < distance_bbox and
            (p2.distance_to(q0) < distance_bbox or p3.distance_to(q1) < distance_bbox)):
        return True

    return False


class PDFExtractor:
    """
    Extracts images from PDF documents using PyMuPDF (fitz).

    Supports three operation modes:
    - safe: Extract only xreferred images (most conservative)
    - normal: Extract with duplicate detection and corruption handling (recommended)
    - unsafe: Extract all images without xref warranty (not recommended)

    The extractor can handle corrupted PDFs and provides image size filtering.
    """

    operations_mode = list(EXTRACTION_MODES.keys())

    def __init__(self, input_path='.'):
        """
        Initialize PDFExtractor with input PDF path(s).

        Parameters
        ----------
        input_path : str or list
            Path to PDF file, directory containing PDFs, or list of PDF paths.

        Raises
        ------
        IOError
            If input path is invalid or not accessible.
        """
        self.input_path = None
        self.pdf_files = []
        self.img_counter = 0
        self.doc = None

        # Handle list input
        if isinstance(input_path, list):
            self.pdf_files = []
            self.input_path = []
            if len(input_path) > 1:
                for pdf in input_path:
                    if pdf.lower().endswith(".pdf"):
                        if "/" in pdf:
                            self.pdf_files.append(pdf[pdf.rfind("/") + 1:])
                            self.input_path.append(pdf[:pdf.rfind("/")])
                        else:
                            self.pdf_files.append(pdf)
                            self.input_path.append(".")
                    else:
                        print(f"{pdf} is not in *.PDF format")
            else:
                input_path = input_path[0]

        # Handle string input
        if isinstance(input_path, str):
            if input_path.lower().endswith(".pdf"):
                self.pdf_files = []
                self.input_path = []
                if "/" in input_path:
                    self.pdf_files.append(input_path[input_path.rfind("/") + 1:])
                    self.input_path.append(input_path[:input_path.rfind("/")])
                else:
                    self.pdf_files.append(input_path)
                    self.input_path.append(".")
            else:
                self.input_path = input_path
                self.pdf_files = self.get_local_pdf()

        if self.input_path is None:
            raise IOError(f"Input Path {input_path} error")

    def get_local_pdf(self, input_path=None):
        """
        Get all PDF files from a directory.

        Parameters
        ----------
        input_path : str, optional
            Directory path. If None, uses instance input_path.

        Returns
        -------
        list
            Sorted list of PDF filenames in the directory.
        """
        if input_path is None:
            input_path = self.input_path
        
        pdf_files = []
        for filename in os.listdir(input_path):
            if filename.lower().endswith(".pdf"):
                pdf_files.append(filename)
        
        pdf_files.sort(key=str.lower)
        return pdf_files

    def extract_all(self, input_path=None, out_name='.', mode='normal'):
        """
        Extract all images from all PDFs.

        Parameters
        ----------
        input_path : str or list, optional
            Override instance input_path.
        out_name : str, optional
            Output directory for extracted images. Default is current directory.
        mode : str, optional
            Extraction mode ('safe', 'normal', or 'unsafe'). Default is 'normal'.

        Raises
        ------
        ValueError
            If mode is not valid.
        IOError
            If output path is not a directory.
        """
        if mode not in self.operations_mode:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {self.operations_mode}")

        if isinstance(out_name, list):
            out_name = out_name[0]

        if not os.path.isdir(out_name):
            raise IOError(f"Output {out_name} is not a directory")

        if input_path is None:
            input_path = self.input_path

        if mode == 'normal':
            self._extract_all_normal(input_path, out_name)
        elif mode == 'safe':
            self._extract_all_safe(input_path, out_name)
        else:  # unsafe
            self._extract_all_unsafe(input_path, out_name)

        print("Extraction Done!")

    def _extract_all_normal(self, input_path, out_name):
        """Extract all PDFs using normal mode with timeout handling."""
        for index, pdf in enumerate(self.pdf_files):
            in_path = input_path[index] if isinstance(input_path, list) else input_path
            print(f"Processing: {pdf}")

            try:
                signal.signal(signal.SIGALRM, handler_timeout)
                signal.alarm(EXTRACTION_TIMEOUT)
                self.normal_mode(dir_path=f"{out_name}/{pdf[:-4]}", pdf=f"{in_path}/{pdf}")
            except KeyboardInterrupt:
                signal.alarm(0)
                raise
            except TimeoutError:
                try:
                    print(f"{pdf} is taking too much time. Trying safe mode...")
                    if os.path.isdir(f"{out_name}/{pdf[:-4]}"):
                        shutil.rmtree(f"{out_name}/{pdf[:-4]}")
                    self.safe_mode(dir_path=f"{out_name}/{pdf[:-4]}", pdf=f"{in_path}/{pdf}")
                except Exception:
                    if os.path.isdir(f"{out_name}/{pdf[:-4]}"):
                        shutil.rmtree(f"{out_name}/{pdf[:-4]}")
                    print(f"Can't complete extraction of {pdf}")
            except Exception:
                try:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, handler_timeout)
                    signal.alarm(EXTRACTION_TIMEOUT)
                    print(f"{pdf} can't be extracted with normal mode. Trying safe mode...")
                    if os.path.isdir(f"{out_name}/{pdf[:-4]}"):
                        shutil.rmtree(f"{out_name}/{pdf[:-4]}")
                    self.safe_mode(dir_path=f"{out_name}/{pdf[:-4]}", pdf=f"{in_path}/{pdf}")
                except Exception:
                    if os.path.isdir(f"{out_name}/{pdf[:-4]}"):
                        shutil.rmtree(f"{out_name}/{pdf[:-4]}")
                    print(f"Can't complete extraction of {pdf}")
            finally:
                signal.alarm(0)
                self.posprocessing_extraction(dir_path=f"{out_name}/{pdf[:-4]}")

    def _extract_all_safe(self, input_path, out_name):
        """Extract all PDFs using safe mode."""
        for index, pdf in enumerate(self.pdf_files):
            in_path = input_path[index] if isinstance(input_path, list) else input_path
            print(f"Processing: {pdf}")

            try:
                self.safe_mode(dir_path=f"{out_name}/{pdf[:-4]}", pdf=f"{in_path}/{pdf}")
            except Exception as e:
                print(f"Can't complete extraction of {pdf} using safe mode: {e}")
                raise

    def _extract_all_unsafe(self, input_path, out_name):
        """Extract all PDFs using unsafe mode."""
        for index, pdf in enumerate(self.pdf_files):
            in_path = input_path[index] if isinstance(input_path, list) else input_path
            print(f"Processing: {pdf}")

            try:
                self.unsafe_mode(dir_path=f"{out_name}/{pdf[:-4]}", pdf=f"{in_path}/{pdf}")
            except Exception as e:
                print(f"Can't extract using unsafe mode: {e}")
                raise

    def is_single_color(self, img_path):
        """
        Check if image contains only a single color.

        Parameters
        ----------
        img_path : str
            Path to image file.

        Returns
        -------
        bool
            True if image is single color, False otherwise.
        """
        img = Image.open(img_path)
        extrema = img.getextrema()

        if len(extrema) >= 3:
            return all(band_extrema[0] == band_extrema[1] for band_extrema in extrema)
        else:
            return extrema[0] == extrema[1]

    def is_equal_imgs(self, img_path_i, img_path_j):
        """
        Check if two images are equal or if one should be deleted.

        Parameters
        ----------
        img_path_i : str
            Path to first image.
        img_path_j : str
            Path to second image.

        Returns
        -------
        tuple
            (bool, str or None) - (are_equal, path_to_delete)
        """
        img_i = Image.open(img_path_i)
        img_j = Image.open(img_path_j)

        if img_i.size != img_j.size:
            return False, None

        img_i.load()
        img_j.load()

        if img_i.mode != img_j.mode:
            if img_j.mode == 'L':
                return True, img_path_j
            if img_i.mode == 'L':
                return True, img_path_i

        if img_i.mode == img_j.mode:
            if img_i.mode == 'L':
                last = sorted([img_path_i, img_path_j],
                            key=lambda x: int(x[x.rfind("-"):-4]), reverse=True)
                return True, last[1]
            else:
                if ImageChops.difference(img_i, img_j).getbbox() is None:
                    return True, img_path_i

        return False, None

    def isclose_infos(self, img_i, img_j):
        """Check if two image info tuples are close in coordinates."""
        return all(np.isclose(img_i[i], img_j[i]) for i in range(5))

    def posprocessing_extraction(self, dir_path):
        """
        Eliminate duplicate and single-color images from extraction.

        Parameters
        ----------
        dir_path : str
            Path to directory containing extracted images.
        """
        if not os.path.isdir(dir_path):
            return

        imgs_names = glob(f"{dir_path}/*.png")
        imgs_names.sort(key=lambda x: int(x[x.rfind("-"):-4]), reverse=True)

        # Parse image info from filenames
        imgs_infos = [
            (int(img[img.find("/p-") + 3:img.find("-x0-")]),
             float(img[img.find("-x0-") + 4:img.find("-y0-")]),
             float(img[img.find("-y0-") + 4:img.find("-x1-")]),
             float(img[img.find("-x1-") + 4:img.find("-y1-")]),
             float(img[img.find("-y1-") + 4:img.rfind("-")]),
             index)
            for index, img in enumerate(imgs_names)
        ]

        while imgs_infos:
            img_i = imgs_infos.pop(0)

            # Remove single-color images
            if self.is_single_color(imgs_names[img_i[5]]):
                os.remove(imgs_names[img_i[5]])
                continue

            # Check for duplicates
            for index, img_j in enumerate(imgs_infos):
                if self.isclose_infos(img_i, img_j):
                    delete, delete_image_name = self.is_equal_imgs(
                        imgs_names[img_i[5]], imgs_names[img_j[5]]
                    )
                    if delete:
                        if delete_image_name == imgs_names[img_j[5]]:
                            imgs_infos[index] = img_i
                        os.remove(delete_image_name)
                        break

    def unsafe_mode(self, pdf, dir_path=None):
        """
        Extract all images from PDF without xref warranty (unsafe mode).

        Parameters
        ----------
        pdf : str
            Path to PDF file.
        dir_path : str, optional
            Output directory path.
        """
        self.img_counter = 1
        extraction_path = dir_path or self.input_path

        if not os.path.exists(extraction_path):
            os.mkdir(extraction_path)

        self.doc = fitz.open(pdf)

        try:
            for page in range(len(self.doc)):
                page_contents = self.doc[page].get_text("dict")
                all_image_from_page = [t for t in page_contents['blocks'] if t['type'] == 1]

                for img_data in all_image_from_page:
                    img = Image.open(io.BytesIO(img_data['image']))
                    img.load()

                    if img.width < MIN_IMAGE_WIDTH or img.height < MIN_IMAGE_HEIGHT:
                        continue

                    name = f"{extraction_path}/p-{page + 1}-{self.img_counter}.png"
                    
                    # Convert CMYK to RGB
                    if img.mode == 'CMYK':
                        img = img.convert('RGB')
                    # Handle RGBA images with white background
                    elif img.mode == 'RGBA':
                        white_bg = Image.new('RGB', img.size, (255, 255, 255))
                        white_bg.paste(img, mask=img.split()[3])
                        img = white_bg
                    # Convert other modes to RGB if needed
                    elif img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    
                    # Save without compression to preserve raw image data
                    img.save(name, compress_level=0)
                    self.img_counter += 1
        finally:
            self.doc.close()

    def safe_mode(self, pdf, dir_path=None):
        """
        Extract only xreferred images from PDF (safe mode).

        Parameters
        ----------
        pdf : str
            Path to PDF file.
        dir_path : str, optional
            Output directory path.
        """
        self.img_counter = 1
        extraction_path = dir_path or self.input_path

        if not os.path.exists(extraction_path):
            os.mkdir(extraction_path)

        self.doc = fitz.open(pdf)
        xrefs_checked = []

        try:
            for page in range(len(self.doc)):
                for img in self.doc[page].get_images(full=True):
                    xref = img[0]

                    if xref in xrefs_checked:
                        continue

                    smask = img[1]

                    if smask != 0:  # Has stencil mask
                        pix1 = fitz.Pixmap(self.doc, xref)
                        
                        # Convert CMYK to RGB if needed BEFORE adding alpha
                        if pix1.colorspace and pix1.colorspace.name == COLORSPACE_CMYK:
                            pix1 = fitz.Pixmap(fitz.csRGB, pix1)
                        
                        pix2 = fitz.Pixmap(self.doc, smask)
                        pix = fitz.Pixmap(pix1)
                        pix.set_alpha(pix2.samples)

                        if self.write_img(pix, f"{extraction_path}/p-{page + 1}-{self.img_counter}.png"):
                            self.img_counter += 1
                            xrefs_checked.append(xref)

                        pix = pix1 = pix2 = None
                    else:  # No stencil mask
                        pix = fitz.Pixmap(self.doc, xref)

                        if self.write_img(pix, f"{extraction_path}/p-{page + 1}-{self.img_counter}.png", img[5]):
                            self.img_counter += 1
                            xrefs_checked.append(xref)

                        pix = None
        finally:
            self.doc.close()

    def normal_mode(self, pdf, dir_path=None):
        """
        Extract images with duplicate and corruption detection (normal mode).

        This is the recommended mode for robust extraction.

        Parameters
        ----------
        pdf : str
            Path to PDF file.
        dir_path : str, optional
            Output directory path.
        """
        self.img_counter = 1
        extraction_path = dir_path or self.input_path

        if not os.path.exists(extraction_path):
            os.mkdir(extraction_path)

        self.doc = fitz.open(pdf)
        xrefs_checked = []

        try:
            for page in range(len(self.doc)):
                page_contents = self.doc[page].get_text("dict")
                all_image_from_page = [t for t in page_contents['blocks'] if t['type'] == 1]
                xreferred_image_list = []

                # Build list of xreferred images
                for img in self.doc[page].get_images(full=True):
                    xref = img[0]
                    extract_img = self.doc.extract_image(xref)

                    if xref in xrefs_checked:
                        continue

                    # Handle images with alpha
                    if extract_img["smask"] > 0:
                        self._handle_alpha_image(page, xref, extract_img, img, all_image_from_page,
                                               xreferred_image_list, xrefs_checked, extraction_path)
                        continue

                    pix = fitz.Pixmap(self.doc, xref)
                    if pix.colorspace is None:
                        continue

                    # Match extracted image with page content
                    self._match_page_content(page, xref, extract_img, img, all_image_from_page,
                                            xreferred_image_list, xrefs_checked)

                # Process unmatched images
                if not xreferred_image_list and all_image_from_page:
                    self._process_unmatched_images(page, all_image_from_page, xrefs_checked,
                                                  xreferred_image_list)

                # Handle overlapping images
                if len(xreferred_image_list) > 1:
                    self._handle_overlapping_images(page, xreferred_image_list, extraction_path)
                elif xreferred_image_list:
                    self._save_single_image(page, xreferred_image_list[0], extraction_path)

        except KeyboardInterrupt:
            self.doc.close()
            raise
        except Exception:
            self.doc.close()
            print("NORMAL MODE FAILS")
            raise

    def _handle_alpha_image(self, page, xref, extract_img, img, all_image_from_page,
                           xreferred_image_list, xrefs_checked, extraction_path):
        """Handle images with alpha channels."""
        pix_img = fitz.Pixmap(self.doc, xref)

        if pix_img.colorspace and pix_img.colorspace.name == COLORSPACE_CMYK:
            pix_img = fitz.Pixmap(fitz.csRGB, pix_img)

        aux_img = pix_img.tobytes('png')
        pix_img = None
        found = False

        for p_img in all_image_from_page:
            if p_img['image'] == aux_img:
                xreferred_image_list.append(
                    ImageEmbedded(xref, p_img['bbox'], extract_img, alt_colorspace=img[5], doc=self.doc)
                )
                xrefs_checked.append(xref)
                found = True
                break

        if not found:
            xreferred_image_list.append(
                ImageEmbedded(xref, None, extract_img, alt_colorspace=img[5], doc=self.doc)
            )
            xrefs_checked.append(xref)

    def _match_page_content(self, page, xref, extract_img, img, all_image_from_page,
                           xreferred_image_list, xrefs_checked):
        """Match extracted images with page content."""
        index = 0
        while index < len(all_image_from_page):
            if extract_img['image'] == all_image_from_page[index]['image']:
                secure_to_add = True

                for obj in xreferred_image_list:
                    if all_image_from_page[index]['bbox'] == obj.bbox:
                        if obj.image == all_image_from_page[index]['image'] or obj.smask:
                            secure_to_add = False
                            break

                if xref in xrefs_checked:
                    if extract_img['width'] > 30 and extract_img['height'] > 30:
                        img = list(img)
                        img[5] = f"Isolate{index}"
                        img = tuple(img)

                if secure_to_add:
                    xreferred_image_list.append(
                        ImageEmbedded(xref, all_image_from_page[index]['bbox'], extract_img,
                                    alt_colorspace=img[5], doc=self.doc)
                    )
                    xrefs_checked.append(xref)
                    all_image_from_page.pop(index)
                    continue

            index += 1

    def _process_unmatched_images(self, page, all_image_from_page, xrefs_checked, xreferred_image_list):
        """Process images that weren't matched to xrefs."""
        index = 0
        for img in self.doc[page].get_images(full=True):
            xref = img[0]

            if xref in xrefs_checked or index >= len(all_image_from_page):
                index += 1
                continue

            extract_img = self.doc.extract_image(xref)

            if extract_img["smask"] > 0:
                xreferred_image_list.append(
                    ImageEmbedded(xref, None, extract_img, alt_colorspace=img[5], doc=self.doc)
                )
            else:
                xreferred_image_list.append(
                    ImageEmbedded(xref, all_image_from_page[index]['bbox'], extract_img,
                                alt_colorspace=img[5], doc=self.doc)
                )

            index += 1

    def _handle_overlapping_images(self, page, xreferred_image_list, extraction_path):
        """Handle images that overlap on the page."""
        overlap_set = self.build_overlap_set(xreferred_image_list)
        overlap_list = [list(o_set) for o_set in overlap_set]

        for list_ in overlap_list:
            embedded_overlapping_figures = [xreferred_image_list[i] for i in list_]

            if embedded_overlapping_figures[0].has_alpha():
                self._save_alpha_overlapped_image(page, embedded_overlapping_figures[0], extraction_path)
            elif len(embedded_overlapping_figures) > 1:
                self.assembly_image(embedded_overlapping_figures,
                                   f"{extraction_path}/p-{page + 1}-")
            else:
                self._save_single_image(page, embedded_overlapping_figures[0], extraction_path)

    def _save_alpha_overlapped_image(self, page, figure, extraction_path):
        """Save an overlapped image with alpha channel."""
        pix1 = fitz.Pixmap(self.doc, figure.xref)
        
        # Convert CMYK to RGB if needed BEFORE adding alpha
        if pix1.colorspace and pix1.colorspace.name == COLORSPACE_CMYK:
            pix1 = fitz.Pixmap(fitz.csRGB, pix1)
        
        pix2 = fitz.Pixmap(self.doc, figure.smask)
        pix = fitz.Pixmap(pix1)
        pix.set_alpha(pix2.samples)

        if figure.bbox:
            file_name = (f"{extraction_path}/p-{page + 1}-x0-{figure.x0:.3f}-"
                        f"y0-{figure.y0:.3f}-x1-{figure.x1:.3f}-y1-{figure.y1:.3f}-"
                        f"{self.img_counter}.png")
        else:
            file_name = (f"{extraction_path}/p-{page + 1}-x0-0.000-y0-0.000-"
                        f"x1-0.000-y1-0.000-{self.img_counter}.png")

        if self.write_img(pix, file_name):
            self.img_counter += 1

        pix = pix1 = pix2 = None

    def _save_single_image(self, page, figure, extraction_path):
        """Save a single image."""
        if figure.has_alpha():
            pix1 = fitz.Pixmap(self.doc, figure.xref)
            
            # Convert CMYK to RGB if needed BEFORE adding alpha
            if pix1.colorspace and pix1.colorspace.name == COLORSPACE_CMYK:
                pix1 = fitz.Pixmap(fitz.csRGB, pix1)
            
            pix2 = fitz.Pixmap(self.doc, figure.smask)
            pix = fitz.Pixmap(pix1)
            pix.set_alpha(pix2.samples)

            if figure.bbox:
                file_name = (f"{extraction_path}/p-{page + 1}-x0-{figure.x0:.3f}-"
                            f"y0-{figure.y0:.3f}-x1-{figure.x1:.3f}-y1-{figure.y1:.3f}-"
                            f"{self.img_counter}.png")
            else:
                file_name = (f"{extraction_path}/p-{page + 1}-x0-0.000-y0-0.000-"
                            f"x1-0.000-y1-0.000-{self.img_counter}.png")

            if self.write_img(pix, file_name, figure.alt_colorspace):
                self.img_counter += 1

        else:
            pix = fitz.Pixmap(self.doc, figure.xref)

            if figure.bbox:
                file_name = (f"{extraction_path}/p-{page + 1}-x0-{figure.x0:.3f}-"
                            f"y0-{figure.y0:.3f}-x1-{figure.x1:.3f}-y1-{figure.y1:.3f}-"
                            f"{self.img_counter}.png")
            else:
                file_name = (f"{extraction_path}/p-{page + 1}-x0-0.000-y0-0.000-"
                            f"x1-0.000-y1-0.000-{self.img_counter}.png")

            if self.write_img(pix, file_name, figure.alt_colorspace):
                self.img_counter += 1

    def write_alpha_imgs(self, img_data, name):
        """
        Write RGBA image with white background without compression.

        Parameters
        ----------
        img_data : PIL.Image or bytes
            Image data as PIL Image or bytes.
        name : str
            Output filename.

        Returns
        -------
        bool
            Success status.
        """
        if not img_data:
            raise ValueError(f"IMAGE {name} WITH STENCIL MASK ERROR")

        # Handle both PIL Image and bytes input
        if isinstance(img_data, Image.Image):
            img = img_data
        else:
            img = Image.open(io.BytesIO(img_data))
            img.load()

        if img.size[0] < MIN_IMAGE_WIDTH or img.size[1] < MIN_IMAGE_HEIGHT:
            return False

        background = Image.new("RGB", img.size, (255, 255, 255))
        # Ensure img has alpha channel
        if img.mode not in ('RGBA', 'LA', 'PA'):
            # If no alpha channel, just paste directly
            background.paste(img)
        else:
            background.paste(img, mask=img.split()[-1])  # Use last channel as mask (alpha)
        # Save without compression to preserve raw image data
        background.save(name, compress_level=0)
        del background
        del img

        return True

    def write_img(self, pix, file_name, alt_colorspace=None):
        """
        Write image from fitz.Pixmap to file without compression.

        Parameters
        ----------
        pix : fitz.Pixmap
            Pixmap object to write.
        file_name : str
            Output filename.
        alt_colorspace : str, optional
            Alternative colorspace name.

        Returns
        -------
        bool
            Success status.
        """
        if pix.width < MIN_IMAGE_WIDTH or pix.height < MIN_IMAGE_HEIGHT:
            return False

        if not pix.colorspace:
            return False

        try:
            colorspace_name = pix.colorspace.name

            if colorspace_name == COLORSPACE_GRAY:
                if pix.alpha > 1:  # Has alpha channel
                    pixRGB = fitz.Pixmap(fitz.csRGB, pix)
                    # Use getPNGData() to properly encode alpha channel, then write as RGBA
                    png_bytes = pixRGB.tobytes('png')
                    return self.write_alpha_imgs(png_bytes, file_name)
                else:
                    if alt_colorspace in ("Separation", "DeviceN"):
                        pix.invertIRect()
                    # Convert to PIL and save without compression
                    pil_img = pix.pil_image()
                    pil_img.save(file_name, compress_level=0)
                    return True

            elif colorspace_name == COLORSPACE_RGB:
                if pix.alpha > 1:  # Has alpha channel
                    # Use getPNGData() to properly encode alpha channel, then write as RGBA
                    png_bytes = pix.tobytes('png')
                    return self.write_alpha_imgs(png_bytes, file_name)
                else:
                    # Convert to PIL and save without compression
                    pil_img = pix.pil_image()
                    pil_img.save(file_name, compress_level=0)
                    return True

            elif colorspace_name == COLORSPACE_CMYK:
                # Convert CMYK to RGB
                pixRGB = fitz.Pixmap(fitz.csRGB, pix)

                if pixRGB.alpha > 1:  # Has alpha channel
                    # Use getPNGData() to properly encode alpha channel, then write as RGBA
                    png_bytes = pixRGB.tobytes('png')
                    return self.write_alpha_imgs(png_bytes, file_name)
                else:
                    # Convert to PIL and save without compression
                    pil_img = pixRGB.pil_image()
                    # Ensure it's RGB format (not CMYK)
                    if pil_img.mode == 'CMYK':
                        pil_img = pil_img.convert('RGB')
                    pil_img.save(file_name, compress_level=0)
                    return True

            else:
                # Handle unknown colorspaces by converting to RGB
                try:
                    pixRGB = fitz.Pixmap(fitz.csRGB, pix)
                    pil_img = pixRGB.pil_image()
                    # Ensure it's RGB format
                    if pil_img.mode not in ('RGB', 'RGBA'):
                        pil_img = pil_img.convert('RGB')
                    pil_img.save(file_name, compress_level=0)
                    return True
                except Exception as e:
                    print(f"Warning: Could not convert colorspace {colorspace_name}: {e}")
                    return False

        except ValueError:
            return False
        except KeyboardInterrupt:
            raise

    def build_overlap_set(self, figures):
        """
        Build sets of overlapping figures.

        Parameters
        ----------
        figures : list
            List of ImageEmbedded objects.

        Returns
        -------
        list
            List of sets containing indices of overlapping images.
        """
        overlap_set = [set() for _ in range(len(figures))]

        for i in range(len(figures)):
            for j in range(i, len(figures)):
                if self.has_overlap(figures, i, j):
                    overlap_set[i].add(j)

        self.union_intersections_images(overlap_set)

        while True:
            old_len_set = len(overlap_set)
            overlap_set = self.union_region_fig_overlap(figures, overlap_set)
            if old_len_set == len(overlap_set):
                break

        return overlap_set

    def union_region_fig_overlap(self, figures, overlap_set):
        """Union overlapping figure regions."""
        overlap_figs = []

        for index, set_figs in enumerate(overlap_set):
            list_figs = list(set_figs)
            valid_index_bbox = 0
            stop_index = 0

            for lists_index, figures_index in enumerate(list_figs):
                if figures[figures_index].bbox:
                    valid_index_bbox = lists_index
                    stop_index = lists_index
                    break

            if stop_index <= len(list_figs) - 1 and figures[list_figs[valid_index_bbox]].bbox:
                union_region = figures[list_figs[valid_index_bbox]].copy()
                for fig in list_figs[valid_index_bbox:]:
                    union_region.bbox.include_rect(figures[fig].bbox)
                overlap_figs.append(union_region)
            else:
                overlap_figs.append(ImageEmbedded(None, None))

        restart_union_search = True
        while restart_union_search:
            restart_union_search = False
            for i in range(len(overlap_figs)):
                if restart_union_search:
                    break
                for j in range(i, len(overlap_figs)):
                    if i != j and self.has_overlap(overlap_figs, i, j):
                        if not self.same_location_bbox_used(overlap_set[i], overlap_set[j], figures):
                            overlap_figs[i].bbox.include_rect(overlap_figs[j].bbox)
                            overlap_set[i] = overlap_set[i].union(overlap_set[j])
                            overlap_figs.pop(j)
                            overlap_set.pop(j)
                            restart_union_search = True
                            break

        self.union_intersections_images(overlap_set)
        return overlap_set

    def same_location_bbox_used(self, set_i, set_j, figures):
        """Check if two sets of figures share the same location."""
        for fig_i in set_i:
            for fig_j in set_j:
                p0_i, p1_i, p2_i, p3_i = get_rectangles_points(figures[fig_i].bbox)
                p0_j, p1_j, p2_j, p3_j = get_rectangles_points(figures[fig_j].bbox)

                if (p0_i.distance_to(p0_j) == 0 and p1_i.distance_to(p1_j) == 0 and
                        p2_i.distance_to(p2_j) == 0 and p3_i.distance_to(p3_j) == 0):
                    return True

        return False

    def union_intersections_images(self, overlap_set):
        """Union sets that have intersections."""
        restart_union_search = True
        while restart_union_search:
            restart_union_search = False
            for i in range(len(overlap_set)):
                if restart_union_search:
                    break
                for j in range(i, len(overlap_set)):
                    if bool(set.intersection(overlap_set[i], overlap_set[j])) and i != j:
                        overlap_set[i] = overlap_set[i].union(overlap_set[j])
                        del overlap_set[j]
                        restart_union_search = True
                        break

    def assembly_image(self, figures, file_name):
        """
        Assembly overlapping figures into a single image.

        Parameters
        ----------
        figures : list
            List of overlapping ImageEmbedded objects.
        file_name : str
            Base filename for output.

        Returns
        -------
        bool
            Success status.
        """
        sketch = fitz.Rect(figures[0].bbox)
        for fig in figures:
            sketch.include_rect(fig.bbox)

        res_img = None
        distance = 1.0
        not_found = 1

        try:
            figures.sort(key=lambda x: (x.x1, x.y1, x.x0, x.y0))

            while len(figures) > 1:
                obj_i = figures.pop(0)

                for index_j, obj_j in enumerate(figures):
                    if check_overlap(obj_i.bbox, obj_j.bbox, distance):
                        res_img, res_obj = self.merge_images(obj_i, obj_j, file_name)
                        figures.pop(index_j)
                        figures.append(res_obj)
                        not_found = 0
                        break

                if not_found == len(figures):
                    if distance == 5:
                        distance = 0.5
                        img_i = self._load_image(obj_i)
                        full_file_name = (f"{file_name}x0-{obj_i.x0:.3f}-y0-{obj_i.y0:.3f}-"
                                         f"x1-{obj_i.x1:.3f}-y1-{obj_i.y1:.3f}-{self.img_counter}.png")
                        # Ensure image is in RGB mode before saving as PNG
                        if img_i.mode == 'CMYK':
                            img_i = img_i.convert('RGB')
                        elif img_i.mode not in ('RGB', 'RGBA', 'L'):
                            img_i = img_i.convert('RGB')
                        img_i.save(full_file_name, compress_level=0)
                        self.img_counter += 1
                        continue

                    distance += 0.5
                    print(f"ERROR: {file_name} IMAGE IS CORRUPT. TRYING WITH {distance} DISTANCE")
                    not_found = 0

                if not_found:
                    figures.sort(key=lambda x: (x.x1, x.y1, x.x0, x.y0))
                    figures.append(obj_i)

                not_found += 1

            if res_img is not None:
                if res_img.size[0] < MIN_IMAGE_WIDTH or res_img.size[1] < MIN_IMAGE_HEIGHT:
                    return False

                full_file_name = (f"{file_name}x0-{res_obj.x0:.3f}-y0-{res_obj.y0:.3f}-"
                                 f"x1-{res_obj.x1:.3f}-y1-{res_obj.y1:.3f}-{self.img_counter}.png")
                # Ensure image is in RGB mode before saving as PNG
                if res_img.mode == 'CMYK':
                    res_img = res_img.convert('RGB')
                elif res_img.mode not in ('RGB', 'RGBA', 'L'):
                    res_img = res_img.convert('RGB')
                res_img.save(full_file_name, compress_level=0)
                return True
            else:
                raise ValueError("Assembly failed")

        except ValueError:
            print(f"{file_name} has image errors in assembly function")
            return False
        except KeyboardInterrupt:
            raise

    def _load_image(self, obj):
        """Load image from ImageEmbedded object."""
        if obj.xref is None:
            return obj.image

        pix = fitz.Pixmap(self.doc, obj.xref)

        if obj.colorspace != 3 and pix.colorspace and pix.alpha == 0:
            pix = fitz.Pixmap(fitz.csRGB, pix)

        byte_img = pix.tobytes('png')
        img = Image.open(io.BytesIO(byte_img))
        img.load()

        if len(img.getbands()) == 1 and pix.colorspace is None:
            img = ImageOps.invert(img)
            img = img.convert("RGB")

        if img.mode == 'RGBA':
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background.copy()
            del background

        pix = None
        return img

    def merge_images(self, obj_i, obj_j, file_name):
        """
        Merge two overlapping images.

        Parameters
        ----------
        obj_i : ImageEmbedded
            First image object.
        obj_j : ImageEmbedded
            Second image object.
        file_name : str
            Base output filename.

        Returns
        -------
        tuple
            (merged_image, result_object)
        """
        img_i = self._load_image(obj_i)
        img_j = self._load_image(obj_j)

        sketch = fitz.Rect(obj_i.bbox)
        sketch.include_rect(obj_j.bbox)

        real_w = [(sketch.width * obj.width) / (obj.x1 - obj.x0) for obj in [obj_i, obj_j]]
        real_h = [(sketch.height * obj.height) / (obj.y1 - obj.y0) for obj in [obj_i, obj_j]]

        real_w = int(np.round(np.mean(real_w), 1))
        real_h = int(np.round(np.mean(real_h), 1))

        # Calculate positions
        if obj_i.x0 < obj_j.x0:
            x0_i = 0
            x1_i = int(real_w * (obj_i.x1 - obj_i.x0) / sketch.width)
            x1_j = real_w
            x0_j = max(0, real_w - obj_j.width)
        else:
            x1_i = real_w
            x0_i = max(0, real_w - obj_i.width)
            x0_j = 0
            x1_j = int(real_w * (obj_j.x1 - obj_j.x0) / sketch.width)

        if obj_i.y0 < obj_j.y0:
            y0_i = 0
            y1_i = int(real_h * (obj_i.y1 - obj_i.y0) / sketch.height)
            y1_j = real_h
            y0_j = max(0, real_h - obj_j.height)
        else:
            y1_i = real_h
            y0_i = max(0, real_h - obj_i.height)
            y0_j = 0
            y1_j = int(real_h * (obj_j.y1 - obj_j.y0) / sketch.height)

        x0_i, y0_i, x1_i, y1_i = [int(x) for x in np.round([x0_i, y0_i, x1_i, y1_i], 3)]
        x0_j, y0_j, x1_j, y1_j = [int(x) for x in np.round([x0_j, y0_j, x1_j, y1_j], 3)]

        # Check for overlapping conflicts
        if x0_i < x0_j and (x0_i + img_i.width - x0_j) > 10:
            if img_j.width > 10 and img_j.height > 10:
                full_file_name = (f"{file_name}x0-{obj_j.x0:.3f}-y0-{obj_j.y0:.3f}-"
                                 f"x1-{obj_j.x1:.3f}-y1-{obj_j.y1:.3f}-{self.img_counter}.png")
                # Ensure image is in RGB mode before saving as PNG
                if img_j.mode == 'CMYK':
                    img_j = img_j.convert('RGB')
                elif img_j.mode not in ('RGB', 'RGBA', 'L'):
                    img_j = img_j.convert('RGB')
                img_j.save(full_file_name, compress_level=0)
                self.img_counter += 1
            return img_i, obj_i

        if x0_j < x0_i and (x0_j + img_j.width - x0_i) > 10:
            if img_i.width > 10 and img_i.height > 10:
                full_file_name = (f"{file_name}x0-{obj_i.x0:.3f}-y0-{obj_i.y0:.3f}-"
                                 f"x1-{obj_i.x1:.3f}-y1-{obj_i.y1:.3f}-{self.img_counter}.png")
                # Ensure image is in RGB mode before saving as PNG
                if img_i.mode == 'CMYK':
                    img_i = img_i.convert('RGB')
                elif img_i.mode not in ('RGB', 'RGBA', 'L'):
                    img_i = img_i.convert('RGB')
                img_i.save(full_file_name, compress_level=0)
                self.img_counter += 1
            return img_j, obj_j

        if y0_i < y0_j and (y0_i + img_i.height - y0_j) > 10:
            if img_j.width > 10 and img_j.height > 10:
                full_file_name = (f"{file_name}x0-{obj_j.x0:.3f}-y0-{obj_j.y0:.3f}-"
                                 f"x1-{obj_j.x1:.3f}-y1-{obj_j.y1:.3f}-{self.img_counter}.png")
                # Ensure image is in RGB mode before saving as PNG
                if img_j.mode == 'CMYK':
                    img_j = img_j.convert('RGB')
                elif img_j.mode not in ('RGB', 'RGBA', 'L'):
                    img_j = img_j.convert('RGB')
                img_j.save(full_file_name, compress_level=0)
                self.img_counter += 1
            return img_i, obj_i

        if y0_j < y0_i and (y0_j + img_j.height - y0_i) > 10:
            if img_i.width > 10 and img_i.height > 10:
                full_file_name = (f"{file_name}x0-{obj_i.x0:.3f}-y0-{obj_i.y0:.3f}-"
                                 f"x1-{obj_i.x1:.3f}-y1-{obj_i.y1:.3f}-{self.img_counter}.png")
                img_i.save(full_file_name)
                self.img_counter += 1
            return img_j, obj_j

        # Create merged image
        res_img = Image.new('RGB', (real_w, real_h), (255, 255, 255))
        res_img.paste(img_j, (x0_j, y0_j))
        res_img.paste(img_i, (x0_i, y0_i))

        merge_embedded_image = ImageEmbedded(None, sketch)
        merge_embedded_image.height = real_h
        merge_embedded_image.width = real_w
        merge_embedded_image.colorspace = obj_j.colorspace
        merge_embedded_image.ext = obj_j.ext
        merge_embedded_image.image = res_img

        return res_img, merge_embedded_image

    def has_overlap(self, figures, figure_i, figure_j):
        """
        Check if two figures overlap on the PDF page.

        Parameters
        ----------
        figures : list
            List of ImageEmbedded objects.
        figure_i : int
            Index of first figure.
        figure_j : int
            Index of second figure.

        Returns
        -------
        bool
            True if figures overlap, False otherwise.
        """
        if figure_i == figure_j:
            return True

        img_i = figures[figure_i]
        img_j = figures[figure_j]

        if img_i.bbox is None or img_j.bbox is None:
            return False

        if img_i.has_alpha() or img_j.has_alpha():
            return False

        if img_i.xref and img_j.xref and img_i.filter != img_j.filter:
            return False

        if img_i.colorspace != img_j.colorspace:
            return False

        if img_i.alt_colorspace != img_j.alt_colorspace:
            return False

        if img_j.xref and img_i.xref:
            pixi = fitz.Pixmap(self.doc, img_i.xref)
            pixj = fitz.Pixmap(self.doc, img_j.xref)

            if pixi.colorspace != pixj.colorspace:
                return False

        return check_overlap(img_i.bbox, img_j.bbox)
