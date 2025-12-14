import os
import sys
from pathlib import Path
import joblib
import pandas as pd

# Mock the path logic from ml.py
BASE_DIR = Path("/Users/terrelnuentsa/Documents/Projets/Banquise/scoring")
MODEL_PATH = BASE_DIR / "model_credit.pkl"

print(f"Checking model at: {MODEL_PATH}")

if not MODEL_PATH.exists():
    print("ERROR: Model file does not exist!")
    sys.exit(1)

print(f"File size: {MODEL_PATH.stat().st_size} bytes")

try:
    artifact = joblib.load(MODEL_PATH)
    print("Model loaded successfully via joblib.")
    print("Keys in artifact:", artifact.keys())
    
    if "pipeline" not in artifact or "features" not in artifact:
        print("ERROR: Invalid artifact structure.")
    else:
        print("Artifact valid.")
        
except Exception as e:
    print(f"ERROR loading model: {e}")
    import traceback
    traceback.print_exc()
