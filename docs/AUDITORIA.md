# Auditoría técnica — SignMed

Análisis completo de los dos repositorios del sistema, los fallos encontrados y
las correcciones aplicadas.

- **Backend:** [signmed-backend](https://github.com/RodrigoFK06/signmed-backend) — FastAPI + TensorFlow + MongoDB
- **Frontend:** [signmed-frontend](https://github.com/RodrigoFK06/signmed-frontend) — Next.js + React + MediaPipe

Este documento existe porque el hallazgo principal no es un bug de código, sino
un fallo de diseño de datos que ningún test, log ni excepción hacía visible: el
sistema funcionaba de extremo a extremo mientras alimentaba al modelo con
información que no describía lo que decía describir.

---

## Resumen ejecutivo

| # | Hallazgo | Gravedad | Efecto |
|---|---|---|---|
| 1 | El vector de features no contenía las manos | **Crítica** | El modelo de lengua de señas nunca vio una mano |
| 2 | El frontend enviaba un vector incompatible con el entrenamiento | **Crítica** | Entrada sin significado, predicción arbitraria |
| 3 | Train/serve skew en la normalización | **Crítica** | Distribución en producción distinta a la de entrenamiento |
| 4 | `/labels` leía un CSV de 135 MB en cada petición | **Alta** | Agotamiento de memoria; listado vacío en producción |
| 5 | `role: "ADMIN"` autoasignable en el registro | **Alta** | Escalación de privilegios trivial |
| 6 | `SECRET_KEY` con valor por defecto publicado en el repo | **Alta** | Cualquiera podía firmar un JWT válido |
| 7 | `/predict` con reserva anónima si fallaba un import | **Alta** | Endpoint público accidental |
| 8 | Documentos personales de usuarios versionados en Git | **Alta** | PDFs de acreditación expuestos en un repo público |
| 9 | `model.predict()` bloqueando el event loop | Media | El servidor se congelaba para todas las peticiones |
| 10 | Sin índices en MongoDB | Media | `COLLSCAN` en cada consulta de historial |
| 11 | NextAuth configurado sin handler | Media | El panel de administración devolvía 403 permanente |
| 12 | CI fallando en el 100 % de las ejecuciones | Media | Ninguna verificación automática desde el primer commit |
| 13 | `npm install` y `next build` fallaban en un clon limpio | Media | El proyecto no era reproducible |

Además, 27 hallazgos menores de correctitud, rendimiento y mantenimiento
detallados más abajo.

### Estado antes y después

| | Antes | Después |
|---|---|---|
| Tests backend | No arrancaban (`ImportError`) | **58 pasando** |
| Tests frontend | 2, ambos rotos | **21 pasando** |
| Ejecuciones de CI en verde | 0 de 10 | Verificado en local |
| `npm install` en clon limpio | Falla (`ERESOLVE`) | Correcto |
| `next build` | Falla (prerender) | Correcto |
| Errores de ESLint | 59 | **0** (70 avisos documentados) |
| `tsc --noEmit` | Sin ejecutar en CI | Limpio |
| Ficheros `.py` | 52 | 46 |
| Ficheros `.ts` / `.tsx` | 128 | 91 |
| Dependencias de producción (frontend) | 58 | 27 |
| Tamaño del repositorio backend | 286 MB | ~7 MB |

---

## Metodología

Cada afirmación de este documento se comprobó contra el código o los datos
reales, no por lectura:

- El layout del vector de features se verificó **cargando el propio
  `dataset_medico.csv`** y comparando coordenadas conocidas (§1).
- El fallo de CI se confirmó con `gh run list`, que devolvió `failure` en las
  diez ejecuciones registradas.
- El fallo de `npm install` se reprodujo borrando `node_modules` y los ficheros
  de bloqueo.
- Las rutas muertas se confirmaron buscando consumidores en todo el árbol antes
  de eliminarlas.

---

## 1. El vector de features no contenía las manos

### El código

`app/utils/grabar_secuencia_lstm.py` construía cada frame concatenando bloques y
recortando al final:

```python
# --- CUERPO (33 puntos) ---
if results.pose_landmarks:
    for lm in results.pose_landmarks.landmark:
        frame_vector.extend([lm.x, lm.y])          # 66 valores

# --- CARA (muestra cada 10 puntos de los 468) ---
if results.face_landmarks:
    for lm in results.face_landmarks.landmark[::10]:
        frame_vector.extend([lm.x, lm.y])          # 94 valores

# --- MANOS (42 puntos total) ---
for hand_landmarks in [results.left_hand_landmarks, results.right_hand_landmarks]:
    if hand_landmarks:
        for lm in hand_landmarks.landmark:
            frame_vector.extend([lm.x, lm.y])      # 84 valores

frame_vector = frame_vector[:150]                  # <-- el recorte
```

`66 + 94 = 160`, ya por encima de 150 **antes de llegar a las manos**. Como las
manos se añadían las últimas, el recorte las eliminaba por completo.

Un sistema de reconocimiento de lengua de señas se entrenó con postura corporal
y posición facial.

### La verificación

No basta con contar: hay que demostrarlo sobre los datos. Se cargó el primer
frame de una secuencia real etiquetada `yo` y se compararon coordenadas.

Si el bloque `[66:150]` fueran manos, la posición 66 sería el landmark 0 de una
mano —la muñeca— y coincidiría con alguna de las dos muñecas que ya aporta la
pose (landmarks 15 y 16, features 30-33).

| Referencia | Coordenadas (x, y) |
|---|---|
| Pose — muñeca izquierda (features 30, 31) | (0.634, 0.933) |
| Pose — muñeca derecha (features 32, 33) | (0.310, 0.952) |
| Pose — nariz (features 0, 1) | (0.394, 0.529) |
| **Bloque en la posición 66, 67** | **(0.389, 0.573)** |

La posición 66 cae sobre la nariz, no sobre ninguna muñeca. Es cara.

**Segunda comprobación — movimiento a lo largo de los 35 frames:**

| Bloque | Desviación típica temporal media |
|---|---|
| `[0:66]` (pose) | 0.0276 |
| `[66:150]` | 0.0037 |

El segundo bloque es casi estático. Unas manos ejecutando una seña no se
comportan así; una cara sí.

### El agravante

El vector no solo estaba mal: **era inconsistente entre frames**. Los bloques se
añadían únicamente si MediaPipe detectaba esa parte. Si en un frame no
encontraba cara, el vector pasaba a ser `66 (pose) + 84 (manos) = 150` y las
manos **sí** entraban.

La misma posición del vector significaba una cosa u otra según lo que el
detector hubiera encontrado en ese instante. Para un modelo, eso es ruido
estructural.

### Ruido añadido: las piernas

16 features del bloque de pose tienen medias fuera del rango `[0, 1]` que
MediaPipe garantiza, llegando hasta **2.91**. Corresponden a las coordenadas `y`
de los landmarks 23-32: caderas, rodillas, tobillos y pies. En un encuadre de
webcam quedan fuera de cámara y MediaPipe los extrapola. Ocupaban el 11 % del
vector con valores inventados.

### La corrección

`app/utils/feature_extraction.py` es ahora la única fuente de verdad del layout,
y su equivalente en el frontend es `lib/landmarks.ts`:

```
[  0: 84]  mano izquierda (21) + mano derecha (21), (x, y)
[ 84:130]  pose, tren superior: landmarks 0-22, (x, y)
[130:150]  cara: 10 puntos de referencia, (x, y)
```

Tres decisiones:

1. **Las manos van primero**, con espacio garantizado. Son lo que describe la seña.
2. **Los bloques tienen tamaño fijo.** Un landmark ausente se rellena con `0.0` y
   el bloque conserva su longitud, de modo que cada posición significa siempre lo
   mismo.
3. **Se descarta el tren inferior** de la pose.

Se añadió `has_hands()` / `hasHands()`: un frame sin manos detectadas se descarta
en vez de guardarse. La comprobación anterior era «algún valor distinto de cero»,
que la pose satisface siempre.

### Consecuencia, sin adornos

**El dataset actual no se arregla reentrenando.** Las grabaciones nunca
contuvieron las manos: la información no está ahí. Hay que **volver a grabar**
con el extractor corregido.

Los artefactos publicados se conservan para que el sistema sea desplegable y
demostrable de extremo a extremo, pero sus métricas no miden reconocimiento de
señas. El detalle está en [`MODEL_NOTES.md`](MODEL_NOTES.md).

---

## 2. El frontend enviaba un vector distinto

Mientras el backend esperaba 150 features de pose y cara, el navegador enviaba
otra cosa por completo. `hooks/use-camera.ts` y `components/camera-module.tsx`
hacían tres transformaciones incompatibles.

**a) Capturaba 42 features de UNA mano y rellenaba hasta 150 con ceros.**

```ts
function to150Features(vec: number[]): number[] {
  const out = Array.isArray(vec) ? vec.slice(0, 150) : []
  if (out.length < 150) out.push(...Array(150 - out.length).fill(0))
  return out
}
```

Las 108 posiciones rellenadas no son «ausencia de dato»: para el modelo son las
coordenadas de la pose y la cara. Se le estaba diciendo que el cuerpo entero
estaba en el origen.

Además el `HandLandmarker` se configuraba con `numHands: 2` pero solo se leía
`result.landmarks[0]`: una mano de dos.

**b) Escalaba las coordenadas a píxeles.**

