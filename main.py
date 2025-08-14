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
    get_document_stats, find_title, 
    classify_numbered_heading, classify_styled_heading,
    remove_headers_footers_tables, is_table_block,
    is_title_block, clean_heading_text
)
from src.data_processing.feature_engineering import create_feature_vector
from src.models.prediction import StructurePredictor
from src.utils.validation import validate_hierarchy

# --- Configuration ---
MODEL_PATH = './models/lgbm_model.joblib'
ENCODER_PATH = './models/label_encoder.joblib'

# Original 5 test PDFs for evaluation
ORIGINAL_TEST_FILES = [
    'file01.pdf',
    'file02.pdf', 
    'file03.pdf',
    'file04.pdf',
    'file05.pdf',
]

def associate_content_to_headings(headings: List[Dict[str, Any]], all_content_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Associates paragraph text content with each heading.

    The content for a heading is defined as all text blocks that appear after it
    but before the next heading.
    """
    if not headings:
        return []

    # Create a set of heading identifiers (page, y_pos) for quick lookup
    heading_positions = {(h['page'], h['y_pos']) for h in headings}

    # Filter out blocks that are already identified as headings from our potential content blocks.
    # These are the paragraphs, list items, etc.
    paragraph_blocks = [
        b for b in all_content_blocks
        if (b.get('page_num', -1), b.get('bbox', [0, 0, 0, 0])[1]) not in heading_positions
    ]

    # Initialize content for each heading
    for h in headings:
        h['content'] = ""

    # Iterate through headings to assign content blocks
    for i, current_heading in enumerate(headings):
        content_for_heading = []
        
        # Define the start boundary (the current heading's position)
        start_page = current_heading['page']
        start_y = current_heading['y_pos']

        # Define the end boundary (the next heading's position)
        end_page, end_y = float('inf'), float('inf')
        if i + 1 < len(headings):
            next_heading = headings[i+1]
            end_page = next_heading['page']
            end_y = next_heading['y_pos']

        # Find all paragraph blocks that fall between the current and next heading
        for block in paragraph_blocks:
            block_page = block['page_num']
            block_y = block['bbox'][1]

            is_after_start = (block_page > start_page) or (block_page == start_page and block_y > start_y)
            is_before_end = (block_page < end_page) or (block_page == end_page and block_y < end_y)

            if is_after_start and is_before_end:
                block_text = " ".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
                if block_text:
                    content_for_heading.append(block_text)
        
        # Join the collected paragraphs with a newline
        current_heading['content'] = "\n".join(content_for_heading)

    return headings

def process_pdf(pdf_path: str) -> dict:
    """
    Main processing function for a single PDF file. This function orchestrates
    the entire extraction and classification pipeline with enhanced robustness.
    """
    start_time = time.time()
    print(f"Processing: {os.path.basename(pdf_path)}")

    # 1. Ingestion and Initial Parsing
    all_blocks = extract_text_blocks(pdf_path)
    if not all_blocks:
        print(f"Warning: No text blocks found in {os.path.basename(pdf_path)}.")
        return {"title": "", "outline": []}

    num_pages = max(b.get('page_num', 0) for b in all_blocks) + 1
    doc_stats = get_document_stats(all_blocks)

    # 2. Title Extraction (enhanced with special case handling)
    title = find_title(all_blocks)
    # Special case for file05.pdf - if no meaningful title found, use empty string
    if not title or title.lower() == os.path.basename(pdf_path).lower():
        title = ""
    print(f"  - Extracted title: '{title[:50]}{'...' if len(title) > 50 else ''}'")

    # 3. Enhanced Preprocessing: Remove headers, footers, and table text
    print(f"  - Filtering headers, footers, and table text...")
    filtered_blocks = remove_headers_footers_tables(all_blocks, num_pages, doc_stats)
    print(f"  - Reduced from {len(all_blocks)} to {len(filtered_blocks)} blocks after filtering")
    
    headings = []
    blocks_for_ml = []
    
    # 4. Enhanced Heuristic Classification with Title Exclusion
    print(f"  - Applying heuristic classification...")
    for block in filtered_blocks:
        # Skip table blocks from heading classification
        if is_table_block(block, filtered_blocks, doc_stats):
            continue
            
        # Skip blocks that contain the title
        if is_title_block(block, title):
            continue
            
        # First, try numbered heading classification
        level = classify_numbered_heading(block, filtered_blocks, doc_stats)
        
        # If no numbered heading, try styled heading classification
        if not level:
            level = classify_styled_heading(block, doc_stats, filtered_blocks)
        
        if level:
            text = "".join(span['text'] for line in block['lines'] for span in line['spans']).strip()
            # Clean up the text using the new cleaning function
            text = clean_heading_text(text)
            if text:  # Only add if text is not empty after cleaning
                headings.append({
                    'level': level, 
                    'text': text, 
                    'page': block['page_num'], 
                    'y_pos': block['bbox'][1]  # Use y0 for sorting
                })
        else:
            blocks_for_ml.append(block)

    print(f"  - Found {len(headings)} headings via heuristics, {len(blocks_for_ml)} blocks for ML")

    # 5. ML-based Disambiguation for remaining blocks
    if blocks_for_ml:
        print(f"  - Applying ML classification...")
        predictor = StructurePredictor(MODEL_PATH, ENCODER_PATH)
        feature_vectors = []
        valid_blocks = []
        
        # Get page dimensions for feature engineering
        doc = fitz.open(pdf_path)
        prev_block = None
        
        for block in blocks_for_ml:
            # Skip table blocks from ML classification too
            if is_table_block(block, filtered_blocks, doc_stats):
                continue
                
            # Skip blocks that contain the title
            if is_title_block(block, title):
                continue
                
            page_num = block.get('page_num', 0)
            page = doc[page_num]
            features = create_feature_vector(
                block, doc_stats, page.rect.width, page.rect.height, prev_block
            )
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
                    text = clean_heading_text(text)
                    if text:  # Only add if text is not empty after cleaning
                        headings.append({
                            'level': label, 
                            'text': text, 
                            'page': block['page_num'], 
                            'y_pos': block['bbox'][1]
                        })
            print(f"  - ML added {len([p for p in predictions if p in ['H1', 'H2', 'H3']])} headings")

    # 6. Final Sorting, Validation, and Formatting
    print(f"  - Finalizing outline...")
    headings.sort(key=lambda x: (x['page'], x['y_pos']))
    
    # Associate content with each heading
    print(f"  - Associating content with headings...")
    headings_with_content = associate_content_to_headings(headings, filtered_blocks)

    # Remove temporary keys and perform final text cleaning
    for h in headings_with_content:
        del h['y_pos']
        # Final text cleaning
        h['text'] = clean_heading_text(h['text'])

    # Apply hierarchical validation
    final_outline = validate_hierarchy(headings_with_content)
    
    end_time = time.time()
    print(f"  - Completed in {end_time - start_time:.2f} seconds")
    print(f"  - Final outline: {len(final_outline)} headings")
    
    return {"title": title, "outline": final_outline}

def main():
    """
    Main function to process only the original 5 test PDFs for evaluation.
    This allows testing model improvements while training on a larger dataset.
    """
    parser = argparse.ArgumentParser(description="Extracts a structured outline from PDF files.")
    parser.add_argument("input_dir", type=str, help="The directory containing input PDF files.")
    parser.add_argument("output_dir", type=str, help="The directory where JSON output will be saved.")
    parser.add_argument("--test-only", action="store_true", 
                       help="Only process the original 5 test files (file01.pdf through file05.pdf)")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' not found.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # Filter to only the original 5 test files
    all_pdf_files = [os.path.join(args.input_dir, f) for f in os.listdir(args.input_dir) if f.lower().endswith('.pdf')]
    
    if args.test_only:
        # Only process the original 5 test files
        pdf_files = []
        for test_file in ORIGINAL_TEST_FILES:
            test_path = os.path.join(args.input_dir, test_file)
            if os.path.exists(test_path):
                pdf_files.append(test_path)
            else:
                print(f"Warning: {test_file} not found in {args.input_dir}")
        
        if not pdf_files:
            print(f"Error: None of the original test files found in {args.input_dir}")
            print(f"Expected files: {ORIGINAL_TEST_FILES}")
            return
            
        print(f"Processing only the original 5 test files for evaluation...")
    else:
        # Process all PDF files (original behavior)
        pdf_files = all_pdf_files
        print(f"Processing all PDF files in {args.input_dir}...")

    if not pdf_files:
        print(f"No PDF files found to process.")
        return

    # Use multiprocessing to process PDFs in parallel
    num_processes = min(cpu_count(), len(pdf_files))
    print(f"Starting processing pool with {num_processes} workers for {len(pdf_files)} files...")
    
    with Pool(processes=num_processes) as pool:
        results = pool.map(process_pdf, pdf_files)

    # 7. Write results to JSON files
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
    # This guard is essential for multiprocessing to work correctly
    main()
