"""
CLI module for Docker and command-line operations.

Provides environment variable support for Docker deployment.
"""

import os
import sys
import argparse

from pdf_image_extraction.core import PDFExtractor


def extract_with_env():
    """
    Extract images using environment variables.
    
    Supports Docker environment variables:
    - INPUT_PATH: Path to PDF file (required)
    - OUTPUT_PATH: Output directory (default: /OUTPUT)
    - EXTRACTION_MODE: safe|normal|unsafe (default: normal)
    
    This function is useful for Docker ENTRYPOINT configuration.
    """
    input_path = os.environ.get('INPUT_PATH')
    output_path = os.environ.get('OUTPUT_PATH', '/OUTPUT')
    mode = os.environ.get('EXTRACTION_MODE', 'normal')
    
    if not input_path:
        print("Error: INPUT_PATH environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(input_path):
        print(f"Error: PDF file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    os.makedirs(output_path, exist_ok=True)
    
    try:
        print(f"Extracting images from: {input_path}")
        print(f"Mode: {mode}")
        print(f"Output: {output_path}")
        
        extractor = PDFExtractor(input_path)
        
        if mode == 'safe':
            extractor.safe_mode(pdf=input_path, dir_path=output_path)
        elif mode == 'unsafe':
            extractor.unsafe_mode(pdf=input_path, dir_path=output_path)
        else:  # normal
            extractor.normal_mode(pdf=input_path, dir_path=output_path)
        
        print("✓ Extraction complete")
        return 0
        
    except Exception as e:
        print(f"✗ Extraction failed: {str(e)}", file=sys.stderr)
        return 1


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
  # Extract from single PDF
  %(prog)s -i input.pdf -o ./output
  
  # Extract with specific mode
  %(prog)s -i /path/to/pdf.pdf -o ./output -m safe
  
  # Extract from multiple PDFs
  %(prog)s -i doc1.pdf doc2.pdf -o ./output -m normal
  
  # Using environment variables (Docker)
  export INPUT_PATH=/path/to/pdf.pdf
  export OUTPUT_PATH=/path/to/output
  export EXTRACTION_MODE=normal
  %(prog)s --env
        """
    )

    parser.add_argument(
        '--input-path', '-i',
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
        '--env',
        action='store_true',
        help='Use environment variables (INPUT_PATH, OUTPUT_PATH, EXTRACTION_MODE)'
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

    # If --env flag is set, use environment variables
    if args.env:
        if args.verbose:
            print("Using environment variables mode")
        sys.exit(extract_with_env())

    # Otherwise, use command-line arguments
    if not args.input_path:
        parser.print_help()
        sys.exit(1)

    try:
        if args.verbose:
            print(f"Mode: {args.mode}")
            print(f"Input: {args.input_path}")
            print(f"Output: {args.output_path}")

        extractor = PDFExtractor(input_path=args.input_path)
        extractor.extract_all(out_name=args.output_path, mode=args.mode)

        if args.verbose:
            print("✓ Extraction completed successfully!")

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
