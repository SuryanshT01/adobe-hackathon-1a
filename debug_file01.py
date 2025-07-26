import os
from src.data_processing.pdf_parser import extract_text_blocks
from src.data_processing.heuristics import remove_headers_footers_tables, get_document_stats, is_table_block, classify_numbered_heading, classify_styled_heading

def debug_file01():
    """Debug file01.pdf to understand why table text is still appearing."""
    pdf_path = 'data/raw_pdfs/file01.pdf'
    print(f'=== Debugging {pdf_path} ===')
    
    # Extract blocks
    blocks = extract_text_blocks(pdf_path)
    if not blocks:
        print('No blocks found.')
        return
    
    num_pages = max(b['page_num'] for b in blocks) + 1
    doc_stats = get_document_stats(blocks)
    
    print(f'Total blocks: {len(blocks)}')
    print(f'Number of pages: {num_pages}')
    print(f'Document median font size: {doc_stats.get("median_size", 12.0):.2f}')
    
    # Analyze each block in detail
    print('\n=== Detailed Block Analysis ===')
    for i, block in enumerate(blocks):
        text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
        if not text:
            continue
            
        # Check if it's table text
        is_table = is_table_block(block, blocks, doc_stats)
        
        # Check heading classification
        numbered_heading = classify_numbered_heading(block, blocks, doc_stats)
        styled_heading = classify_styled_heading(block, doc_stats, blocks)
        heading_level = numbered_heading or styled_heading
        
        # Get block details
        x0, y0, x1, y1 = block['bbox']
        page_width = block.get('page_width', 595)
        page_height = block.get('page_height', 842)
        
        # Check if text contains "PAY + SI + NPA" or similar
        if "PAY" in text or "SI" in text or "NPA" in text:
            print(f'\n*** POTENTIAL TABLE TEXT FOUND ***')
            print(f'Block {i}: "{text}"')
            print(f'  BBox: ({x0:.2f}, {y0:.2f}, {x1:.2f}, {y1:.2f})')
            print(f'  Page width: {page_width}, x0: {x0:.2f}, x0/page_width: {x0/page_width:.3f}')
            print(f'  Is table block: {is_table}')
            print(f'  Heading level: {heading_level}')
            print(f'  Source: {block.get("source")}')
            
            # Check spacing
            lines = block.get('lines', [])
            if len(lines) >= 2:
                for j in range(len(lines) - 1):
                    current_line_bottom = lines[j]['bbox'][3]
                    next_line_top = lines[j + 1]['bbox'][1]
                    spacing = next_line_top - current_line_bottom
                    print(f'  Line {j} spacing: {spacing:.2f}')
        
        # Also check for numbered items that might be table headers
        if re.match(r'^\d+\.', text.strip()):
            print(f'\n*** NUMBERED ITEM FOUND ***')
            print(f'Block {i}: "{text}"')
            print(f'  BBox: ({x0:.2f}, {y0:.2f}, {x1:.2f}, {y1:.2f})')
            print(f'  Page width: {page_width}, x0: {x0:.2f}, x0/page_width: {x0/page_width:.3f}')
            print(f'  Is table block: {is_table}')
            print(f'  Heading level: {heading_level}')
            print(f'  Text length: {len(text)}')
    
    # Apply filtering and check results
    print('\n=== After Filtering ===')
    filtered_blocks = remove_headers_footers_tables(blocks, num_pages, doc_stats)
    print(f'Blocks after filtering: {len(filtered_blocks)}')
    
    # Check what headings remain after filtering
    print('\n=== Headings After Filtering ===')
    for i, block in enumerate(filtered_blocks):
        numbered_heading = classify_numbered_heading(block, filtered_blocks, doc_stats)
        styled_heading = classify_styled_heading(block, doc_stats, filtered_blocks)
        heading_level = numbered_heading or styled_heading
        
        if heading_level:
            text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
            print(f'{heading_level} | Block {i} | "{text}"')

if __name__ == '__main__':
    import re
    debug_file01() 