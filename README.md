# SignMed — Backend

API de reconocimiento de **lengua de señas médica** en tiempo real. Recibe una
secuencia de keypoints capturada en el navegador, la clasifica con un modelo
CNN+LSTM y gestiona usuarios, práctica guiada, exámenes y progreso.

[![CI](https://github.com/RodrigoFK06/signmed-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/RodrigoFK06/signmed-backend/actions/workflows/ci.yml)

**Stack:** Python 3.12 · FastAPI · TensorFlow/Keras · MediaPipe Holistic · MongoDB
(Motor) · Pydantic v2 · JWT · pytest · Docker · GitHub Actions

Frontend: [signmed-frontend](https://github.com/RodrigoFK06/signmed-frontend)

---

## Arquitectura

```
app/
├── core/          settings (pydantic-settings) y logging
├── api/
│   ├── router.py
│   └── endpoints/ auth · predict · labels · records · progress ·
│                  level_progress · activity · statistics · exams ·
│                  admin · upload
├── services/      predictor · labels · auth · authorize
├── models/        esquemas Pydantic
├── db/            cliente MongoDB, colecciones e índices
└── utils/         feature_extraction · data_loader · holistic_tracking
artifacts/         modelo, encoder, estadísticas y catálogo de señas
docs/              MODEL_NOTES.md
tests/             suite pytest
```

Separación en tres capas: los *endpoints* solo validan y orquestan, los
*services* contienen la lógica y `db/` aísla el acceso a datos.

---

## Puesta en marcha

Requiere **Python 3.12** (TensorFlow 2.19 no publica ruedas para 3.13+).

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # pega en SECRET_KEY

uvicorn app.main:app --reload
```

Documentación interactiva en <http://localhost:8000/docs>.

### Docker

```bash
docker build -t signmed-backend .
docker run -p 8000:8000 --env-file .env signmed-backend
```

### Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

`requirements-dev.txt` no incluye TensorFlow ni MediaPipe: la suite cubre la API
y la lógica de negocio sobre una MongoDB en memoria, sin más de 1 GB de descarga.

---

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/health` | — | Health check |
| `GET` | `/labels` | — | Señas disponibles |
| `GET` | `/labels/detailed` | — | Señas con nombre y dificultad |
| `POST` | `/auth/signup` | — | Alta (`PATIENT` o `HEALTH_WORKER`) |
| `POST` | `/auth/login` | — | Devuelve el JWT |
| `GET` | `/auth/me` | JWT | Perfil actual |
| `POST` | `/upload-document` | — | Documento acreditativo (PDF) |
| `POST` | `/predict` | JWT | Clasifica una secuencia 35×150 |
| `GET` | `/records` | JWT | Historial paginado |
| `GET` | `/progress` | JWT | Estadísticas por seña |
| `GET` | `/progress/level-progress` | JWT | Progreso por nivel |
| `POST` | `/progress/increment-level` | JWT | Registra una seña completada |
| `GET` | `/activity/daily/{nickname}/{fecha}` | JWT | Actividad de un día |
| `GET` | `/stats/global_distribution` | JWT | Distribución global |
| `GET/POST/PUT/DELETE` | `/exams…` | JWT (ADMIN para escribir) | Gestión de exámenes |
| `GET` | `/admin/users` | ADMIN | Usuarios del sistema |
| `POST` | `/admin/approve-health-worker/{id}` | ADMIN | Aprobar solicitud |

### `POST /predict`

```jsonc
{
  "sequence": [[0.41, 0.52, /* … 150 valores … */], /* … 35 frames … */],
  "expected_label": "tengo_fiebre_y_mareo"   // opcional
}
```

```jsonc
{
  "label": "tengo_fiebre_y_mareo",
  "confidence": 87.4,
  "probabilities": [0.02, 0.87, /* … */],
  "evaluation": { "expected": "tengo_fiebre_y_mareo", "final": "CORRECTO" },
  "nickname": "ana"
}
```

`DUDOSO` significa que el modelo no alcanza el umbral de confianza
(`CONFIDENCE_THRESHOLD`, 75 % por defecto), no que el usuario se haya equivocado.

---

## Roles

| Rol | Permisos |
|---|---|
| `PATIENT` | Practicar, exámenes y **solo sus propios** datos |
| `HEALTH_WORKER` | Lo anterior + consultar la actividad de pacientes. Requiere aprobación |
| `ADMIN` | Gestión de exámenes, usuarios y aprobaciones |

`ADMIN` **no es autoasignable**: `/auth/signup` solo acepta `PATIENT` y
`HEALTH_WORKER`. Los administradores se crean con `scripts/create_admin.py`.

---

## Modelo

Arquitectura CNN+LSTM sobre secuencias de 35 frames × 150 features extraídas con
MediaPipe Holistic:

```
Input(35, 150) → Conv1D(64) → BatchNorm → MaxPool → Dropout
               → Conv1D(128) → BatchNorm → MaxPool → Dropout
               → LSTM(128, seq) → LSTM(64)
               → Dense(64, L2) → Dropout → Dense(n_clases, softmax)
```

El layout de las 150 features está definido en `app/utils/feature_extraction.py`
y debe mantenerse sincronizado con `lib/landmarks.ts` del frontend.

> **Antes de usar este modelo en serio, lee [`docs/MODEL_NOTES.md`](docs/MODEL_NOTES.md).**
> Documenta tres fallos encontrados en el pipeline original —el vector de
> features no contenía las manos, había train/serve skew y el dataset arrastra
> etiquetas duplicadas— con la evidencia que los demuestra y qué se corrigió.
> Las métricas publicadas **no** miden reconocimiento de señas real.

### Dataset y entrenamiento

El dataset no se versiona (ver [`data/README.md`](data/README.md)).

```bash
pip install -r requirements-training.txt
python -m app.utils.grabar_secuencia_lstm   # grabar secuencias
python -m app.train_cnn_lstm_model          # entrenar y evaluar
```

---

## Configuración

Todo se lee del entorno (ver `.env.example`). Fuera de `ENVIRONMENT=development`
la aplicación **no arranca** si `SECRET_KEY` conserva su valor por defecto.

| Variable | Por defecto | Descripción |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` · `staging` · `production` |
| `SECRET_KEY` | *(dev)* | Clave de firma del JWT. Obligatoria en producción |
| `MONGO_URI` | `mongodb://localhost:27017` | Cadena de conexión |
| `CORS_ORIGINS` | `http://localhost:3000` | Orígenes permitidos, separados por comas |
| `CONFIDENCE_THRESHOLD` | `75` | Umbral (%) para dar una predicción por buena |
| `APPLY_FEATURE_NORMALIZATION` | `false` | Activar solo tras reentrenar (ver notas) |
| `MAX_UPLOAD_BYTES` | `10485760` | Tamaño máximo de los PDF |

---

## Licencia

[MIT](LICENSE)