```ts
features[i * 2]     = x * imageData.width
features[i * 2 + 1] = y * imageData.height
```

MediaPipe entrega coordenadas normalizadas (0..1) y así se entrenó el modelo.
Multiplicarlas por el tamaño del vídeo produce valores de 0 a 1920 **que dependen
de la resolución de cada webcam**: el mismo gesto daba números distintos en cada
ordenador.

**c) Aplicaba un z-score por frame en el cliente**, y el backend volvía a
estandarizar encima con las estadísticas del entrenamiento. Dos normalizaciones
distintas encadenadas.

### La corrección

`lib/landmarks.ts` construye el mismo vector que el backend, en coordenadas
normalizadas, sin escalar ni normalizar en cliente. `usePredict` dejó de rellenar
y recortar: si la secuencia no tiene la forma correcta lanza un error visible en
vez de enviar algo que el backend aceptará sin protestar.

`__tests__/landmarks.test.ts` cubre ese contrato precisamente porque una
desincronización **no produce ningún error**: el backend responde 200 con una
predicción sin sentido.

---

## 3. Train/serve skew

`app/train_cnn_lstm_model.py` calculaba y guardaba las estadísticas de
normalización… y luego entrenaba con los datos en crudo:

```python
mean = np.mean(X_train, axis=(0, 1))
std  = np.std(X_train, axis=(0, 1))
np.save(MEAN_PATH, mean)
np.save(STD_PATH, std)
...
model.fit(X_train, y_train, ...)      # X_train SIN normalizar
```

