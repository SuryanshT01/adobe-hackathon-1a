import fitz  # PyMuPDF
from typing import List, Dict, Any
import pytesseract
from PIL import Image
import io

def is_scanned_page(page: fitz.Page) -> bool:
    """
    Determines if a page is likely scanned by checking for a low number of
    text blocks. A page with fewer than 3 text blocks is a strong indicator
    of being an image-based or scanned page.
    """
    return len(page.get_text("blocks")) < 3

def ocr_page_to_blocks(page: fitz.Page, page_num: int) -> List[Dict[str, Any]]:
    """
    Performs OCR on a page image and reconstructs the output into a block
    structure that mimics PyMuPDF's output, including positional data.
    """
    print(f"[INFO] OCR triggered for page {page_num}.")
    final_blocks = []
    try:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        if not ocr_data or not ocr_data.get('text'):
            return []
        lines_in_block = {}
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            if not text:
                continue
            block_num = ocr_data['block_num'][i]
            line_num = ocr_data['line_num'][i]
            x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
            word_bbox = (x, y, x + w, y + h)
            span = {
                'text': text + " ",
                'size': 12.0,
                'font': 'OCR-Default',
                'bbox': word_bbox
            }
            key = (block_num, line_num)
            if key not in lines_in_block:
                lines_in_block[key] = {'spans': [], 'bbox': list(word_bbox)}
            lines_in_block[key]['spans'].append(span)
            # Expand line bbox
            lines_in_block[key]['bbox'][0] = min(lines_in_block[key]['bbox'][0], word_bbox[0])
            lines_in_block[key]['bbox'][1] = min(lines_in_block[key]['bbox'][1], word_bbox[1])
            lines_in_block[key]['bbox'][2] = max(lines_in_block[key]['bbox'][2], word_bbox[2])
            lines_in_block[key]['bbox'][3] = max(lines_in_block[key]['bbox'][3], word_bbox[3])
        for (block_num, line_num), line_data in lines_in_block.items():
            final_blocks.append({
                'type': 0,
                'bbox': tuple(line_data['bbox']),
                'page_num': page_num,
                'source': 'ocr',
                'lines': [{
                    'spans': line_data['spans'],
                    'bbox': tuple(line_data['bbox'])
                }]
            })
        return final_blocks
    except Exception as e:
        print(f" OCR failed for page {page_num}: {e}")
        return []

def extract_text_blocks(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extracts all text blocks from a PDF. It now checks EVERY page to see if
    it is scanned and applies OCR as needed.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF {pdf_path}: {e}")
        return []
    all_blocks = []
    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        if is_scanned_page(page):
            ocr_blocks = ocr_page_to_blocks(page, page_num)
            if ocr_blocks:
                for block in ocr_blocks:
                    block['page_height'] = page_height
                all_blocks.extend(ocr_blocks)
        else:
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get('type') == 0 and 'lines' in block:
                    block['page_num'] = page_num
                    block['source'] = 'pymupdf'
                    block['page_height'] = page_height
                    all_blocks.append(block)
    doc.close()
    return all_blocks