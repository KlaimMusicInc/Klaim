import pandas as pd

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN
EXCEL_FILE = (
    "catalogo_sayce_mlc_julio.xlsx"  # Asegúrate de que esté en el mismo directorio
)
SHEET_NAME = 0  # Si solo tiene una hoja, puedes dejarlo en 0
VALUE_TO_SEARCH = "SAYCE (SOCIEDAD DE AUTORES Y COMPOSITORES DE ECUADOR)"

# ─────────────────────────────────────────────────────────
# LEER ARCHIVO
df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, dtype=str)
df.fillna("", inplace=True)  # Evita errores con celdas vacías

# ─────────────────────────────────────────────────────────
# FILTRAR FILAS
matching_rows = []
non_matching_rows = []

for idx, row in df.iterrows():
    if any(VALUE_TO_SEARCH in str(cell) for cell in row):
        matching_rows.append(row)
    else:
        non_matching_rows.append(row)

df_matching = pd.DataFrame(matching_rows)
df_non_matching = pd.DataFrame(non_matching_rows)

# ─────────────────────────────────────────────────────────
# GUARDAR RESULTADOS EN EXCEL
output_file = "resultado_saycE_filas_filtradas.xlsx"
with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    df_matching.to_excel(writer, index=False, sheet_name="Filas_CON_SAYCE")
    df_non_matching.to_excel(writer, index=False, sheet_name="Filas_SIN_SAYCE")
