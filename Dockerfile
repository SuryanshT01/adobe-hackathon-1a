# Build stage
FROM --platform=linux/amd64 python:3.10-slim AS builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-jpn-vert \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM --platform=linux/amd64 python:3.10-slim

# Install runtime dependencies (Tesseract OCR)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-jpn-vert \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy application code
COPY src/ ./src/
COPY models/ ./models/
COPY main.py .

# Create input and output directories
RUN mkdir -p /app/input /app/output

# Set the command to process PDFs from input directory to output directory
CMD ["python", "main.py", "/app/input", "/app/output"]