Mientras tanto, `app/services/predictor.py` **sí** estandarizaba en inferencia.
El modelo recibía en producción una distribución que nunca había visto durante el
entrenamiento.

**Corregido en dos frentes:**

- El entrenamiento aplica ahora la normalización, con las estadísticas calculadas
  solo sobre `train` y aplicadas también a `test` para no filtrar información.
- La inferencia se controla con `APPLY_FEATURE_NORMALIZATION`, **por defecto
  `false`**, porque el modelo actualmente publicado se entrenó sin normalizar. Al
  reentrenar hay que ponerlo a `true`.

---

## 4. El dataset se leía en tiempo de petición

`/labels`, `/labels/detailed` y `/progress/level-progress` hacían esto en **cada
petición HTTP**:

```python
df = pd.read_csv(dataset_path, header=None)   # data/dataset_medico.csv = 135 MB
```

Con `Cache-Control: no-store` para que el navegador no reutilizara nunca la
respuesta. Cada carga de la pantalla de práctica reservaba cientos de megabytes.

`get_labels_by_difficulty()` lo hacía además **dentro de un `async def`**, es
decir, dentro del event loop: durante los segundos que tarda pandas en parsear
135 MB, el servidor no atendía ninguna otra petición.

Y como el dataset no se despliega —ni debe: pesa más que el límite de GitHub—, en
producción `os.path.exists()` daba `False` y el endpoint devolvía un listado
**vacío con estado 200**. Sin error, sin log, sin señal.

