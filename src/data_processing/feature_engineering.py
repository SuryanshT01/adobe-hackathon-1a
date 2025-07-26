import numpy as np
from typing import List, Dict, Any, Optional

def create_feature_vector(
    block: Dict[str, Any], 
    doc_stats: Dict[str, float], 
    page_width: float, 
    page_height: float,
    prev_block: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Creates a numerical feature vector for a single text block, making it
    ready for the machine learning model.
    """
    # Ignore blocks from OCR as they lack reliable style metadata
    if block.get('source') == 'ocr':
        return None

    try:
        spans = [span for line in block.get('lines', []) for span in line.get('spans', [])]
        if not spans:
            return None

        full_text = " ".join(s.get('text', '').strip() for s in spans).strip()
        if not full_text:
            return None

        # --- Feature Calculation ---
        avg_font_size = np.mean([s.get('size', 12.0) for s in spans])
        x0, y0, x1, y1 = block['bbox']
        
        # Contextual feature: vertical space to the previous block
        space_above = y0 - prev_block['bbox'][1] if prev_block else y0

        features = {
            # Font-Based Features [4]
            'font_size_ratio': avg_font_size / (doc_stats.get('median_size', 12.0) + 1e-6),
            'is_bold': int(any('bold' in s.get('font', '').lower() for s in spans)),
            
            # Content-Based Features [4]
            'word_count': len(full_text.split()),
            'is_all_caps': int(full_text.isupper() and len(full_text) > 1),
            'is_title_case': int(full_text.istitle() and len(full_text) > 1),
            
            # Positional & Layout Features [5]
            'x_position_norm': x0 / page_width,
            'y_position_norm': y0 / page_height,
            'block_width_norm': (x1 - x0) / page_width,
            'block_height': y1 - y0,
            'space_above': space_above,
        }
        return features
    except (IndexError, KeyError, ZeroDivisionError):
        return None