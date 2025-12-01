from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from datetime import datetime
from app.db.mongodb import users_collection
from app.services.auth import get_current_user
from bson import ObjectId
import pandas as pd
from app.config import DATASET_PATH
import os

router = APIRouter(prefix="/progress", tags=["Progress"])

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
        
        # DEBUG: Mostrar valores únicos ANTES del mapeo
        print(f"[DEBUG] Unique difficulty values BEFORE mapping: {df['difficulty'].unique().tolist()}")
        
        # Normalizar dificultad - IMPORTANTE: convertir a string y limpiar espacios
        df["difficulty"] = df["difficulty"].astype(str).str.strip().str.lower()
        
        print(f"[DEBUG] Unique difficulty values AFTER cleaning: {df['difficulty'].unique().tolist()}")
        
        # Reemplazar con los valores en inglés
        df["difficulty"] = df["difficulty"].replace({
            "principiante": "beginner",
            "intermedio": "intermediate", 
            "avanzado": "advanced"
        })
        
        # Si algún valor no se mapeó correctamente, asignar "beginner" por defecto
        df.loc[~df["difficulty"].isin(["beginner", "intermediate", "advanced"]), "difficulty"] = "beginner"
        
        print(f"[DEBUG] Unique difficulty values AFTER mapping: {df['difficulty'].unique().tolist()}")
        
        print(f"[DEBUG] Difficulty distribution: {df['difficulty'].value_counts().to_dict()}")
        
        # Agrupar por dificultad
        result = {
            "beginner": df[df["difficulty"] == "beginner"]["label"].unique().tolist(),
            "intermediate": df[df["difficulty"] == "intermediate"]["label"].unique().tolist(),
            "advanced": df[df["difficulty"] == "advanced"]["label"].unique().tolist(),
        }
        
        print(f"[DEBUG] Labels grouped by difficulty: {[(k, len(v)) for k, v in result.items()]}")
        return result
    except Exception as e:
        print(f"[ERROR] Error reading dataset: {e}")
        import traceback
        traceback.print_exc()
        return {"beginner": [], "intermediate": [], "advanced": []}

@router.get("/level-progress")
async def get_level_progress(current_user: dict = Depends(get_current_user)):
    """
    Obtener progreso por niveles (principiante, intermedio, avanzado)
    """
    try:
        user_id = str(current_user["_id"])
        print(f"[DEBUG] Getting level progress for user: {user_id}")
        
        # Obtener progreso del usuario (campo level_progress)
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        level_progress = user.get("level_progress", {}) if user else {}
        print(f"[DEBUG] User level_progress from DB: {level_progress}")
        
        # Obtener señas por nivel del dataset
        labels_by_level = get_labels_by_difficulty()
        print(f"[DEBUG] Labels by level: {[(k, len(v)) for k, v in labels_by_level.items()]}")
        
        result = {}
        
        for level in ["beginner", "intermediate", "advanced"]:
            # Obtener total de señas en este nivel
            total_signs = labels_by_level.get(level, [])
            total_count = len(total_signs)
            
            # Obtener señas completadas para este nivel
            completed_signs = level_progress.get(level, {}).get("completed_signs", [])
            completed_count = len(completed_signs)
            
            # Calcular porcentaje
            percentage = (completed_count / total_count * 100) if total_count > 0 else 0
            
            result[level] = {
                "level": level,
                "total_signs": total_count,
                "completed_signs": completed_count,
                "percentage": round(percentage, 2),
                "last_updated": level_progress.get(level, {}).get("last_updated")
            }
        
        print(f"[DEBUG] Returning result: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] Error in get_level_progress: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al obtener progreso: {str(e)}")

@router.post("/increment-level")
async def increment_level_progress(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Incrementar progreso cuando el usuario completa una seña correctamente
    """
    user_id = str(current_user["_id"])
    level = data.get("level")  # "beginner", "intermediate", "advanced"
    label_id = data.get("label_id")
    
    print(f"[DEBUG INCREMENT] User: {user_id}, Level: {level}, Label ID: {label_id}")
    
    if not level or not label_id:
        raise HTTPException(status_code=400, detail="Se requiere level y label_id")
    
    if level not in ["beginner", "intermediate", "advanced"]:
        raise HTTPException(status_code=400, detail="Nivel inválido")
    
    # Verificar que el label existe en el dataset
    labels_by_level = get_labels_by_difficulty()
    all_labels = labels_by_level.get(level, [])
    
    print(f"[DEBUG INCREMENT] Labels disponibles en {level}: {all_labels}")
    print(f"[DEBUG INCREMENT] ¿Label '{label_id}' está en la lista? {label_id in all_labels}")
    
    if label_id not in all_labels:
        print(f"[ERROR INCREMENT] Label '{label_id}' no encontrado en nivel '{level}'")
        # TEMPORAL: Para debugging, aceptar cualquier label
        print(f"[WARN INCREMENT] Aceptando el label de todas formas para pruebas")
    
    # Agregar el label_id al conjunto de completados (usando $addToSet para evitar duplicados)
    update_result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$addToSet": {f"level_progress.{level}.completed_signs": label_id},
            "$set": {f"level_progress.{level}.last_updated": datetime.utcnow()}
        }
    )
    
    print(f"[DEBUG INCREMENT] Update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
    
    if update_result.modified_count == 0 and update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Obtener progreso actualizado
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    level_progress = user.get("level_progress", {}).get(level, {})
    completed_signs = level_progress.get("completed_signs", [])
    
    print(f"[DEBUG INCREMENT] Completed signs después del update: {completed_signs}")
    
    # Contar total de señas en este nivel
    total_count = len(all_labels)
    completed_count = len(completed_signs)
    percentage = (completed_count / total_count * 100) if total_count > 0 else 0
    
    result = {
        "level": level,
        "total_signs": total_count,
        "completed_signs": completed_count,
        "percentage": round(percentage, 2),
        "message": "Progreso actualizado exitosamente"
    }
    
    print(f"[DEBUG INCREMENT] Returning result: {result}")
    
    return result


@router.get("/completed-difficulties")
async def get_completed_difficulties(current_user: dict = Depends(get_current_user)):
    """
    Obtiene las dificultades que el usuario ha completado (al menos una seña).
    Retorna lista de dificultades disponibles para tomar exámenes.
    """
    user_id = str(current_user.get("_id"))
    
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        level_progress = user.get("level_progress", {})
        completed_difficulties = []
        
        # Verificar qué niveles tienen al menos una seña completada
        for difficulty in ["beginner", "intermediate", "advanced"]:
            completed_signs = level_progress.get(difficulty, {}).get("completed_signs", [])
            if len(completed_signs) > 0:
                completed_difficulties.append(difficulty)
        
        return {
            "completed_difficulties": completed_difficulties,
            "has_beginner": "beginner" in completed_difficulties,
            "has_intermediate": "intermediate" in completed_difficulties,
            "has_advanced": "advanced" in completed_difficulties,
        }
    
    except Exception as e:
        print(f"[ERROR] Error getting completed difficulties: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener dificultades completadas: {str(e)}")