### La corrección

`app/services/labels.py` resuelve las etiquetas en memoria a partir de dos
artefactos de pocos kilobytes:

- `artifacts/classes.json` — las clases que el modelo sabe emitir, fuente de verdad
- `artifacts/labels_catalog.json` — nombre legible, dificultad y descripción

Con degradación explícita: una entrada del catálogo sin clase en el modelo se
ignora (metadato huérfano), y una clase sin metadatos se sirve con valores
derivados del identificador, de modo que añadir una seña nunca rompe la API.
Ambos casos quedan registrados con `logger.warning`.

Las respuestas pasan a ser cacheables (`public, max-age=300`).

---

## 5. Seguridad

| Hallazgo | Detalle | Corrección |
|---|---|---|
| **Escalación de privilegios** | `UserCreate.role` aceptaba todo el tipo `UserRole`, así que `POST /auth/signup` con `{"role": "ADMIN"}` creaba un administrador | Tipo `SelfAssignableRole` restringido a `PATIENT` y `HEALTH_WORKER`; los administradores se provisionan con `scripts/create_admin.py` |
| **Clave de firma por defecto** | `SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_change_me")`, con el valor publicado en el repositorio. Si la variable faltaba en el despliegue, cualquiera podía firmar un JWT válido para cualquier usuario | La aplicación **no arranca** fuera de `ENVIRONMENT=development` si la clave no está definida |
| **Endpoint público accidental** | `/predict` envolvía el import de `get_current_user` en un `try/except` que, al fallar, definía un usuario anónimo. Un error de importación convertía el endpoint en público y escribía registros sin dueño | Dependencia directa, sin red de seguridad |
| **Condición de carrera en el registro** | Comprobar-y-luego-insertar: dos altas simultáneas con el mismo email pasaban ambas la comprobación | Índices únicos en MongoDB sobre `email` y `nickname`; se captura `DuplicateKeyError` y se devuelve 409 |
| **Subida sin límite real** | `await file.read()` cargaba el fichero **entero** en memoria y comprobaba el tamaño **después**. Una subida de varios GB agotaba el proceso antes de llegar al `if`. La validación era solo la extensión del nombre | Lectura por bloques con corte al superar el límite, verificación de la cabecera `%PDF-`, nombre en disco por UUID |
| **Estadísticas públicas** | `/stats/global_distribution` no exigía sesión y exponía el volumen de uso del sistema | Requiere JWT |
| **Fuga de detalles internos** | Los `except` devolvían `str(e)` al cliente: nombres de colección, errores del driver | Se registra con `logger.exception` y se devuelve un mensaje genérico |
| **Rol tomado del token** | El rol venía del JWT; si un administrador degradaba a un usuario, su token vigente conservaba los permisos antiguos | El rol se lee siempre del documento en base de datos |
| **Documentos personales versionados** | 10 PDFs reales de acreditación de personal de salud (hasta 4,5 MB) estaban en `uploads/documents/` dentro del repositorio | Purgados del historial con `filter-branch` y `force-push`; `uploads/` en `.gitignore`; los tests se aislaron con `tmp_path` porque escribían en el directorio real |

> **Pendiente fuera de nuestro alcance:** esos PDFs **siguen publicados** en el
> repositorio original de la cuenta desde la que se clonó el proyecto. Hay que
> pedir su eliminación allí.

---

## 6. Correctitud y rendimiento

### Backend

