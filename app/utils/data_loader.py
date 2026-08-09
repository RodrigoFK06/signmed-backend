# app/utils/data_loader.py
import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from app.config import DATASET_PATH, FRAMES, MIN_SAMPLES_PER_CLASS, RANDOM_STATE, TEST_SIZE

def _infer_features_per_frame(num_cols: int) -> int:
    """
    Dado el número total de columnas del CSV (incluye label y level),
    calcula cuántas features hay por frame.
    Estructura: (FRAMES * n_features) + 2 (label, level)
    """
    n_total_feats = num_cols - 2
    if n_total_feats <= 0 or n_total_feats % FRAMES != 0:
        raise ValueError(
            f"Estructura inválida: total_cols={num_cols} -> "
            f"(total_cols-2) % {FRAMES} != 0. Revisa que el CSV tenga 35*features + 2 columnas."
        )
    return n_total_feats // FRAMES

def load_dataset(
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
    min_samples_per_class: int = MIN_SAMPLES_PER_CLASS,
):
    """
    Carga el dataset y descarta las clases sin muestras suficientes.

    El umbral era 2, lo que dejaba pasar `tengo_fiebre_y_mareos` (dos grabaciones
    mal etiquetadas, variante en plural de `tengo_fiebre_y_mareo`). Esa clase
    acabo en el modelo publicado con 0 muestras en el conjunto de test, es decir,
    una salida posible que nunca llego a evaluarse.
    """
    csv_path = str(DATASET_PATH)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No se encontró el dataset en: {csv_path}")

    # Cargar sin encabezados
    df = pd.read_csv(csv_path, header=None)
    
    # Filtrar clases con pocas muestras ANTES de procesar
    label_col = df.shape[1] - 2
    
    # Convertir labels a string para manejar NaN correctamente
    df.iloc[:, label_col] = df.iloc[:, label_col].astype(str)
    
    # Contar muestras por clase (incluyendo 'nan' como string)
    label_counts = df.iloc[:, label_col].value_counts(dropna=False)
    
    # Identificar clases a eliminar
    classes_to_remove = label_counts[label_counts < min_samples_per_class].index.tolist()
    
    if classes_to_remove:
        print(f"⚠️ Eliminando {len(classes_to_remove)} clases con <{min_samples_per_class} muestras:")
        for cls in classes_to_remove:
            count = label_counts[cls]
            print(f"   - '{cls}': {count} muestra(s)")
        
        # Filtrar dataset
        before = len(df)
        df = df[~df.iloc[:, label_col].isin(classes_to_remove)]
        removed = before - len(df)
        print(f"   ✅ {removed} filas eliminadas, quedan {len(df)} filas\n")

    # Inferir features por frame
    n_features = _infer_features_per_frame(df.shape[1])

    # Separar columnas numéricas (todas las de features)
    feat_cols = list(range(FRAMES * n_features))
    label_col = FRAMES * n_features        # penúltima
    level_col = FRAMES * n_features + 1    # última (no usada en el modelo)

    # Forzar a numérico las columnas de features (coerce por si hay strings errantes)
    feat_df = df.iloc[:, feat_cols].apply(pd.to_numeric, errors="coerce")
    if feat_df.isna().any().any():
        # Si hay NaN tras coerción, probablemente hay filas corruptas.
        # Las eliminamos con advertencia (o podrías levantar error si prefieres).
        before = len(feat_df)
        mask_valid = ~feat_df.isna().any(axis=1)
        feat_df = feat_df[mask_valid]
        labels_series = df.iloc[:, label_col][mask_valid]
        # level_series = df.iloc[:, level_col][mask_valid]
        removed = before - len(feat_df)
        if removed > 0:
            print(f"⚠️ Se eliminaron {removed} filas con datos no numéricos en features.")

    else:
        labels_series = df.iloc[:, label_col]
        # level_series = df.iloc[:, level_col]

    X = feat_df.values.astype(np.float32).reshape(-1, FRAMES, n_features)

    # Codificar etiquetas
    encoder = LabelEncoder()
    y = encoder.fit_transform(labels_series.astype(str).values).astype(np.int64)

    # Split estratificado
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Debug útil
    print(f"✅ Dataset OK → X.shape={X.shape} (frames={FRAMES}, features/frame={n_features})")
    print(f"   y.shape={y.shape}, clases={list(encoder.classes_)}")

    return X_train, X_test, y_train, y_test, encoder
