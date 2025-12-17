# Minimal Alpine-based PDF image extraction container
# Using Python 3.11+ on Alpine Linux (~200MB total)

FROM python:3.11-alpine

# Install build and runtime dependencies
# Build-time: build-base, musl-dev for C extensions compilation
# Runtime: libjpeg, libffi, freetype, libstdc++ for PDF/image processing
RUN apk add --no-cache \
    build-base \
    musl-dev \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    libffi-dev \
    libstdc++

# Set working directory
WORKDIR /app

# Copy package configuration and requirements
COPY setup.py requirements.txt README.md ./

# Copy source code - all in src/
COPY src/ ./src/

# Install package with dependencies directly to system Python
# --no-cache-dir: Don't cache pip packages (smaller image)
# This installs the package in editable mode for direct src/ access
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -r requirements.txt

# Remove build dependencies for smaller final image
RUN apk del --no-cache \
    build-base \
    musl-dev

# Create input/output directories for volume mounts
RUN mkdir -p /INPUT /OUTPUT

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    INPUT_PATH=/INPUT/sample.pdf \
    OUTPUT_PATH=/OUTPUT \
    EXTRACTION_MODE=normal

# Use the CLI with environment variable support via Docker mode
# When running, set INPUT_PATH, OUTPUT_PATH, and EXTRACTION_MODE environment variables
# Example: docker run -e INPUT_PATH=/INPUT/file.pdf -e OUTPUT_PATH=/OUTPUT \
#                     -e EXTRACTION_MODE=safe -v /local:/INPUT -v /out:/OUTPUT \
#                     pdf-extractor:latest --env
ENTRYPOINT ["python3", "-m", "pdf_image_extraction.cli.docker"]
CMD ["--env"]
