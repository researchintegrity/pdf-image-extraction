"""Setup configuration for pdf-image-extraction package."""

from setuptools import setup, find_packages
import os

# Read README if available (may not exist during docker build)
long_description = "PDF Image Extraction Tool"
if os.path.isfile("README.md"):
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh 
        if line.strip() and not line.strip().startswith("#")
    ]

setup(
    name="pdf-image-extraction",
    version="1.0.0",
    author="Joao Phillipe Cardenuto",
    description="A robust PDF figure extraction tool for scientific documents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/researchintegrity/pdf-image-extraction",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "extract-images=pdf_image_extraction.cli.extract_images:main",
        ],
    },
)
