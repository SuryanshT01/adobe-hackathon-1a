import os
from src.data_processing.pdf_parser import extract_text_blocks

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
        print(f'  Total blocks: {len(blocks)}')
        if blocks:
            # Print a summary of the first 2 blocks
            for i, block in enumerate(blocks[:2]):
                print(f'  Block {i+1}:')
                print(f'    Page: {block.get("page_num")}, BBox: {block.get("bbox")}, Lines: {len(block.get("lines", []))}')
                # Print first line's text if available
                if block.get('lines'):
                    first_line = block['lines'][0]
                    if first_line.get('spans'):
                        print(f'    First line text: {first_line["spans"][0]["text"][:80]}')
        else:
            print('  No text blocks found.')

if __name__ == '__main__':
    main() 