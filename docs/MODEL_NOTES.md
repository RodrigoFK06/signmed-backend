# Notas del modelo

Documento de trazabilidad sobre el modelo publicado (`artifacts/lstm_holistic.h5`),
los fallos detectados en su pipeline y qué se corrigió.

---

## 1. El vector de features no contenía las manos

### Qué pasaba

El grabador (`app/utils/grabar_secuencia_lstm.py`) construía cada frame así:

```python
pose   (33 landmarks)          ->  66 valores
face   (468[::10] = 47 lm)     ->  94 valores
manos  (21 + 21 landmarks)     ->  84 valores
frame_vector = frame_vector[:150]   # <-- recorte
```

`66 + 94 = 160`, ya por encima de 150. **Las manos, que se añadían al final,
quedaban siempre fuera del recorte.** Un modelo de reconocimiento de lengua de
señas se entrenó sin ver ni una sola mano: aprendió postura corporal y posición
de la cara.

Peor aún, el contenido dependía de la detección: si MediaPipe no encontraba cara,
el vector pasaba a ser `66 pose + 84 manos = 150` y las manos **sí** entraban. La
misma posición del vector significaba cosas distintas en frames distintos.

### Cómo se verificó

Sobre `data/dataset_medico.csv`, primer frame de una secuencia etiquetada `yo`:

| Referencia | Coordenadas |
|---|---|
| Pose muñeca izquierda (features 30,31) | (0.634, 0.933) |
| Pose muñeca derecha (features 32,33) | (0.310, 0.952) |
| Pose nariz (features 0,1) | (0.394, 0.529) |
| **Bloque en la posición 66,67** | **(0.389, 0.573)** |

Si el bloque `[66:150]` fueran manos, la posición 66 sería el landmark 0 de una
mano (la muñeca) y coincidiría con alguna de las muñecas de la pose. Cae sobre la
nariz.

Confirmación adicional — movimiento a lo largo de los 35 frames:

| Bloque | Desviación temporal media |
|---|---|
| `[0:66]` (pose) | 0.0276 |
| `[66:150]` | 0.0037 |

El segundo bloque apenas se mueve: es una cara, no unas manos gesticulando.

Además, 16 features del bloque de pose tienen medias fuera de `[0,1]`, hasta
**2.91**. Son las coordenadas `y` de los landmarks 23–32 (caderas, rodillas,
tobillos, pies), que quedan fuera de cuadro en una webcam y MediaPipe extrapola.
Ruido puro ocupando el 11 % del vector.

### Qué se hizo

`app/utils/feature_extraction.py` es ahora la única fuente de verdad del layout,
compartida entre el grabador y el frontend (`lib/landmarks.ts`):

```
[  0: 84]  mano izquierda (21) + mano derecha (21), (x, y)
[ 84:130]  pose, tren superior: landmarks 0-22, (x, y)
[130:150]  cara: 10 puntos de referencia, (x, y)
```

Las manos van primero y con espacio garantizado. Los bloques tienen tamaño fijo:
un landmark ausente se rellena con `0.0` y cada posición significa siempre lo
mismo. Se descartan las piernas.

### Consecuencia

**El dataset actual no puede reentrenarse para arreglar esto**: las grabaciones
nunca contuvieron las manos, la información no está ahí. Hay que **volver a
grabar** con el grabador corregido. Los artefactos publicados se mantienen para
que el sistema sea desplegable y demostrable de extremo a extremo, pero sus
métricas no reflejan reconocimiento de señas real.

---

## 2. Train/serve skew: se entrenaba sin normalizar y se servía normalizado

`train_cnn_lstm_model.py` calculaba y guardaba `mean_holistic.npy` /
`std_holistic.npy`, pero entrenaba con las features en crudo:

```python
mean = np.mean(X_train, axis=(0, 1))
std  = np.std(X_train, axis=(0, 1))
np.save(MEAN_PATH, mean); np.save(STD_PATH, std)
...
model.fit(X_train, y_train, ...)   # X_train SIN normalizar
```

Mientras tanto `predictor.py` sí aplicaba la estandarización en inferencia. El
modelo recibía en producción una distribución que nunca había visto.

**Corregido en dos frentes:**

- El entrenamiento ahora sí aplica la normalización (con las estadísticas de
  train, aplicadas también a test para no filtrar información).
- La inferencia se controla con `APPLY_FEATURE_NORMALIZATION`, **por defecto
  `false`**, porque el modelo actualmente publicado se entrenó sin normalizar.
  Al reentrenar hay que ponerlo a `true`.

---

## 3. Calidad de las etiquetas

Distribución real de `data/dataset_medico.csv` (1353 secuencias):

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

`tengo_fiebre_y_mareos` es un error tipográfico (plural) de
`tengo_fiebre_y_mareo`. El filtro `min_samples_per_class=2` la dejaba pasar, así
que acabó en el modelo publicado como una clase con **0 muestras en test**: una
salida posible que nunca llegó a evaluarse.

**Corregido:** el umbral sube a 10 (`MIN_SAMPLES_PER_CLASS`) y la clase se marca
`deprecated` en `artifacts/labels_catalog.json`, de modo que el modelo puede
seguir emitiéndola pero no se ofrece para practicar.

Pendiente al reentrenar: `dolor` y `me_duele` se solapan semánticamente y
convendría revisar si deben ser clases separadas.

---

## 4. Sobre las métricas publicadas

`classification_report_holistic.txt` reporta **0.80 de accuracy**. No es una
medida de reconocimiento de señas:

- El modelo clasifica postura corporal y posición facial (§1).
- El split es aleatorio por fila, no por sesión de grabación ni por persona.
  Frames de una misma grabación caen a la vez en train y en test, así que el
  modelo puede memorizar el encuadre concreto en lugar de generalizar. Que
  `que_medicamentos_toma` obtenga 1.00 de precisión y recall es la señal típica
  de eso.

El `metrics.json` del modelo anterior (35×42) reporta accuracy 0.35 y
f1_macro 0.17.

**Al reentrenar:** separar por grabación/persona (`GroupShuffleSplit`) antes de
dar por buena ninguna métrica.

---

## Checklist para el reentrenamiento

- [ ] Regrabar el dataset con `app/utils/grabar_secuencia_lstm.py` corregido
- [ ] Verificar que las manos están presentes: `has_hands()` sobre una muestra
- [ ] Depurar etiquetas (typos, clases con pocas muestras, solapamientos)
- [ ] Split por grupo (grabación/persona), no aleatorio por fila
- [ ] Entrenar con `train_cnn_lstm_model.py` (ya aplica la normalización)
- [ ] Publicar `lstm_holistic.h5`, `label_encoder.pkl`, `classes.json`, `mean/std`
- [ ] Actualizar `artifacts/labels_catalog.json`
- [ ] Desplegar con `APPLY_FEATURE_NORMALIZATION=true`
