import os
import json
import sys
import argparse
import time
from multiprocessing import Pool, cpu_count
from typing import List, Dict, Any
import fitz # PyMuPDF

# Import all necessary modules from the project structure
from src.data_processing.pdf_parser import extract_text_blocks
from src.data_processing.heuristics import (
    get_document_stats, find_title, filter_headers_footers,
    classify_numbered_heading, classify_styled_heading
)
from src.data_processing.feature_engineering import create_feature_vector
from src.models.prediction import StructurePredictor
from src.utils.validation import validate_hierarchy

# --- Configuration ---
MODEL_PATH = './models/lgbm_model.joblib'
ENCODER_PATH = './models/label_encoder.joblib'

def process_pdf(pdf_path: str) -> dict:
    """
    Main processing function for a single PDF file. This function orchestrates
    the entire extraction and classification pipeline.
    """
    start_time = time.time()
    print(f"Processing: {os.path.basename(pdf_path)}")

    # 1. Ingestion and Initial Parsing
    all_blocks = extract_text_blocks(pdf_path)
    if not all_blocks:
        print(f"Warning: No text blocks found in {os.path.basename(pdf_path)}.")
        return {"title": os.path.basename(pdf_path), "outline": []}

    num_pages = max(b.get('page_num', 0) for b in all_blocks) + 1
    doc_stats = get_document_stats(all_blocks)

    # 2. Heuristic Preprocessing and Classification
    title = find_title(all_blocks) or os.path.basename(pdf_path)
    filtered_blocks = filter_headers_footers(all_blocks, num_pages, doc_stats)
    
    headings = []
    blocks_for_ml = []
    
    for block in filtered_blocks:
        # First, try heuristic classification
        level = classify_numbered_heading(block) or classify_styled_heading(block, doc_stats)
        
        if level:
            text = "".join(span['text'] for line in block['lines'] for span in line['spans']).strip()
            headings.append({'level': level, 'text': text, 'page': block['page_num'], 'y_pos': block['bbox'][2]})
        else:
            blocks_for_ml.append(block)

    # 3. ML-based Disambiguation for remaining blocks
    if blocks_for_ml:
        predictor = StructurePredictor(MODEL_PATH, ENCODER_PATH)
        feature_vectors = []
        valid_blocks = []
        
        doc = fitz.open(pdf_path)
        prev_block = None
        for block in blocks_for_ml:
            page_num = block.get('page_num', 0)
            page = doc[page_num]
            features = create_feature_vector(block, doc_stats, page.rect.width, page.rect.height, prev_block)
            if features:
                feature_vectors.append(features)
                valid_blocks.append(block)
            prev_block = block
        doc.close()

        if feature_vectors:
            predictions = predictor.predict(feature_vectors)
            for block, label in zip(valid_blocks, predictions):
                if label in ["H1", "H2", "H3"]:
                    text = "".join(span['text'] for line in block['lines'] for span in line['spans']).strip()
                    headings.append({'level': label, 'text': text, 'page': block['page_num'], 'y_pos': block['bbox'][2]})

    # 4. Final Sorting, Validation, and Formatting
    headings.sort(key=lambda x: (x['page'], x['y_pos']))
    
    for h in headings:
        del h['y_pos'] # Remove temporary key

    final_outline = validate_hierarchy(headings)
    
    end_time = time.time()
    print(f"Finished {os.path.basename(pdf_path)} in {end_time - start_time:.2f} seconds.")
    
    return {"title": title, "outline": final_outline}

def main():
    """
    Main function to discover PDFs, process them in parallel, and write JSON outputs.
    """
    parser = argparse.ArgumentParser(description="Extracts a structured outline from PDF files.")
    parser.add_argument("input_dir", type=str, help="The directory containing input PDF files.")
    parser.add_argument("output_dir", type=str, help="The directory where JSON output will be saved.")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' not found.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    pdf_files = [os.path.join(args.input_dir, f) for f in os.listdir(args.input_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f"No PDF files found in {args.input_dir}.")
        return

    # Use multiprocessing to process PDFs in parallel [10, 9]
    num_processes = min(cpu_count(), len(pdf_files))
    print(f"Starting processing pool with {num_processes} workers for {len(pdf_files)} files...")
    
    with Pool(processes=num_processes) as pool:
        results = pool.map(process_pdf, pdf_files)

    # 5. Write results to JSON files
    for pdf_path, result_data in zip(pdf_files, results):
        output_filename = os.path.splitext(os.path.basename(pdf_path))[0] + '.json'
        output_path = os.path.join(args.output_dir, output_filename)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=4, ensure_ascii=False)
            print(f"Successfully wrote output to {output_path}")
        except Exception as e:
            print(f"Error writing JSON for {pdf_path}: {e}")

if __name__ == '__main__':
    # This guard is essential for multiprocessing to work correctly [9]
    main()