| Hallazgo | Efecto | Corrección |
|---|---|---|
| `model.predict()` dentro de un `async def` | Función síncrona de decenas de ms bloqueando el event loop: el servidor se congelaba para **todas** las peticiones concurrentes | `run_in_threadpool` |
| Modelo cargado al importar el módulo | Importar cualquier endpoint —o recolectar los tests— arrastraba TensorFlow y fallaba si el `.h5` no estaba | Carga perezosa bajo lock, precarga en el `lifespan`, y **503** en vez de 500 si el artefacto falta |
| Sin índices en MongoDB | `COLLSCAN` en cada consulta de `/records`, `/progress` y `/activity/daily` | 10 índices creados en el arranque |
| Consulta N+1 | El listado de intentos hacía hasta **tres** consultas de usuario por intento, probando `ObjectId` y `str` alternativamente | Una sola consulta `$in` para todos los autores |
| Umbral de confianza al 50 % | `threshold=50.0` con el comentario `TEMPORAL: para pruebas`: cualquier predicción por encima del 50 % se daba por correcta | Configurable, 75 % por defecto |
| Validación de progreso puenteada | `/increment-level` registraba cualquier etiqueta: `TEMPORAL: Para debugging, aceptar cualquier label`. Un usuario podía inflar su progreso a voluntad | 400 si la seña no pertenece al nivel |
| Duración de examen siempre 0 | `started_at = now` y `time_taken = 0.0`, con el comentario «esto debería venir del frontend» | El cliente envía `started_at`; si falta, se guarda `None` en vez de inventar un valor |
| Campo `score` ambiguo | Documentado como porcentaje, relleno con el conteo de aciertos, y leído de las dos formas según la pantalla | Separado en `score` (conteo) y `percentage`, con compatibilidad hacia atrás |
| `X-Total-Count` no expuesta | La cabecera se enviaba, pero sin `expose_headers` el navegador no puede leerla en peticiones cross-origin: la paginación siempre veía el total de la página actual | Declarada en el middleware de CORS |
| CORS con dominios en el código | Cambiar el dominio del frontend exigía desplegar el backend | Variable de entorno `CORS_ORIGINS` |
| `@app.on_event` | Obsoleto en FastAPI moderno | `lifespan` |
| `datetime.utcnow()` | Devuelve un `datetime` naive; comparado con fechas con zona horaria produce errores silenciosos | `datetime.now(tz=timezone.utc)` |
| `except Exception: pass` en persistencia | Un fallo de base de datos desaparecía sin rastro | Se registra con `logger.exception` sin tumbar la predicción |
| Artefactos dentro de un paquete Python | Los `.h5`, `.pkl` y `.npy` vivían en `app/models/`, que es el paquete de los esquemas Pydantic | Movidos a `artifacts/` |
| Código muerto | `model_loader.py` (con un `MockTensorFlow` que producción no usaba), `evaluator.py`, `feedback_analyzer.py` (0 bytes), 8 scripts sueltos en la raíz y modelos legacy duplicados | Eliminados |

### Frontend

| Hallazgo | Efecto | Corrección |
|---|---|---|
| **La webcam no se apagaba** | El cleanup del efecto dependía solo de `[enabled]` y capturaba el `stream` del render en que se montó (`null`), así que `track.stop()` nunca se ejecutaba. El piloto de la cámara seguía encendido tras cancelar | Referencias locales al stream y al landmarker dentro del efecto |
| Bucle de captura reiniciado en cada render | `onFrame` llegaba inline y estaba en las dependencias del efecto: cada render destruía y recreaba el `requestAnimationFrame` | El callback vive en una `ref` |
| Tres copias del frame por captura | `getImageData` sobre el canvas visible, más un `document.createElement("canvas")` **nuevo en cada frame**, más `putImageData`. A 7 fps y 1080p, cientos de MB/s de basura para el recolector | Detección directa sobre el elemento `<video>` |
| `runningMode: "IMAGE"` | Trataba cada frame como una foto suelta y perdía el seguimiento temporal entre frames, justo lo que necesita una secuencia | `"VIDEO"` con `detectForVideo` |
| Frames guardados en estado | `setFrames([...framesRef.current])` en cada frame: un re-render completo del árbol unas 10 veces por segundo, que además recreaba el callback | Los frames viven en una `ref`; la UI solo re-renderiza el contador |
| `nickname: "demo_user"` fijo | Se enviaba en cada predicción, sobrescribiendo al usuario real | Eliminado: el backend usa siempre el JWT |
| Intervalo de cuenta atrás sin limpiar | Al cancelar durante la cuenta atrás seguía disparando | `clearTimeout` en el cleanup |

---

## 7. Código muerto en el frontend

