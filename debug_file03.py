import os
from src.data_processing.pdf_parser import extract_text_blocks

def debug_file03():
    pdf_path = 'data/raw_pdfs/file03.pdf'
    blocks = extract_text_blocks(pdf_path)
    if not blocks:
        print('No blocks found.')
        return
    print('First page blocks:')
    for i, block in enumerate(blocks):
        if block.get('page_num', 0) == 0 and block.get('type', 0) == 0:
            text = " ".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', []))
            print(f'Block {i}: source={block.get("source")}, bbox={block["bbox"]}')
            print(f'  Text: {text}')
            print('-' * 60)

if __name__ == '__main__':
    debug_file03() 