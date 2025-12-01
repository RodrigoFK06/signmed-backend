# Check class distribution in the cleaned dataset
import pandas as pd
from collections import Counter

csv_path = "data/dataset_medico.csv"

print("📊 Analizando distribución de clases en dataset_medico.csv...\n")

# Load without headers
df = pd.read_csv(csv_path, header=None)

# Last column is the label
label_col = df.shape[1] - 2  # -2 porque hay label y level
labels = df.iloc[:, label_col].astype(str)

# Count occurrences
dist = Counter(labels)

print(f"Total de filas: {len(df)}")
print(f"Total de clases: {len(dist)}\n")

print("Distribución por clase:")
print("-" * 50)

classes_with_one = []
classes_with_few = []

for label, count in sorted(dist.items(), key=lambda x: x[1]):
    status = ""
    if count == 1:
        status = " ⚠️ SOLO 1 MUESTRA - NO SE PUEDE USAR"
        classes_with_one.append(label)
    elif count < 5:
        status = f" ⚠️ MUY POCAS MUESTRAS"
        classes_with_few.append(label)
    
    print(f"  {label:30s}: {count:4d} muestras{status}")

print("\n" + "=" * 50)
print(f"\n❌ Clases con 1 sola muestra (deben eliminarse): {len(classes_with_one)}")
if classes_with_one:
    print(f"   {classes_with_one}")

print(f"\n⚠️ Clases con <5 muestras (recomendado eliminar): {len(classes_with_few)}")
if classes_with_few:
    print(f"   {classes_with_few}")

print(f"\n✅ Clases utilizables (>=2 muestras): {len(dist) - len(classes_with_one)}")

# Recommendation
if classes_with_one or classes_with_few:
    print("\n💡 RECOMENDACIÓN:")
    print("   Eliminar clases con pocas muestras para evitar este error.")
    print("   Mínimo recomendado: 5-10 muestras por clase para un buen entrenamiento.")
