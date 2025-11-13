"""
Command-line interface for PDF image extraction.

Provides the main entry point for running image extraction from PDF files.
"""

import argparse
import sys

from pdf_image_extraction.core import PDFExtractor


def create_parser():
    """
    Create and return the argument parser for the CLI.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog='extract-images',
        description='Extract images from PDF documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i input.pdf -o ./output
  %(prog)s -i /path/to/pdfs -o ./output -m safe
  %(prog)s -i doc1.pdf doc2.pdf -o ./output -m normal
        """
    )

    parser.add_argument(
        '--input-path', '-i',
        required=True,
        nargs='+',
        help='Path to PDF file(s) or directory containing PDFs'
    )

    parser.add_argument(
        '--output-path', '-o',
        type=str,
        default='.',
        help='Output directory for extracted images (default: current directory)'
    )

    parser.add_argument(
        '--mode', '-m',
        type=str,
        default='normal',
        choices=['safe', 'normal', 'unsafe'],
        help="""
Extraction mode:
  safe   - Extract only xreferred images (most conservative)
  normal - Extract with duplicate/corruption detection (default, recommended)
  unsafe - Extract all images without warranty (not recommended)
        """
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    return parser


def main():
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        if args.verbose:
            print(f"Mode: {args.mode}")
            print(f"Input: {args.input_path}")
            print(f"Output: {args.output_path}")

        extractor = PDFExtractor(input_path=args.input_path)
        extractor.extract_all(out_name=args.output_path, mode=args.mode)

        if args.verbose:
            print("Extraction completed successfully!")

    except IOError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Invalid argument: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
