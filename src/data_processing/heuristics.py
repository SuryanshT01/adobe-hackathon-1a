import re
from typing import List, Dict, Any, Optional
from collections import Counter

def get_document_stats(blocks: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculates statistics (median font size) across the document."""
    font_sizes = []
    for block in blocks:
        if block.get('source') == 'ocr': continue
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                font_sizes.append(span.get('size', 0))
    if not font_sizes:
        return {'median_size': 12.0}
    return {'median_size': sorted(font_sizes)[len(font_sizes) // 2]}

def find_title(blocks: List[Dict[str, Any]]) -> str:
    """
    A highly robust heuristic to find the document title. It scores lines on
    the first page and intelligently combines the best candidates into a
    multi-line title if necessary.
    """
    first_page_blocks = [b for b in blocks if b.get('page_num') == 0 and b.get('type') == 0]
    if not first_page_blocks:
        return ""
    candidate_lines = []
    max_font_size = 0
    for block in first_page_blocks:
        if block.get('source') == 'ocr': continue
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                max_font_size = max(max_font_size, span.get('size', 0))
    for block in first_page_blocks:
        if block['bbox'][1] > 400: continue
        for line in block.get('lines', []):
            text = " ".join(s['text'].strip() for s in line.get('spans', []) if s['text'].strip()).strip()
            if not text or len(text) < 3:
                continue
            lower_text = text.lower()
            if any(keyword in lower_text for keyword in ['date:', 'time:', 'address:', 'tel:', 'fax:', 'version', 'page', 'confidential']):
                continue
            if re.match(r'^[~\s]+', text) or text.isdigit():
                continue
            avg_font_size = sum(s['size'] for s in line['spans']) / len(line['spans']) if line['spans'] else 0
            score = 0
            if avg_font_size >= max_font_size * 0.9: score += 5
            elif avg_font_size > max_font_size * 0.7: score += 2
            if any('bold' in s.get('font', '').lower() for s in line.get('spans', [])): score += 2
            if len(text.split()) < 15: score += 1
            if text.isupper() or text.istitle(): score += 1
            candidate_lines.append({'text': text, 'score': score, 'y0': line['bbox'][1], 'size': avg_font_size})
    if not candidate_lines:
        return ""
    candidate_lines.sort(key=lambda x: (x['score'], -x['y0']), reverse=True)
    best_candidate = candidate_lines[0]
    title_parts = [best_candidate]
    for cand in candidate_lines[1:]:
        if cand['score'] >= best_candidate['score'] - 2:
            if abs(cand['y0'] - title_parts[-1]['y0']) < best_candidate['size'] * 2:
                title_parts.append(cand)
    title_parts.sort(key=lambda x: x['y0'])
    return " ".join(p['text'] for p in title_parts).replace('  ', ' ').strip()

def classify_numbered_heading(block: Dict[str, Any]) -> Optional[str]:
    """
    Classifies a block as H1, H2, or H3 if it starts with a hierarchical
    numbering pattern (e.g., "1.", "1.1", "1.1.1.").
    """
    full_text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
    match = re.match(r'^\s*(\d+(\.\d+)*)\.?\s+', full_text)
    if match:
        num_str = match.group(1)
        level = num_str.count('.') + 1
        if 1 <= level <= 3:
            return f"H{level}"
    return None

def classify_styled_heading(block: Dict[str, Any], doc_stats: Dict[str, float]) -> Optional[str]:
    """
    Classifies a block as a heading based on styling cues like font size,
    boldness, word count, and text case.
    """
    if block.get('source') == 'ocr': return None
    text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
    word_count = len(text.split())
    if not (1 <= word_count < 25) or text.endswith(('.', ':', ',')):
        return None
    try:
        avg_font_size = sum(s['size'] for line in block['lines'] for s in line['spans']) / sum(len(line['spans']) for line in block['lines'])
        is_bold = any('bold' in s.get('font', '').lower() for line in block['lines'] for s in line['spans'])
    except (ZeroDivisionError, KeyError):
        return None
    median_size = doc_stats.get('median_size', 12.0)
    if avg_font_size > median_size * 1.4 and (is_bold or text.isupper()):
        return "H1"
    if avg_font_size > median_size * 1.2 and (is_bold or text.isupper()):
        return "H2"
    if (avg_font_size > median_size * 1.1 and is_bold) or (avg_font_size > median_size * 1.25 and text.istitle()):
        return "H3"
    return None

def filter_headers_footers(blocks: List[Dict[str, Any]], num_pages: int, doc_stats: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Filters out headers and footers by identifying text that repeats across
    many pages, but now ignores text with large fonts to protect headings.
    """
    if num_pages < 3:
        return blocks
    potential_hf = Counter()
    median_size = doc_stats.get('median_size', 12.0)
    for block in blocks:
        text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip().lower()
        if not (2 < len(text) < 80) or text.isdigit():
            continue
        if block.get('source') != 'ocr':
            avg_font_size = sum(s['size'] for l in block['lines'] for s in l['spans']) / sum(len(l['spans']) for l in block['lines'])
            if avg_font_size > median_size * 1.2:
                continue
        y0 = block['bbox'][1]
        page_height = block.get('page_height', 842)
        pos_key = "header" if y0 < page_height * 0.15 else "footer" if y0 > page_height * 0.85 else None
        if pos_key:
            potential_hf[(text, pos_key)] += 1
    hf_signatures = {key for key, count in potential_hf.items() if count >= num_pages * 0.5}
    final_blocks = []
    for block in blocks:
        text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip().lower()
        y0 = block['bbox'][1]
        page_height = block.get('page_height', 842)
        pos_key = "header" if y0 < page_height * 0.15 else "footer" if y0 > page_height * 0.85 else None
        if (text, pos_key) not in hf_signatures:
            final_blocks.append(block)
    return final_blocks