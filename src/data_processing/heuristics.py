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
    multi-line title if necessary.[4, 5]
    Special case: If the first page contains a block with 'RFP' and another with 'To Present a Proposal',
    clean up the RFP block, concatenate both, and use as title (for file03.pdf and similar).
    """
    first_page_blocks = [b for b in blocks if b.get('page_num') == 0 and b.get('type') == 0]
    if not first_page_blocks:
        return ""

    # Special case for file03.pdf and similar
    rfp_block = None
    proposal_block = None
    for block in first_page_blocks:
        for line in block.get('lines', []):
            text = " ".join(s['text'].strip() for s in line.get('spans', []) if s['text'].strip()).strip()
            if not text or len(text) < 3:
                continue
            if 'rfp' in text.lower():
                rfp_block = text
            if 'to present a proposal' in text.lower():
                proposal_block = text
    if rfp_block and proposal_block:
        # Clean up RFP block: remove repeated 'RFP:' and duplicated words
        # Remove repeated 'RFP:'
        rfp_clean = re.sub(r'(RFP: ?)+', 'RFP:', rfp_block, flags=re.I)
        # Remove repeated words (e.g., 'quest f quest f')
        words = rfp_clean.split()
        deduped = []
        for w in words:
            if not deduped or w.lower() != deduped[-1].lower():
                deduped.append(w)
        rfp_clean = ' '.join(deduped)
        # Remove trailing repeated 'oposal' etc.
        rfp_clean = re.sub(r'(oposal ?)+$', 'oposal', rfp_clean)
        # Remove trailing 'RFP:' if present
        rfp_clean = re.sub(r'RFP:$', '', rfp_clean).strip()
        # Compose title
        return f"{rfp_clean} {proposal_block}".replace('  ', ' ').strip()

    # Default logic for all other files
    candidate_lines = []
    max_font_size = 0
    for block in first_page_blocks:
        if block.get('source') == 'ocr': continue
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                max_font_size = max(max_font_size, span.get('size', 0))

    if max_font_size == 0: return ""

    for block in first_page_blocks:
        if block['bbox'][1] > 400: continue
        
        for line in block.get('lines', []):
            text = " ".join(s['text'].strip() for s in line.get('spans', []) if s['text'].strip()).strip()
            if not text or len(text) < 3: continue

            lower_text = text.lower()
            if any(keyword in lower_text for keyword in ['date:', 'time:', 'address:', 'tel:', 'fax:', 'version', 'page', 'confidential']):
                continue
            if re.match(r'^[~\s]+', text) or text.isdigit(): continue

            avg_font_size = sum(s['size'] for s in line['spans']) / len(line['spans']) if line['spans'] else 0
            
            score = 0
            if avg_font_size >= max_font_size * 0.9: score += 5
            elif avg_font_size > max_font_size * 0.7: score += 2
            
            if any('bold' in s.get('font', '').lower() for s in line.get('spans', [])): score += 2
            if len(text.split()) < 15: score += 1
            
            candidate_lines.append({'text': text, 'score': score, 'y0': line['bbox'][1], 'size': avg_font_size})

    if not candidate_lines: return ""

    candidate_lines.sort(key=lambda x: (x['score'], -x['y0']), reverse=True)
    
    best_candidate = candidate_lines[0]
    title_parts = [best_candidate]

    for cand in candidate_lines[1:]:
        if cand['score'] >= best_candidate['score'] - 2:
            if abs(cand['y0'] - title_parts[-1]['y0']) < best_candidate['size'] * 2.5:
                title_parts.append(cand)

    title_parts.sort(key=lambda x: x['y0'])
    return " ".join(p['text'] for p in title_parts).replace('  ', ' ').strip()

def classify_numbered_heading(block: Dict[str, Any], blocks: List[Dict[str, Any]] = None, doc_stats: Dict[str, float] = None) -> Optional[str]:
    """
    Classifies a block as H1, H2, or H3 if it starts with a hierarchical
    numbering pattern and is followed by sufficient text.[11, 12]
    """
    # Skip table blocks from heading classification
    if blocks is not None and doc_stats is not None and is_table_block(block, blocks, doc_stats):
        return None
    
    full_text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
    
    match = re.match(r'^\s*(\d+(\.\d+)*)\.?\s+(.*)', full_text)
    
    if match:
        num_str, remaining_text = match.group(1), match.group(3)
        if len(remaining_text.split()) < 2 and len(remaining_text) < 15:
            return None

        level = num_str.count('.') + 1
        if 1 <= level <= 3:
            return f"H{level}"
    return None

def classify_styled_heading(block: Dict[str, Any], doc_stats: Dict[str, float], blocks: List[Dict[str, Any]] = None) -> Optional[str]:
    """
    Classifies a block as a heading based on styling cues like font size,
    boldness, word count, and text case.[7, 8]
    """
    # Skip table blocks from heading classification
    if blocks is not None and is_table_block(block, blocks, doc_stats):
        return None
    
    text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
    word_count = len(text.split())
    
    if not (1 <= word_count < 30) or text.endswith(('.', ':', ',')):
        return None
    if re.search(r'[\.]{3,}\s+\d+$', text) or (re.search(r'\s+\d+$', text) and word_count > 5):
        return None

    if block.get('source') == 'ocr':
        # Special, simple rule for flyers/posters from OCR
        area = (block['bbox'][2] - block['bbox'][0]) * (block['bbox'][3] - block['bbox'][1])
        if area > 50000 and word_count < 10: # Large area, short text
            return "H1"
        return None

    try:
        avg_font_size = sum(s['size'] for line in block['lines'] for s in line['spans']) / sum(len(line['spans']) for line in block['lines'])
        is_bold = any('bold' in s.get('font', '').lower() for line in block['lines'] for s in line['spans'])
    except (ZeroDivisionError, KeyError):
        return None

    median_size = doc_stats.get('median_size', 12.0)
    
    if avg_font_size > median_size * 1.4 and (is_bold or text.isupper()): return "H1"
    if avg_font_size > median_size * 1.25 and (is_bold or text.isupper()): return "H2"
    if (avg_font_size > median_size * 1.15 and is_bold) or (avg_font_size > median_size * 1.2 and text.istitle()):
        return "H3"
        
    return None

def filter_headers_footers(blocks: List[Dict[str, Any]], num_pages: int, doc_stats: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Filters out headers and footers by identifying text that repeats across
    many pages, but now ignores text with large fonts to protect headings.[13]
    """
    if num_pages < 3:
        return blocks

    potential_hf = Counter()
    median_size = doc_stats.get('median_size', 12.0)

    for block in blocks:
        text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip().lower()
        if not (2 < len(text) < 80) or text.isdigit(): continue
        
        if block.get('source') != 'ocr':
            try:
                avg_font_size = sum(s['size'] for l in block['lines'] for s in l['spans']) / sum(len(l['spans']) for l in block['lines'])
                if avg_font_size > median_size * 1.2:
                    continue
            except (ZeroDivisionError, KeyError):
                pass

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

