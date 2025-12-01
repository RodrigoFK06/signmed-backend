# Medical Sign Recognition System

Este proyecto implementa un sistema de reconocimiento de señas médicas basado en una arquitectura **CNN+LSTM**. Incluye los scripts de entrenamiento y evaluación, una API ligera con FastAPI y utilidades para generar datasets de prueba.

## Tabla de contenidos
- [Requisitos](#requisitos)
- [Instalación](#instalacion)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Preparación del dataset](#preparacion-del-dataset)
- [Entrenamiento](#entrenamiento)
- [Evaluación del modelo](#evaluacion-del-modelo)
- [Uso de la API](#uso-de-la-api)
- [Integración con el frontend](#integracion-con-el-frontend)
- [Pruebas](#pruebas)
- [Legacy](#legacy)

## Requisitos
- Python 3.11 o superior
- `virtualenv` o similar para aislar dependencias

## Instalacion
1. Clona este repositorio.
2. Crea y activa un entorno virtual:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```
3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Estructura del proyecto
- **app/**: utilidades de entrenamiento y evaluacion.
- **api/**: API FastAPI para realizar inferencias con el modelo CNN+LSTM.
- **models/**: modelos entrenados y artefactos generados.
- **data/**: dataset en CSV (real o sintético).
- **tests/**: pruebas unitarias con `pytest`.
- **config.py**: define rutas y parámetros globales usados por los scripts y la API.

## Preparacion del dataset
El modelo se entrena con `data/dataset_medico.csv`, donde cada fila contiene 35×42 valores (puntos clave de ambas manos) y la etiqueta correspondiente.

Si no cuentas con datos reales puedes generar un dataset ficticio ejecutando:
```bash
python app/utils/generate_fake_dataset.py
```
El archivo se guardará en `data/dataset_medico.csv`.

## Entrenamiento
El script principal para entrenar el modelo actual es:

```bash
python app/train_cnn_lstm_model.py
```
Generará `models/cnn_lstm_model.h5` y `models/label_encoder.pkl`. Además se guardará la curva de pérdida en `models/loss_plot_cnn_lstm.png`.

La arquitectura CNN+LSTM añade capas convolucionales previas al LSTM, lo que mejora la extracción de características frente al modelo LSTM puro (`train_lstm_model.py`, mantenido solo con fines históricos).

## Evaluacion del modelo
Para evaluar el rendimiento del modelo entrenado:

```bash
python app/train_cnn_lstm_model.py
```

Se obtendrán las métricas en `models/metrics.json`, la matriz de confusión en `models/confusion_matrix.png` y el reporte de clasificación en `models/classification_report.txt`.

## Uso de la API
Inicia la API ligera con:
```bash
uvicorn api.main:app --reload
```
Cada petición a `/predict` se registrará en `models/inference_log.csv` con la fecha UTC, el *nickname* (si se envía) y la confianza obtenida.

### Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| **GET** | `/health` | Comprobación de que el servicio está activo. Devuelve `{"status": "ok"}` |
| **GET** | `/labels` | Lista de etiquetas médicas disponibles (cargadas del dataset) |
| **POST** | `/predict` | Envía una secuencia de 35×42 puntos para obtener la predicción y métricas |

### Solicitud `POST /predict`
Se debe enviar un cuerpo JSON y establecer el encabezado `Content-Type: application/json`:

```json
{
  "sequence": [[0.0, 0.1, ...], ...],
  "expected_label": "dolor_de_cabeza",
  "nickname": "demo"
}
```

### Respuesta de ejemplo
```json
{
  "predicted_label": "dolor_de_cabeza",
  "confidence": 92.5,
  "evaluation": "CORRECTO",
  "success_rate": 80.0,
  "average_confidence": 85.2
}

```
Cada petición a `/predict` se registrará en `models/inference_log.csv` con la fecha UTC, el *nickname* (si se envía) y la confianza obtenida.


### Ejemplo de solicitud
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"sequence": [[0.0, ..., 0.1]], "nickname": "demo"}'
```


  La secuencia debe contener 35 arreglos de 42 flotantes. La respuesta incluye la etiqueta predicha, la confianza, la evaluación y las métricas agregadas (`success_rate`, `average_confidence`), además del vector completo de probabilidades.


## Integracion con el frontend
Para consumir el servicio desde aplicaciones web o móviles:
1. Prepara la **secuencia** como un arreglo de 35 frames, cada uno con 42 valores flotantes normalizados entre 0 y 1.
2. Envía un JSON al endpoint `/predict` con los campos:
   - `sequence` *(obligatorio)*: la secuencia de puntos clave.
   - `expected_label` *(opcional)*: etiqueta que esperas obtener para evaluar la predicción.
   - `nickname` *(opcional)*: identificador del usuario para estadísticas.
3. La respuesta contiene `predicted_label`, `confidence`, `evaluation`, `average_confidence` y `success_rate`.
4. No se requiere autenticación, pero incluir `nickname` ayuda a generar métricas históricas.

La API desplegada en Render tiene la URL base `https://mi-backend.onrender.com`.

### Ejemplo en JavaScript (fetch)
```javascript
const body = {
  sequence,
  expected_label: "dolor_de_cabeza",
  nickname: "demo"
};
fetch("https://mi-backend.onrender.com/predict", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body)
})
  .then(r => r.json())
  .then(data => console.log(data))
  .catch(console.error);
```

### Ejemplo en React
```javascript
import { useState, useEffect } from "react";

export default function PredictView({ sequence }) {
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!sequence) return;
    fetch("https://mi-backend.onrender.com/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sequence })
    })
      .then(res => res.json())
      .then(setResult)
      .catch(console.error);
  }, [sequence]);

  return result && (
    <div>
      <p>Etiqueta: {result.predicted_label}</p>
      <p>Confianza: {result.confidence.toFixed(2)}%</p>
    </div>
  );
}
```

### Ejemplo en Flutter
```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

Future<void> sendSequence(List<List<double>> sequence) async {
  final resp = await http.post(
    Uri.parse('https://mi-backend.onrender.com/predict'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'sequence': sequence,
      'nickname': 'demo'
    }),
  );
  if (resp.statusCode == 200) {
    final data = jsonDecode(resp.body);
    print('Etiqueta: ${data['predicted_label']}');
  } else {
    throw Exception('Error ${resp.statusCode}: ${resp.body}');
  }
}
```

### Buenas prácticas
- Los artefactos `cnn_lstm_model.h5` y `label_encoder.pkl` se encuentran en la carpeta `models/` y el encoder se carga con **joblib**, no con `pickle`.
- Muestra las métricas de `success_rate` y `average_confidence` para dar retroalimentación al usuario.

## Pruebas
Las pruebas unitarias se ejecutan con:
```bash
pytest -q
```

## Legacy
El repositorio conserva scripts y archivos del modelo LSTM original (`lstm_gestos_model.h5` y `label_encoder_lstm.pkl`). También existe una configuración `.env` orientada a una API con MongoDB. Estos elementos se mantienen por compatibilidad, pero el flujo recomendado utiliza el modelo CNN+LSTM y no requiere variables de entorno.
