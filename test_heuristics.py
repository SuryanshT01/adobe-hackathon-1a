import os
from src.data_processing.pdf_parser import extract_text_blocks
from src.data_processing.heuristics import find_title, classify_numbered_heading, classify_styled_heading, remove_headers_footers_tables, get_document_stats

PDF_DIR = 'data/raw_pdfs'

def main():
    pdf_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print('No PDF files found in', PDF_DIR)
        return
    for pdf in pdf_files:
        pdf_path = os.path.join(PDF_DIR, pdf)
        print(f'\nProcessing: {pdf}')
        blocks = extract_text_blocks(pdf_path)
        if not blocks:
            print('  No blocks found.')
            continue
        num_pages = max(b['page_num'] for b in blocks) + 1
        sources = set()
        for block in blocks:
            if block['page_num'] == 0 and block.get('type') == 0:
                for line in block.get('lines', []):
                    y0 = line['bbox'][1]
                    if y0 < 250:
                        sources.add(block.get('source'))
        print(f'  Sources used for title extraction: {sources}')
        # Print extracted title
        title = find_title(blocks)
        print(f'  Extracted Title: {title}')
        # Compute doc stats for heading and header/footer/table filtering
        doc_stats = get_document_stats(blocks)
        # Test remove_headers_footers_tables (includes table text exclusion)
        filtered_blocks = remove_headers_footers_tables(blocks, num_pages, doc_stats)
        print(f'  Blocks after header/footer/table filter: {len(filtered_blocks)} (was {len(blocks)})')
        # Print all detected headings (H1, H2, H3) in filtered blocks
        print('  Detected Headings:')
        for i, block in enumerate(filtered_blocks):
            heading_level = classify_numbered_heading(block, filtered_blocks, doc_stats)
            if not heading_level:
                heading_level = classify_styled_heading(block, doc_stats, filtered_blocks)
            if heading_level:
                text = " ".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', []))
                print(f'    {heading_level} | Page {block.get("page_num")} | {text[:80]}')

if __name__ == '__main__':
    main() 