| Qué | Por qué estaba muerto |
|---|---|
| **NextAuth completo** | Configurado en `lib/auth-options.ts` **sin el handler `[...nextauth]`**. Sin él, `getServerSession()` devuelve siempre `null`, así que los tres route handlers de `app/api/admin/*` respondían **403 permanente**. Además usaban `NEXT_PUBLIC_API_URL`, una variable que no existe en `.env.example`. Nada los llamaba: el panel de administración va directo al backend |
| `pages/api/*` (6 proxies) | Ni un solo consumidor en todo el árbol |
| `uploadthing` y `@uploadthing/react` | Sin usar desde la aplicación |
| 27 componentes de shadcn/ui | Andamiaje de la plantilla; solo se referenciaban entre ellos |
| 31 dependencias de producción | De 58 a 27 |

Resultado: 128 → 91 ficheros TypeScript.

---

## 8. Infraestructura y tooling

### El CI llevaba 10 de 10 ejecuciones fallando

Desde el primer commit. `gh run list` lo confirma: `failure` en todas.

La causa: los tests inyectaban un doble de `app.services.model_loader` parcheando
`sys.modules`, un módulo que **el camino de producción ni siquiera importaba**, y
el doble de `app.db.mongodb` solo definía dos de las cinco colecciones. Con eso,
`from app.main import app` fallaba antes de ejecutar ninguna aserción.

**Corregido:** suite reescrita usando los mecanismos que la propia aplicación
expone (`set_collections`, `dependency_overrides`) sobre una MongoDB en memoria,
sin parchear `sys.modules`. **58 tests.** El workflow añade un paso que verifica
la presencia de los artefactos del modelo, para que un artefacto ausente se
detecte en CI y no al desplegar.

### El proyecto no era reproducible

`npm install` fallaba en un clon limpio:

```
npm error ERESOLVE could not resolve
npm error While resolving: react-day-picker@8.10.1
npm error Found: react@19.1.0
npm error Could not resolve dependency:
npm error peer react@"^16.8.0 || ^17.0.0 || ^18.0.0" from react-day-picker@8.10.1
```

Y `next build` también, por `useSearchParams()` sin límite de Suspense en
`/progress`.

**Corregido:** `react-day-picker` a v10 con `calendar.tsx` adaptado a su nueva
API, `Suspense` en `/progress`, y `next` actualizado a 16 porque 15.2.4 tiene una
vulnerabilidad publicada (CVE-2025-66478).

### Lint

`next lint` desapareció en Next 16. Migrado a ESLint flat config: **de 59 errores
a 0**. Los 70 avisos restantes están documentados en `eslint.config.mjs` — son
reglas nuevas del React Compiler sobre patrones preexistentes en 20 pantallas. Se
dejaron como aviso visible en lugar de silenciarlas: corregirlas es una
refactorización de la capa de estado que merece su propio cambio.

### Otros

- **`Dockerfile`** multi-etapa, sin root, con healthcheck. No había.
- **Requisitos separados por uso:** `requirements.txt` (API),
  `requirements-dev.txt` (CI, sin TensorFlow ni MediaPipe: más de 1 GB
  innecesario) y `requirements-training.txt`.
- **Configuración centralizada** con `pydantic-settings` en vez de
  hiperparámetros y rutas escritas en el código.
- **Logging estructurado** en vez de `print()` con emojis en el camino de
  inferencia.
- **283 MB de datasets** salieron del historial de Git; los modelos (9 MB) pasaron
  de Git LFS a blobs normales, porque están muy por debajo del límite de 100 MB
  por fichero y así el repositorio no depende de una cuota.
- **Rastros de la plantilla:** el `package.json` se llamaba `my-v0-project` y el
  layout declaraba `generator: 'v0.dev'`.

---

## 9. Calidad de los datos y de las métricas

### Distribución real del dataset

1353 secuencias:

| Etiqueta | Nivel | Secuencias |
|---|---|---|
| `yo` | principiante | 344 |
| `que_medicamentos_toma` | avanzado | 256 |
| `dolor` | principiante | 227 |
| `tengo_resfriado_y_tos` | intermedio | 218 |
| `tengo_fiebre_y_mareo` | intermedio | 211 |
| `me_duele` | principiante | 93 |
| `tengo_fiebre_y_mareos` | intermedio | **2** |
| `prueba_test` | principiante | **1** |
| *(cadena vacía)* | intermedio | **1** |

