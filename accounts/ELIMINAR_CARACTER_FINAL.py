import pandas as pd

# Cargar archivo Excel
df = pd.read_excel("CATALOGO_SACVEN_DICIEMBRE.xlsx")

# Eliminar ";" solo si está al final de la celda en la columna deseada
df["Artistas"] = df["Artistas"].str.rstrip(";")

# Guardar el archivo corregido
df.to_excel("archivo_corregido.xlsx", index=False)
