from typing import List, Dict, Any

def validate_hierarchy(headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enforces a logical heading hierarchy (e.g., an H2 must follow an H1 or
    another H2). It demotes headings that skip a level and converts H4 to H3.
    """
    if not headings:
        return []

    validated_headings = []
    # last_level starts at 0, representing the level before the first H1.
    last_level = 0
    
    for heading in headings:
        # Extract the numeric level from the label (e.g., 'H1' -> 1)
        current_level = int(heading['level'].replace('H', ''))
        
        # Convert H4 to H3 (since we only support H1, H2, H3)
        if current_level == 4:
            current_level = 3
            heading['level'] = 'H3'
        
        # If the current heading skips a level (e.g., H1 -> H3),
        # demote it to the next logical level.
        if current_level > last_level + 1:
            new_level = last_level + 1
            heading['level'] = f"H{new_level}"
            current_level = new_level
            
        validated_headings.append(heading)
        last_level = current_level
        
    return validated_headings