# Dataset

El dataset de entrenamiento (`dataset_medico.csv`, ~135 MB) **no se versiona en este repositorio**
para mantenerlo liviano y no consumir cuota de Git LFS.

Cada fila del CSV contiene una secuencia de **35 frames x 150 features** (puntos clave extraidos con
MediaPipe Holistic: manos, pose y rostro) mas la etiqueta de la sena medica correspondiente.

## Como obtener los datos

### Opcion 1 - Generar un dataset sintetico (para probar el pipeline)

```bash
python app/utils/generate_fake_dataset.py
```

Genera `data/dataset_medico.csv` con datos ficticios, suficiente para verificar que el
entrenamiento y la API funcionan de extremo a extremo.

### Opcion 2 - Grabar secuencias reales con la webcam

```bash
python app/utils/grabar_secuencia_lstm.py
```

Captura secuencias reales usando MediaPipe y las agrega al CSV.

## Modelos preentrenados

Los artefactos ya entrenados **si estan incluidos** en el repositorio, en `artifacts/`:

| Archivo | Descripcion |
|---|---|
| `lstm_holistic.h5` | Modelo CNN+LSTM en produccion (entrada 35x150) |
| `cnn_lstm_model.h5` | Modelo CNN+LSTM previo (entrada 35x42) |
| `label_encoder.pkl` / `classes.json` | Clases del modelo, en el orden del encoder |
| `mean_holistic.npy` / `std_holistic.npy` | Estadisticas de normalizacion |
| `labels_catalog.json` | Nombre legible y dificultad de cada sena |

Esto permite levantar la API e inferir **sin necesidad de descargar el dataset ni reentrenar**.

> **Importante:** el dataset actual se grabo con un extractor que dejaba las
> manos fuera del vector de features. Regrabarlo es imprescindible antes de dar
> por buena cualquier metrica. El analisis completo esta en
> [`../docs/MODEL_NOTES.md`](../docs/MODEL_NOTES.md).
