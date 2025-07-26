import joblib
import pandas as pd
from typing import List, Dict, Any

class StructurePredictor:
    """
    A wrapper class for the LightGBM model to handle loading and prediction
    for document structure classification.
    """
    def __init__(self, model_path: str, encoder_path: str):
        """
        Initializes the predictor by loading the trained model and label encoder.
        """
        self.model = None
        self.encoder = None
        try:
            self.model = joblib.load(model_path)
            self.encoder = joblib.load(encoder_path)
        except FileNotFoundError:
            print(f"Warning: Model or encoder not found. Searched paths:")
            print(f"Model: {model_path}")
            print(f"Encoder: {encoder_path}")
            print("ML classification will be skipped. Please train the model first.")
        except Exception as e:
            print(f"An error occurred while loading the model or encoder: {e}")

    def predict(self, feature_vectors: List[Dict[str, Any]]) -> List[str]:
        """
        Predicts the class labels for a list of feature vectors.
        """
        if not self.model or not self.encoder or not feature_vectors:
            return [None] * len(feature_vectors)
        
        df = pd.DataFrame(feature_vectors)
        # Ensure the DataFrame columns are in the same order as during training
        if hasattr(self.model, 'feature_name_'):
            feature_names = list(self.model.feature_name_)
            df = df[[col for col in feature_names if col in df.columns]]
        predictions_encoded = self.model.predict(df)
        predictions = self.encoder.inverse_transform(predictions_encoded)
        return predictions.tolist()