#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carga LISTADO_CONFLICTOS.xlsx, valida y crea registros en conflictos_plataforma
• Si custom_id no existe en subidas_plataforma  ➜ se guarda en df_no_encontrados
• Si ya existe un conflicto vigente para ese obra_id + ADREV ➜ df_ya_existentes
• Si pasa ambas validaciones            ➜ se inserta nuevo conflicto
Genera:
  ├─ custom_id_no_encontrados.xlsx
  └─ conflictos_existentes.xlsx
Imprime resumen final en consola.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import mysql.connector
import pandas as pd

# ───────────────────────── Parametrización ───────────────────────── #
EXCEL_FILE = Path("LISTADO_CONFLICTOS.xlsx")  # mismo directorio
OUTPUT_DIR = Path(".")
INFO_EXTRA = (
    "Se solicita por correo la documentación que respalde dicha administración."
)
PLATAFORMA = "ADREV"
ESTADO_DEFAULT = "vigente"
HOY = date.today()  # YYYY-MM-DD

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",
    "database": "base_datos_klaim",
    "port": 3306,
    "autocommit": False,
}


# ───────────────────────── Utilidades ───────────────────────── #
def to_decimal_or_none(value: str | int | float | None):
    """Convierte a Decimal; si está vacío o no numérico → None"""
    if pd.isna(value) or value == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


# ───────────────────────── Carga del Excel ───────────────────────── #
if not EXCEL_FILE.exists():
    raise FileNotFoundError(f"No se encontró {EXCEL_FILE.resolve()}")

df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
# Asegurar nombres de columna en mayúsculas / sin espacios accidentales
df.columns = [c.strip().upper() for c in df.columns]

required_cols = {"CUSTOM_ID", "CONTRAPARTE", "SHARE"}
missing = required_cols - set(df.columns)
if missing:
    raise ValueError(f"Faltan columnas requeridas en el Excel: {missing}")

# ───────────────────────── Conexión a MySQL ───────────────────────── #
cnx = mysql.connector.connect(**MYSQL_CONFIG)
cur = cnx.cursor(dictionary=True)

# Preparamos sentencias parametrizadas
SQL_OBRA = "SELECT obra_id FROM subidas_plataforma WHERE codigo_ADREV = %s LIMIT 1"
SQL_EXISTE = """
    SELECT id_conflicto
      FROM conflictos_plataforma
     WHERE obra_id = %s
       AND plataforma = %s
       AND estado_conflicto = %s
     LIMIT 1
"""
SQL_INSERT = """
    INSERT INTO conflictos_plataforma
        (obra_id, plataforma, nombre_contraparte, porcentaje_contraparte,
         informacion_adicional, fecha_conflicto, estado_conflicto)
    VALUES (%s,      %s,         %s,                 %s,
            %s,                  %s,           %s)
"""

# DataFrames para reportes
sin_obra_df = pd.DataFrame(columns=list(required_cols))
duplica_df = pd.DataFrame(columns=["custom_id", "obra_id", "CONTRAPARTE", "SHARE"])

procesadas = insertadas = omitidas_no_obra = omitidas_dup = 0

# ───────────────────────── Iteración principal ────────────────────── #
for ix, row in df.iterrows():
    procesadas += 1
    custom_id = str(row["CUSTOM_ID"]).strip()
    contraparte = (
        str(row["CONTRAPARTE"]).strip() if not pd.isna(row["CONTRAPARTE"]) else None
    )
    share = to_decimal_or_none(row["SHARE"])

    # 1. Buscar obra_id en subidas_plataforma
    cur.execute(SQL_OBRA, (custom_id,))
    res = cur.fetchone()
    if not res:
        print(f"[NO ENCONTRADO] custom_id {custom_id} no existe en subidas_plataforma")
        sin_obra_df.loc[len(sin_obra_df)] = [custom_id, contraparte, share]
        omitidas_no_obra += 1
        continue
    obra_id = res["obra_id"]

    # 2. Verificar duplicado en conflictos_plataforma
    cur.execute(SQL_EXISTE, (obra_id, PLATAFORMA, ESTADO_DEFAULT))
    if cur.fetchone():
        print(
            f"[EXISTENTE] Ya hay conflicto vigente para obra_id {obra_id} - {custom_id}"
        )
        duplica_df.loc[len(duplica_df)] = [custom_id, obra_id, contraparte, share]
        omitidas_dup += 1
        continue

    # 3. Insertar nuevo conflicto
    cur.execute(
        SQL_INSERT,
        (obra_id, PLATAFORMA, contraparte, share, INFO_EXTRA, HOY, ESTADO_DEFAULT),
    )
    insertadas += 1
    if insertadas % 100 == 0:
        cnx.commit()  # commits parciales para grandes volúmenes

# Commit final
cnx.commit()
cur.close()
cnx.close()

# ───────────────────────── Guardar reportes ───────────────────────── #
if not sin_obra_df.empty:
    sin_obra_file = OUTPUT_DIR / "custom_id_no_encontrados.xlsx"
    sin_obra_df.to_excel(sin_obra_file, index=False)
    print(f"→ Guardado listado de custom_id sin obra en {sin_obra_file}")

if not duplica_df.empty:
    duplica_file = OUTPUT_DIR / "conflictos_existentes.xlsx"
    duplica_df.to_excel(duplica_file, index=False)
    print(f"→ Guardado listado de conflictos ya existentes en {duplica_file}")

# ───────────────────────── Resumen final ──────────────────────────── #
print("\n──────── Resumen ────────")
print(f"Filas procesadas          : {procesadas}")
print(f"Conflictos insertados     : {insertadas}")
print(f"Omitidas (sin obra)       : {omitidas_no_obra}")
print(f"Omitidas (duplicadas)     : {omitidas_dup}")
print("Fin del proceso.")
