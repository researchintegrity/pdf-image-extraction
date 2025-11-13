# PDF Image Extraction 

A robust PDF figure extraction tool for scientific documents using PyMuPDF with support for corrupted PDF handling.

![](.figs/PDF-content-extraction.png)

## Features

- **Multiple extraction modes**: safe, normal (recommended), and unsafe
- **Corruption handling**: Can reconstruct figures from PDFs with certain types of corruption
- **Smart filtering**: Removes duplicate and single-color images
- **Docker support**: Containerized extraction service
- **Python API**: Easy integration into other tools

## Installation

### From Source

```bash
# Install the package in development mode
pip install -e .

# Or install with all dependencies at once
pip install -r requirements.txt
pip install -e .
```

### Using Docker

```bash
# Build the Docker image
docker build -t pdf-extractor:latest -f Dockerfile .
```

## Quick Start

### Command Line

```bash
# Extract images from a single PDF
extract-images -i input.pdf -o ./output

# Extract from a directory of PDFs
extract-images -i /path/to/pdfs -o ./output -m normal

# Use safe mode (most conservative)
extract-images -i document.pdf -o ./output -m safe
```

### Python API

```python
from pdf_image_extraction import PDFExtractor

# Create extractor
extractor = PDFExtractor(input_path='document.pdf')

# Extract images in normal mode
extractor.extract_all(out_name='./output', mode='normal')
```

### Service API

```python
from pdf_image_extraction_service.image_extractor_service import ImageExtractorService

# Create service
service = ImageExtractorService(extraction_mode='normal')

# Extract from single PDF
images = service.extract_images('document.pdf', './output')

# Extract from multiple PDFs
pdf_list = ['doc1.pdf', 'doc2.pdf', 'doc3.pdf']
results = service.extract_images_batch(pdf_list, './output')
```

### Docker

```bash
# Run extraction with Docker using environment variables
docker run \
  -v $(pwd):/INPUT \
  -v $(pwd)/output:/OUTPUT \
  -e INPUT_PATH=/INPUT/sample.pdf \
  -e OUTPUT_PATH=/OUTPUT \
  -e EXTRACTION_MODE=normal \
  pdf-extractor:latest --env

# Or use CLI arguments
docker run \
  -v $(pwd):/work \
  pdf-extractor:latest \
  -i /work/sample.pdf \
  -o /work/output \
  -m normal
```

## Extraction Modes

### Safe Mode (`-m safe`)
- Extracts only xreferred images
- Most conservative approach
- Recommended for quick extraction when speed is priority

### Normal Mode (`-m normal`) [Default]
- Extracts xreferred images
- Includes duplicate detection
- Handles PDF corruption
- **Recommended for most use cases**

### Unsafe Mode (`-m unsafe`)
- Extracts all images without xref warranty
- Not recommended - may produce duplicates
- Use only if other modes fail

## Output Format

Extracted images are saved as PNG files with naming convention:

```
p-{page}-x0-{x0}-y0-{y0}-x1-{x1}-y1-{y1}-{count}.png
```

Where:
- `page`: Page number in PDF (1-indexed)
- `x0, y0, x1, y1`: Bounding box coordinates in PDF coordinates
- `count`: Sequential image count

Example:
```
p-4-x0-40.000-y0-59.280-x1-553.600-y1-492.000-1.png
```


## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

See [LICENSE](LICENSE) file for full details.

### Summary

- **License Type:** AGPL-3.0
  - Free to use, modify, and distribute
  - If used in network/server applications, source code must be available to users
  - Modifications must be documented and shared
  - Derivative works must use the same license

For more information, visit: https://www.gnu.org/licenses/agpl-3.0.html

## Cite this work

If you use this tool in your research, please cite:

> Moreira, D., Cardenuto, J.P., Shao, R. et al. SILA: a system for scientific image analysis. Nature Scientific Reports 12 (18306), 2022. https://doi.org/10.1038/s41598-022-21535-3

```bibtex
@article{sila,
   author = {Moreira, Daniel and Cardenuto, João Phillipe and Shao, Ruiting and Baireddy, Sriram and Cozzolino, Davide and Gragnaniello, Diego and Abd‑Almageed, Wael and Bestagini, Paolo and Tubaro, Stefano and Rocha, Anderson and Scheirer, Walter and Verdoliva, Luisa and Delp, Edward},
   title = {{SILA: a system for scientifc image analysis}},
   journal = {Nature Scientific Reports},
   year = 2022,
   number = {12},
   volume = {18306},
   pages = {1--15}
}
```