`tengo_fiebre_y_mareos` es un error tipográfico —el plural de
`tengo_fiebre_y_mareo`—. El filtro `min_samples_per_class=2` la dejaba pasar, así
que acabó en el modelo publicado como una clase con **0 muestras en el conjunto
de test**: una salida posible que nunca llegó a evaluarse.

**Corregido:** el umbral sube a 10 y la clase se marca `deprecated` en el
catálogo, de modo que el modelo puede seguir emitiéndola pero no se ofrece para
practicar.

### Las métricas publicadas no miden lo que parecen

`classification_report_holistic.txt` reporta **0.80 de accuracy**. No es una
medida de reconocimiento de señas, por dos razones independientes:

1. El modelo clasifica postura corporal y posición facial (§1).
2. **El split es aleatorio por fila**, no por sesión de grabación ni por persona.
   Frames de una misma grabación caen a la vez en entrenamiento y en test, así que
   el modelo puede memorizar el encuadre concreto en lugar de generalizar. Que
   `que_medicamentos_toma` obtenga 1.00 de precisión **y** 1.00 de recall es la
   señal típica de esa fuga.

El `metrics.json` del modelo anterior (35×42) reporta accuracy 0.35 y
f1_macro 0.17.

**Al reentrenar:** separar por grupo (`GroupShuffleSplit` sobre la grabación o la
persona) antes de dar por buena ninguna métrica.

---

## 10. Qué queda pendiente

Ordenado por lo que más cambia el resultado:

1. **Regrabar el dataset** con el extractor corregido. Sin esto, ninguna métrica
   significa nada. Checklist completo en [`MODEL_NOTES.md`](MODEL_NOTES.md).
2. **Reentrenar** con split por grupo y `APPLY_FEATURE_NORMALIZATION=true`.
3. **Revisar el solapamiento semántico** entre `dolor` y `me_duele`.
4. **Refactorizar la capa de estado del frontend**: los 70 avisos de
   `set-state-in-effect` e `immutability`.
5. **Resolver la facturación de GitHub** para que Actions vuelva a ejecutarse
   (gratis e ilimitado en repositorios públicos).
6. **Pedir la eliminación** de los PDFs de usuarios en el repositorio original.

---

## 11. Cómo reproducir las verificaciones

```bash
# Backend
pip install -r requirements-dev.txt
pytest -q                       # 58 tests

# Frontend
npm ci
npm run typecheck               # limpio
npm run lint                    # 0 errores
npm test                        # 21 tests
npm run build                   # correcto
```

Para comprobar el hallazgo §1 sobre el dataset (requiere `dataset_medico.csv`):

```python
import csv, numpy as np

with open("data/dataset_medico.csv", newline="") as f:
    row = next(csv.reader(f))

seq = np.array([float(v) for v in row[:-2]], dtype=np.float32).reshape(35, 150)
f0 = seq[0]

print("pose muñeca izq (30,31):", f0[30], f0[31])
print("pose muñeca der (32,33):", f0[32], f0[33])
print("pose nariz      ( 0, 1):", f0[0],  f0[1])
print("bloque          (66,67):", f0[66], f0[67])   # coincide con la nariz

t = seq.std(axis=0)
print("std temporal pose  [0:66]  :", t[0:66].mean())
print("std temporal resto [66:150]:", t[66:150].mean())
```

---

## Nota final

El fallo principal de este proyecto es instructivo justo porque **no se
manifestaba**. No había excepción, ni log, ni test en rojo: el sistema arrancaba,
la cámara grababa, el backend respondía 200 y la interfaz mostraba un porcentaje
de confianza. Un `classification_report` con 0.80 de accuracy respaldaba la
sensación de que funcionaba.

Lo que lo delató fue comparar los datos con lo que decían representar: sumar
`66 + 94 + 84` y ver que no cabía en 150, y después ir al CSV a confirmar qué
había realmente en cada posición.

Documentar esto es más útil que ocultarlo. Un modelo que no funciona y se sabe
por qué es un punto de partida; uno que parece funcionar sin que nadie sepa qué
mide, no.
