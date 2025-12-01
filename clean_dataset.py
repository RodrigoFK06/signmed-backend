# Script para limpiar dataset_medico.csv
# Elimina filas con formato antiguo (1472 columnas) y mantiene solo Holistic (5252 columnas)

import os
import shutil
from datetime import datetime

csv_path = "data/dataset_medico.csv"
backup_path = f"data/dataset_medico_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

print(f"📂 Creando backup en: {backup_path}")
shutil.copy(csv_path, backup_path)

print(f"🔍 Filtrando dataset...")
valid_rows = 0
removed_rows = 0

with open(csv_path, 'r', encoding='utf-8') as infile:
    with open("data/dataset_medico_temp.csv", 'w', encoding='utf-8') as outfile:
        for line_num, line in enumerate(infile, 1):
            cols = line.count(',') + 1  # número de columnas
            
            if cols == 5252:
                outfile.write(line)
                valid_rows += 1
            else:
                removed_rows += 1
                if removed_rows <= 5:  # mostrar primeras 5 eliminadas
                    print(f"   ❌ Línea {line_num}: {cols} columnas (eliminada)")

# Reemplazar archivo original con el limpio
os.replace("data/dataset_medico_temp.csv", csv_path)

print(f"\n✅ Limpieza completada:")
print(f"   ✔ Filas válidas (5252 cols): {valid_rows}")
print(f"   ✘ Filas eliminadas: {removed_rows}")
print(f"   💾 Backup guardado en: {backup_path}")
print(f"\n🚀 Ahora puedes ejecutar: python -m app.train_cnn_lstm_model")