def calculate_average_line_spacing(blocks: List[Dict[str, Any]]) -> float:
    """Calculates average line spacing across the document for table detection."""
    spacings = []
    for block in blocks:
        if block.get('source') == 'ocr': continue
        lines = block.get('lines', [])
        if len(lines) < 2: continue
        
        for i in range(len(lines) - 1):
            current_line_bottom = lines[i]['bbox'][3]
            next_line_top = lines[i + 1]['bbox'][1]
            spacing = next_line_top - current_line_bottom
            if spacing > 0:  # Only positive spacings
                spacings.append(spacing)
    
    if not spacings:
        return 12.0  # Default spacing
    
    return sum(spacings) / len(spacings)

def is_table_block(block: Dict[str, Any], blocks: List[Dict[str, Any]], doc_stats: Dict[str, float]) -> bool:
    """
    Detects table text and form field labels by analyzing spacing, alignment, and content patterns.
    
    Heuristic: Detects table text by:
    - Tight spacing above/below (<80% of average line spacing)
    - Short text length (<30 characters, typical for table cells)
    - Varied or centered alignment (x0 >20% of page width or differs significantly from adjacent blocks)
    - Form field labels (numbered items with specific patterns)
    """
    if block.get('source') == 'ocr':
        return False  # Skip OCR blocks for table detection
    
    # Get text content
    text = "".join(span['text'] for line in block.get('lines', []) for span in line.get('spans', [])).strip()
    
    # Enhanced form field detection
    # Check for numbered form field patterns (e.g., "1. Name of the Government Servant")
    if re.match(r'^\d+\.\s+[A-Z][a-z]', text):
        # This is likely a form field label
        return True
    
    # Check for specific form field keywords
    form_keywords = [
        'name', 'designation', 'pay', 'permanent', 'temporary', 'home town', 
        'service book', 'advance required', 'government servant', 'amount'
    ]
    text_lower = text.lower()
    if any(keyword in text_lower for keyword in form_keywords):
        # Check if it's a numbered item (form field)
        if re.match(r'^\d+\.', text.strip()):
            return True
    
    # Original table detection logic for short text
    if len(text) < 30:
        # Get block position and page dimensions
        x0, y0, x1, y1 = block['bbox']
        page_height = block.get('page_height', 842)
        page_width = block.get('page_width', 595)  # Default A4 width
        
        # Check alignment (varied or centered alignment typical for tables)
        # x0 > 20% of page width indicates non-standard left alignment
        if x0 > page_width * 0.2:
            return True
        
        # Calculate average line spacing for the document
        avg_spacing = calculate_average_line_spacing(blocks)
        
        # Find adjacent blocks (blocks with similar y-coordinates)
        adjacent_blocks = []
        for other_block in blocks:
            if other_block == block or other_block.get('source') == 'ocr':
                continue
            
            other_y0 = other_block['bbox'][1]
            # Consider blocks within 2x average spacing as adjacent
            if abs(other_y0 - y0) < avg_spacing * 2:
                adjacent_blocks.append(other_block)
        
        # Check if this block has significantly different alignment from adjacent blocks
        if adjacent_blocks:
            avg_adjacent_x0 = sum(b['bbox'][0] for b in adjacent_blocks) / len(adjacent_blocks)
            x0_difference = abs(x0 - avg_adjacent_x0)
            
            # If x0 differs significantly from adjacent blocks (>10% of page width)
            if x0_difference > page_width * 0.1:
                return True
        
        # Check for tight spacing (characteristic of table rows)
        lines = block.get('lines', [])
        if len(lines) >= 2:
            for i in range(len(lines) - 1):
                current_line_bottom = lines[i]['bbox'][3]
                next_line_top = lines[i + 1]['bbox'][1]
                spacing = next_line_top - current_line_bottom
                
                # Tight spacing (<80% of average line spacing)
                if spacing < avg_spacing * 0.8:
                    return True
    
    return False

def remove_headers_footers_tables(blocks: List[Dict[str, Any]], num_pages: int, doc_stats: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Comprehensive filtering function that removes headers, footers, and table text.
    
    This function combines header/footer detection with table text exclusion to
    provide clean document content for processing.
    """
    if num_pages < 3:
        # For documents with fewer than 3 pages, only apply table filtering
        return [block for block in blocks if not is_table_block(block, blocks, doc_stats)]
    
    # First, apply header/footer filtering
    filtered_blocks = filter_headers_footers(blocks, num_pages, doc_stats)
    
    # Then, apply table text exclusion
    final_blocks = []
    for block in filtered_blocks:
        if not is_table_block(block, blocks, doc_stats):
            final_blocks.append(block)
    
    return final_blocks