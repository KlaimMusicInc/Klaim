#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Actualiza la columna `codigo_MLC` en `subidas_plataforma` a partir
de un Excel de Musixmatch / MLC y genera tres reportes:

  1. ISWC no encontrados en el Excel
  2. Obras cuyo título no aparece en el Excel
  3. Obras cuyo título aparece pero ninguno de los autores coincide

• Sólo considera catálogos 'Activo'.
• Después de actualizar, marca `estado_MLC = 'OK'`.
"""

import getpass
# ───────────────────────── IMPORTS ──────────────────────────
import re
import sys
from pathlib import Path
from typing import List

import mysql.connector
import pandas as pd
from unidecode import unidecode

# ───────────────────────── CONFIG ───────────────────────────
EXCEL_FILE = Path("catalogo_sayce_mlc_julio.xlsx")
SHEET_NAME = 0

DB_CFG = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",  # deja vacío para que lo pida
    "database": "base_datos_klaim_dev",
    "charset": "utf8mb4",
    "use_unicode": True,
    "autocommit": False,
}

PUNCT_REGEX = re.compile(r"[.,;:()\[\]¿?¡!\"'´`]+")


# ───────────────────── FUNCIONES AUXILIARES ──────────────────
def normalize(text: str) -> str:
    """Minúsculas, quita acentos, puntuación, 'feat/featuring', y dobles espacios."""
    text = unidecode(text or "")
    text = text.lower()
    text = re.sub(r"\b(feat(\.|uring)?|ft\.)\b", " ", text)
    text = PUNCT_REGEX.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_writer_pairs(row: pd.Series) -> List[str]:
    """Extrae y normaliza WRITER LAST/FIRST NAME x -> ['nombre completo', ...]."""
    pairs = []
    for col in row.index:
        if col.startswith("WRITER LAST NAME"):
            suf = col.split("WRITER LAST NAME")[-1].strip()
            last_ = str(row[col]).strip()
            first_ = str(row.get(f"WRITER FIRST NAME {suf}", "")).strip()
            full = f"{first_} {last_}".strip()
            if full:
                pairs.append(normalize(full))
    return pairs


def all_words_in(short: str, long: str) -> bool:
    """True si cada palabra de `short` aparece (como sub-cadena) en `long`."""
    return all(word in long for word in short.split())


def author_match(a: str, writers: List[str]) -> bool:
    """
    Devuelve True si las palabras del nombre más corto aparecen
    (como sub-cadenas) en el nombre más largo.
    """
    a_norm = normalize(a)
    for w in writers:
        long_, short_ = (w, a_norm) if len(w) >= len(a_norm) else (a_norm, w)
        if all_words_in(short_, long_):
            return True
    return False


# ─────────────────────── CONEXIÓN DB ────────────────────────
if not DB_CFG["password"]:
    DB_CFG["password"] = getpass.getpass("Contraseña MySQL: ")

try:
    conn = mysql.connector.connect(**DB_CFG)
except mysql.connector.Error as err:
    sys.exit(f"⛔ Error al conectar: {err}")

cursor = conn.cursor(dictionary=True)

# ────────────────── INPUT ID_CLIENTE ────────────────────────
try:
    ID_CLIENTE = int(input("Ingresa el id_cliente a actualizar: ").strip())
except ValueError:
    sys.exit("⛔ Debes ingresar un número entero.")

# ─────────── 1. CATÁLOGOS ACTIVOS DEL CLIENTE ───────────────
cursor.execute(
    """
    SELECT id_catalogo
    FROM catalogos
    WHERE id_cliente = %s AND estado = 'Activo'
    """,
    (ID_CLIENTE,),
)
catalogos = [row["id_catalogo"] for row in cursor.fetchall()]
if not catalogos:
    sys.exit("⚠️  El cliente no tiene catálogos activos.")

# ─────────── 2. OBRAS SIN CODIGO_MLC ────────────────────────
fmt = ",".join(["%s"] * len(catalogos))
cursor.execute(
    f"""
    SELECT  o.cod_klaim AS obra_id,
            o.titulo,
            IFNULL(o.codigo_iswc, '') AS codigo_iswc
    FROM    obras o
    JOIN    subidas_plataforma s ON s.obra_id = o.cod_klaim
    WHERE   o.catalogo_id IN ({fmt})
      AND   (s.codigo_MLC IS NULL OR s.codigo_MLC = '')
    """,
    tuple(catalogos),
)
obras_pend = cursor.fetchall()
if not obras_pend:
    sys.exit("✅ No hay obras pendientes de actualizar para este cliente.")

grupo_iswc = [o for o in obras_pend if o["codigo_iswc"]]
grupo_sin_iswc = [o for o in obras_pend if not o["codigo_iswc"]]

# ─────────── 4. CARGAR EXCEL ────────────────────────────────
df_excel = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, dtype=str).fillna("")
excel_by_iswc = {
    str(r["ISWC"]).strip(): r for _, r in df_excel.iterrows() if str(r["ISWC"]).strip()
}
df_excel["__title_norm"] = df_excel["PRIMARY TITLE"].apply(normalize)

# ─────────── 5. LISTAS DE PENDIENTES ────────────────────────
nf_iswc, nf_title, nf_ta = [], [], []
updates = 0

# ─────────── 6. GRUPO A (CON ISWC) ──────────────────────────
for obra in grupo_iswc:
    row = excel_by_iswc.get(obra["codigo_iswc"])
    if row is None or not str(row["MLC SONG CODE"]).strip():
        nf_iswc.append(obra)
        continue

    cursor.execute(
        """
        UPDATE subidas_plataforma
        SET codigo_MLC = %s, estado_MLC = 'OK'
        WHERE obra_id = %s AND (codigo_MLC IS NULL OR codigo_MLC = '')
        """,
        (str(row["MLC SONG CODE"]).strip(), obra["obra_id"]),
    )
    updates += cursor.rowcount


# ─────────── 7. GRUPO B (SIN ISWC) ─────────────────────────
def autores_de_obra(obra_id: int) -> List[str]:
    cursor.execute(
        """
        SELECT au.nombre_autor
        FROM autoresunicos au
        JOIN obrasautores oa ON oa.autor_id = au.id_autor
        WHERE oa.obra_id = %s
        """,
        (obra_id,),
    )
    return [r["nombre_autor"] for r in cursor.fetchall()]


for obra in grupo_sin_iswc:
    title_norm = normalize(obra["titulo"])
    df_matches = df_excel[df_excel["__title_norm"] == title_norm]

    if df_matches.empty:
        nf_title.append(obra)
        continue

    autores_bd = autores_de_obra(obra["obra_id"])
    found = False

    for _, row in df_matches.iterrows():
        writers_norm = get_writer_pairs(row)
        if not writers_norm:
            continue

        if any(author_match(a, writers_norm) for a in autores_bd):
            codigo_mlc = str(row["MLC SONG CODE"]).strip()
            if codigo_mlc:
                cursor.execute(
                    """
                    UPDATE subidas_plataforma
                    SET codigo_MLC = %s, estado_MLC = 'OK'
                    WHERE obra_id = %s AND (codigo_MLC IS NULL OR codigo_MLC = '')
                    """,
                    (codigo_mlc, obra["obra_id"]),
                )
                updates += cursor.rowcount
                found = True
                break

    if not found:
        obra_copy = obra.copy()
        obra_copy["autores_bd"] = " | ".join(autores_bd)
        nf_ta.append(obra_copy)

# ─────────── 8. COMMIT Y REPORTES ───────────────────────────
conn.commit()
cursor.close()
conn.close()

print(f"✅ Actualizaciones realizadas: {updates}")

writer = pd.ExcelWriter("reporte_no_encontrados.xlsx", engine="openpyxl")
if nf_iswc:
    pd.DataFrame(nf_iswc).to_excel(
        writer, index=False, sheet_name="ISWC_NO_ENCONTRADOS"
    )
if nf_title:
    pd.DataFrame(nf_title).to_excel(
        writer, index=False, sheet_name="TITULO_NO_ENCONTRADOS"
    )
if nf_ta:
    pd.DataFrame(nf_ta).to_excel(
        writer, index=False, sheet_name="TITULO_AUTOR_NO_MATCH"
    )
writer.close()
print("📄 Se generó 'reporte_no_encontrados.xlsx' con los pendientes.")
