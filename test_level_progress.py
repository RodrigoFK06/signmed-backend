"""
Script de prueba para verificar la función get_labels_by_difficulty
"""
import pandas as pd
from app.config import DATASET_PATH
import os

def get_labels_by_difficulty():
    """
    Obtiene las señas del dataset agrupadas por dificultad
    """
    dataset_path = str(DATASET_PATH)
    print(f"[DEBUG] Reading dataset from: {dataset_path}")
    
    if not os.path.exists(dataset_path):
        print(f"[ERROR] Dataset not found at: {dataset_path}")
        return {"beginner": [], "intermediate": [], "advanced": []}
    
    try:
        df = pd.read_csv(dataset_path, header=None)
        print(f"[DEBUG] Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        
        if df.empty or df.shape[1] < 3:
            print(f"[ERROR] Dataset is empty or has insufficient columns")
            return {"beginner": [], "intermediate": [], "advanced": []}
        
        # Columna -2 es el label, columna -1 es la dificultad
        df.columns = [*[f"col_{i}" for i in range(df.shape[1] - 2)], "label", "difficulty"]
        
        # DEBUG: Mostrar valores únicos de dificultad ANTES del mapeo
        print(f"[DEBUG] Unique difficulty values BEFORE mapping: {df['difficulty'].unique().tolist()}")
        print(f"[DEBUG] Difficulty data type: {df['difficulty'].dtype}")
        
        # Normalizar dificultad - IMPORTANTE: convertir a string primero
        df["difficulty"] = df["difficulty"].astype(str).str.strip().str.lower()
        
        print(f"[DEBUG] Unique difficulty values AFTER str conversion: {df['difficulty'].unique().tolist()}")
        
        df["difficulty"] = df["difficulty"].replace({
            "principiante": "beginner",
            "intermedio": "intermediate", 
            "avanzado": "advanced"
        })
        
        print(f"[DEBUG] Unique difficulty values AFTER mapping: {df['difficulty'].unique().tolist()}")
        
        print(f"[DEBUG] Difficulty distribution: {df['difficulty'].value_counts().to_dict()}")
        print(f"[DEBUG] Sample labels: {df['label'].head().tolist()}")
        
        # Agrupar por dificultad
        result = {
            "beginner": df[df["difficulty"] == "beginner"]["label"].unique().tolist(),
            "intermediate": df[df["difficulty"] == "intermediate"]["label"].unique().tolist(),
            "advanced": df[df["difficulty"] == "advanced"]["label"].unique().tolist(),
        }
        
        print(f"[DEBUG] Labels grouped by difficulty:")
        for level, labels in result.items():
            print(f"  {level}: {len(labels)} labels - {labels[:5]}...")
        
        return result
    except Exception as e:
        print(f"[ERROR] Error reading dataset: {e}")
        import traceback
        traceback.print_exc()
        return {"beginner": [], "intermediate": [], "advanced": []}

if __name__ == "__main__":
    print("Testing get_labels_by_difficulty()...")
    result = get_labels_by_difficulty()
    print("\n✅ Test completed successfully!")
    print(f"Total labels by level: {[(k, len(v)) for k, v in result.items()]}")
