from pathlib import Path

import pandas as pd

# ─── Parámetros ────────────────────────────────────────────────
ARCHIVO_ENTRADA = Path("LISTADO_CONFLICTOS_ADREV.xlsx")
HOJA = 0  # o el nombre de la hoja
ARCHIVO_SALIDA = Path("LISTADO_LIMPIO.xlsx")
COLUMNA_OBJETIVO = "conflicting_percentage"
# ────────────────────────────────────────────────────────────────

# 1) Cargar Excel
df = pd.read_excel(ARCHIVO_ENTRADA, sheet_name=HOJA)

# 2) Limpiar la columna
patron = r"Adrev Publishing:\d+\.\d+"
df[COLUMNA_OBJETIVO] = (
    df[COLUMNA_OBJETIVO]
    .astype(str)  # por si hay números/NaN
    .str.replace(patron, "", regex=True)  # quita el texto-número
    .str.strip()  # remueve espacios sobrantes
    .replace({"": pd.NA})  # vuelve a dejar celda vacía si quedó vacía
)

# 3) Guardar resultado
df.to_excel(ARCHIVO_SALIDA, index=False)
print("✅ Archivo limpio guardado en", ARCHIVO_SALIDA)
