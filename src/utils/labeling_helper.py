import pandas as pd
import os

def create_labeling_template(csv_path: str, output_path: str = None):
    """
    Creates a template for manual labeling with helpful information.
    
    Args:
        csv_path: Path to the features CSV file
        output_path: Path to save the labeled template (optional)
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
    
    df = pd.read_csv(csv_path)
    
    # Add a label column with instructions
    df['label'] = ''  # Empty column for manual labeling
    
    # Add helpful columns for labeling
    df['labeling_notes'] = ''
    df['confidence'] = ''
    
    # Reorder columns to make labeling easier
    label_columns = ['label', 'labeling_notes', 'confidence', 'pdf_file', 'page_num', 'text_preview']
    feature_columns = [col for col in df.columns if col not in label_columns]
    
    df_labeling = df[label_columns + feature_columns]
    
    if output_path is None:
        output_path = csv_path.replace('.csv', '_for_labeling.csv')
    
    df_labeling.to_csv(output_path, index=False)
    
    print(f"Labeling template created: {output_path}")
    print("\nLabeling Guidelines:")
    print("- H1: Main headings (largest, most prominent)")
    print("- H2: Section headings (medium prominence)")
    print("- H3: Subsection headings (smaller prominence)")
    print("- Body_Text: Regular paragraph text")
    print("\nTips:")
    print("- Look at font_size_ratio, is_bold, and text_preview")
    print("- Consider word_count and text case")
    print("- Use labeling_notes to record your reasoning")
    print("- Use confidence (1-5) to indicate your certainty")

def validate_labels(csv_path: str):
    """
    Validates the labeled data for common issues.
    
    Args:
        csv_path: Path to the labeled CSV file
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
    
    df = pd.read_csv(csv_path)
    
    if 'label' not in df.columns:
        print("Error: No 'label' column found")
        return
    
    # Check for empty labels
    empty_labels = df['label'].isna().sum()
    if empty_labels > 0:
        print(f"Warning: {empty_labels} rows have empty labels")
    
    # Check label distribution
    print("\nLabel distribution:")
    print(df['label'].value_counts())
    
    # Check for invalid labels
    valid_labels = ['H1', 'H2', 'H3', 'Body_Text']
    invalid_labels = df[~df['label'].isin(valid_labels)]['label'].unique()
    if len(invalid_labels) > 0:
        print(f"\nWarning: Invalid labels found: {invalid_labels}")
    
    # Check for potential issues
    print("\nPotential issues to check:")
    
    # Very short text labeled as headings
    short_headings = df[(df['word_count'] < 2) & (df['label'].str.startswith('H', na=False))]
    if len(short_headings) > 0:
        print(f"- {len(short_headings)} headings with < 2 words")
    
    # Very long text labeled as headings
    long_headings = df[(df['word_count'] > 20) & (df['label'].str.startswith('H', na=False))]
    if len(long_headings) > 0:
        print(f"- {len(long_headings)} headings with > 20 words")
    
    # Low font size labeled as headings
    small_headings = df[(df['font_size_ratio'] < 1.0) & (df['label'].str.startswith('H', na=False))]
    if len(small_headings) > 0:
        print(f"- {len(small_headings)} headings with font_size_ratio < 1.0")

if __name__ == "__main__":
    # Example usage
    csv_path = "../data/training/features_for_labeling.csv"
    
    if os.path.exists(csv_path):
        print("Creating labeling template...")
        create_labeling_template(csv_path)
        
        print("\nTo validate labels after manual labeling:")
        print("python labeling_helper.py validate")
    else:
        print(f"Features file not found at {csv_path}")
        print("Please run the feature generation notebook first.") 