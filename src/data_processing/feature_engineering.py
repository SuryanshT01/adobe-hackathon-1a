import numpy as np
from typing import List, Dict, Any

def get_document_stats(blocks: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculates font size statistics across the document."""
    font_sizes = [span['size'] for block in blocks for line in block.get('lines', []) for span in line.get('spans', [])]
    if not font_sizes:
        return {'median_size': 12.0, 'std_dev_size': 1.0}
    return {
        'median_size': np.median(font_sizes),
        'std_dev_size': np.std(font_sizes) if len(font_sizes) > 1 else 1.0
    }

def create_feature_vector(block: Dict[str, Any], doc_stats: Dict[str, float]) -> Dict[str, Any]:
    """Creates a feature vector for a text block."""
    spans = [span for line in block.get('lines', []) for span in line.get('spans', [])]
    if not spans:
        return None

    full_text = " ".join(s['text'] for s in spans).strip()
    avg_font_size = np.mean([s['size'] for s in spans])
    features = {
        'font_size_ratio': avg_font_size / (doc_stats['median_size'] + 1e-6),
        'is_bold': any('bold' in s['font'].lower() for s in spans),
        'word_count': len(full_text.split()),
        'is_all_caps': full_text.isupper() and len(full_text) > 1,
        'x_position': block['bbox'][0],
        'y_position': block['bbox'][1],
        'block_width': block['bbox'][2] - block['bbox'][0],
        'block_height': block['bbox'][3] - block['bbox'][1]
    }
    return features