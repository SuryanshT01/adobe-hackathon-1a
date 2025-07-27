# PDF Document Structure Extraction

## Overview

This project implements an intelligent PDF document structure extraction system that automatically identifies titles and headings from PDF documents. The solution combines rule-based heuristics with machine learning to accurately classify document structure elements.

## Approach

### Multi-Stage Processing Pipeline

1. **PDF Text Extraction**: Uses PyMuPDF for native text extraction and Tesseract OCR for scanned documents
2. **Preprocessing**: Removes headers, footers, and table text using advanced heuristics
3. **Title Detection**: Identifies document titles using font size, position, and content analysis
4. **Heading Classification**: 
   - **Rule-based**: Detects numbered headings (1.1, 2.3, etc.) and styled headings (bold, large font)
   - **ML-based**: Uses LightGBM model for disambiguation of remaining text blocks
5. **Hierarchy Validation**: Ensures logical heading structure (H1 → H2 → H3)

### Key Features

- **OCR Support**: Automatically detects and processes scanned PDFs
- **Table Text Exclusion**: Advanced heuristics to remove table content from analysis
- **Robust Title Extraction**: Handles multi-line titles and special cases
- **Parallel Processing**: Multi-threaded PDF processing for efficiency
- **Hierarchical Validation**: Maintains logical document structure

## Models and Libraries Used

### Core Libraries
- **PyMuPDF (fitz)**: PDF text extraction and analysis
- **Tesseract OCR**: Optical character recognition for scanned documents
- **LightGBM**: Machine learning model for heading classification
- **scikit-learn**: Feature engineering and model utilities
- **NumPy/Pandas**: Data manipulation and analysis

### Machine Learning Model
- **Algorithm**: LightGBM (Gradient Boosting)
- **Features**: Font size, position, text case, word count, spacing, alignment
- **Classes**: H1, H2, H3, and non-heading text
- **Training**: Supervised learning on labeled document data

### Heuristic Rules
- **Numbered Headings**: Pattern matching for hierarchical numbering (1.1, 2.3, etc.)
- **Styled Headings**: Font size, boldness, and text case analysis
- **Table Detection**: Spacing, alignment, and content pattern analysis
- **Header/Footer Removal**: Cross-page repetition detection

## Input/Output Format

### Input
- PDF files placed in `/app/input` directory
- Supports both native text PDFs and scanned documents

### Output
- JSON files in `/app/output` directory
- Each `filename.pdf` generates `filename.json`
- Output format:
```json
{
  "title": "Document Title",
  "outline": [
    {
      "level": "H1",
      "text": "Main Heading",
      "page": 1
    },
    {
      "level": "H2", 
      "text": "Sub Heading",
      "page": 1
    }
  ]
}
```

## Build and Run Instructions

### Building the Docker Image

```bash
docker build --platform linux/amd64 -t pdf-structure-extractor:latest .
```

### Running the Solution

```bash
docker run --rm \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/output:/app/output \
  --network none \
  pdf-structure-extractor:latest
```

### Expected Execution (as per submission guidelines)

```bash
# Build
docker build --platform linux/amd64 -t mysolutionname:somerandomidentifier

# Run
docker run --rm \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/output:/app/output \
  --network none \
  mysolutionname:somerandomidentifier
```

### Directory Structure
```
input/
├── file01.pdf
├── file02.pdf
└── ...

output/
├── file01.json
├── file02.json
└── ...
```

## Technical Details

### OCR Processing
- Automatically detects scanned pages (< 3 text blocks)
- Uses 300 DPI resolution for optimal accuracy
- Supports Japanese vertical text orientation

### Performance Optimizations
- Multi-stage Docker build for smaller image size
- Parallel PDF processing using multiprocessing
- Efficient memory management for large documents

### Error Handling
- Graceful handling of corrupted PDFs
- Fallback mechanisms for OCR failures
- Robust text cleaning and validation

## Model Training

The machine learning model was trained on a diverse dataset of PDF documents with manually labeled headings. Features include:

- **Font-based**: Size, weight, family
- **Positional**: X/Y coordinates, page position
- **Content-based**: Word count, text case, patterns
- **Contextual**: Spacing, alignment with adjacent blocks

## Limitations and Future Improvements

- Currently supports H1, H2, H3 heading levels
- Optimized for English and Japanese text
- Could be extended for more document types and languages
- Potential for real-time processing with streaming input
