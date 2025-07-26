import os
from src.data_processing.pdf_parser import extract_text_blocks
from src.data_processing.heuristics import remove_headers_footers_tables, get_document_stats, is_table_block

PDF_DIR = 'data/raw_pdfs'

def test_table_exclusion():
    """Test the table text exclusion functionality."""
    pdf_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print('No PDF files found in', PDF_DIR)
        return
    
    for pdf in pdf_files:
        pdf_path = os.path.join(PDF_DIR, pdf)
        print(f'\n=== Testing Table Exclusion for: {pdf} ===')
        
        # Extract blocks
        blocks = extract_text_blocks(pdf_path)
        if not blocks:
            print('  No blocks found.')
            continue
        
        num_pages = max(b['page_num'] for b in blocks) + 1
        doc_stats = get_document_stats(blocks)
        
        print(f'  Total blocks before filtering: {len(blocks)}')
        print(f'  Number of pages: {num_pages}')
        print(f'  Document median font size: {doc_stats.get("median_size", 12.0):.2f}')
        
        # Test table detection on individual blocks
        table_blocks = []
        for i, block in enumerate(blocks):
            if is_table_block(block, blocks, doc_stats):
                text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
                table_blocks.append((i, text[:50], block['bbox']))
        
        print(f'  Blocks detected as table text: {len(table_blocks)}')
        if table_blocks:
            print('  Sample table blocks:')
            for idx, text, bbox in table_blocks[:5]:  # Show first 5
                print(f'    Block {idx}: "{text}..." at {bbox}')
        
        # Apply comprehensive filtering
        filtered_blocks = remove_headers_footers_tables(blocks, num_pages, doc_stats)
        print(f'  Blocks after comprehensive filtering: {len(filtered_blocks)}')
        print(f'  Removed {len(blocks) - len(filtered_blocks)} blocks total')
        
        # Show sample of remaining blocks
        print('  Sample remaining blocks:')
        for i, block in enumerate(filtered_blocks[:3]):
            text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
            print(f'    Block {i}: "{text[:80]}..."')

if __name__ == '__main__':
    test_table_exclusion() 