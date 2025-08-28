"""
Script: cargar_codigo_adrev.py
Descripción
-----------
Lee el libro de Excel CATALOGO_ADREV.xlsx (hojas SAYCO, SACVEN y SAYCE);
• Cuando la fila trae ISWC → usa el ISWC para localizar la obra y actualizar/insertar
  el código_ADREV (=custom_id) en subidas_plataforma.
• Cuando la fila NO trae ISWC → usa (title + writers) para ubicar la obra con ayuda
  de las tablas obras, obrasautores y autoresunicos.
Genera:
  – iswc_not_found.xlsx                ← ISWC’s que no existen en la BD
  – «titulo»_«writers».xlsx (n‑m)      ← títulos sin coincidencia por autores
Reglas clave
------------
* Normalización “ligera” para ISWC, títulos y autores:     ─→ solo mayúsculas,
  sin tildes, sin guiones, puntos ni espacios repetidos.
* Si el custom_id aparece repetido dentro del Excel → avisa y omite la fila.
* Si ya existe un registro en subidas_plataforma:
      – Se sobreescribe código_ADREV.
* Commit por lotes de 1 000 operaciones (buen compromiso rendimiento/seguridad).
Requisitos
----------
pip install pandas openpyxl mysql-connector-python unidecode
(ejecutar dentro del entorno KLAIM)
"""

"""
Script: cargar_codigo_adrev.py   (versión corregida)
─ Inserta/actualiza codigo_ADREV partiendo de CATALOGO_ADREV.xlsx
"""
import re
import string
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import mysql.connector
import pandas as pd
from unidecode import unidecode

# ───────────────────────── Parametrización ───────────────────────── #
EXCEL_FILE = Path("CATALOGO_ADREV.xlsx")
SHEETS = ["SAYCO", "SACVEN", "SAYCE"]
OUTPUT_DIR = Path(".")

mysql_config = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",
    "database": "base_datos_klaim",
    "autocommit": False,
}

BATCH_SIZE = 1_000  # commits parciales


# ──────────────────────── Funciones auxiliares ───────────────────── #
def normalize_iswc(iswc: str) -> str:
    if not isinstance(iswc, str):
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", iswc).upper().strip()


def _strip_accents(text: str) -> str:
    return unidecode(text)


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = _strip_accents(text).upper()
    text = re.sub(rf"[{re.escape(string.punctuation)}]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sanitize_filename(name: str, max_len: int = 100) -> str:
    name = normalize_text(name)
    name = re.sub(r"[^A-Z0-9]+", "_", name)
    return name[:max_len] or "SIN_NOMBRE"


def save_if_not_empty(df: pd.DataFrame, path: Path):
    if not df.empty:
        df.to_excel(path, index=False)


# ───────────────────────── Conexión BD ───────────────────────────── #
print("➜ Conectando a MySQL…")
cnx = mysql.connector.connect(**mysql_config)
cur = cnx.cursor(dictionary=True)

# ─────────────────── Carga datos de referencia ───────────────────── #
print("➜ Cargando tabla OBRAS…")
cur.execute(
    """
    SELECT cod_klaim AS obra_id,
           codigo_iswc AS raw_iswc,
           titulo
    FROM obras
"""
)
obras_rows = cur.fetchall()

dict_iswc_to_obra: Dict[str, int] = {}
dict_title_to_obras: Dict[str, List[int]] = {}
for row in obras_rows:
    obra_id = row["obra_id"]
    norm_iswc = normalize_iswc(row["raw_iswc"])
    if norm_iswc:
        dict_iswc_to_obra[norm_iswc] = obra_id

    norm_title = normalize_text(row["titulo"])
    dict_title_to_obras.setdefault(norm_title, []).append(obra_id)

print(f"   → {len(dict_iswc_to_obra):,} ISWC indexados.")
print(f"   → {len(dict_title_to_obras):,} títulos únicos indexados.")

print("➜ Cargando autores por obra…")
cur.execute(
    """
    SELECT oa.obra_id,
           au.nombre_autor
    FROM obrasautores oa
    JOIN autoresunicos au ON au.id_autor = oa.autor_id
"""
)
dict_obra_to_authors: Dict[int, Set[str]] = {}
for row in cur:
    obra_id = row["obra_id"]
    norm_author = normalize_text(row["nombre_autor"])
    dict_obra_to_authors.setdefault(obra_id, set()).add(norm_author)

print(f"   → Autores indexados para {len(dict_obra_to_authors):,} obras.")

print("➜ Indexando subidas_plataforma existentes…")
cur.execute(
    """
    SELECT obra_id, codigo_ADREV
    FROM subidas_plataforma
"""
)
existing_subidas = {row["obra_id"]: row["codigo_ADREV"] or "" for row in cur}
print(f"   → {len(existing_subidas):,} registros de subidas_plataforma.")

# ───────────────────── Contenedores globales ────────────────────── #
iswc_not_found: List[Tuple[str, str]] = []  # (custom_id, iswc)
duplicate_custom_ids: Set[str] = set()
title_not_found: List[Tuple[str, str, str]] = []  # (title, writers, custom_id)

updates: List[Tuple[str, int]] = []  # (codigo_ADREV, obra_id)
pending_inserts: Dict[int, str] = {}  # obra_id → codigo_ADREV
duplicates_by_obra: Dict[int, List[str]] = {}  # obra_id → [custom_id,…]


# ─────────────────────── Funciones de soporte ───────────────────── #
def apply_update_insert(obra_id: int, custom_id: str):
    cur.execute(
        "SELECT obra_id FROM subidas_plataforma WHERE codigo_ADREV = %s LIMIT 1",
        (custom_id,),
    )
    row_same_code = cur.fetchone()
    if row_same_code and row_same_code["obra_id"] != obra_id:
        print(
            f"   ⚠️ custom_id {custom_id} ya ligado a obra_id={row_same_code['obra_id']}; se omite para obra_id={obra_id}."
        )
        return

    if obra_id in existing_subidas:
        updates.append((custom_id, obra_id))
        existing_subidas[obra_id] = custom_id
    elif obra_id in pending_inserts:
        duplicates_by_obra.setdefault(obra_id, [pending_inserts[obra_id]]).append(
            custom_id
        )
    else:
        pending_inserts[obra_id] = custom_id


def flush_batches():
    if not updates and not pending_inserts:
        return
    print(f"   ↳ Aplicando {len(updates)} updates + {len(pending_inserts)} inserts…")

    if updates:
        cur.executemany(
            "UPDATE subidas_plataforma SET codigo_ADREV = %s WHERE obra_id = %s",
            updates,
        )
    if pending_inserts:
        cur.executemany(
            "INSERT INTO subidas_plataforma (obra_id, codigo_ADREV) VALUES (%s, %s)",
            list(pending_inserts.items()),
        )
        existing_subidas.update(pending_inserts)

    cnx.commit()
    updates.clear()
    pending_inserts.clear()


# ───────────────────── Procesamiento principal ──────────────────── #
total_rows = 0
batch_counter = 0
seen_custom_ids: Set[str] = set()

for sheet in SHEETS:
    print(
        f"\n───────────────────────────────────────────────\nProcesando hoja «{sheet}»…"
    )
    df = pd.read_excel(EXCEL_FILE, sheet_name=sheet, dtype=str)

    for _, row in df.iterrows():
        total_rows += 1

        # Extrae valores respetando NaN
        iswc_raw = row.get("iswc")
        title_raw = row.get("title")
        writers_raw = row.get("writers")

        iswc = "" if pd.isna(iswc_raw) else str(iswc_raw).strip()
        title = "" if pd.isna(title_raw) else str(title_raw).strip()
        writers = "" if pd.isna(writers_raw) else str(writers_raw).strip()

        custom_id = str(row.get("custom_id", "")).strip()

        if custom_id in seen_custom_ids:
            duplicate_custom_ids.add(custom_id)
            continue
        seen_custom_ids.add(custom_id)

        # 1️⃣ Con ISWC
        if iswc:
            obra_id = dict_iswc_to_obra.get(normalize_iswc(iswc))
            if obra_id:
                apply_update_insert(obra_id, custom_id)
            else:
                iswc_not_found.append((custom_id, iswc))
        # 2️⃣ Sin ISWC
        else:
            norm_title = normalize_text(title)
            candidate_obras = dict_title_to_obras.get(norm_title, [])

            if not candidate_obras:
                title_not_found.append((title, writers, custom_id))
                continue

            parts = [normalize_text(p) for p in writers.split("|") if p.strip()]
            matched_obra = None
            for obra in candidate_obras:
                authors_set = dict_obra_to_authors.get(obra, set())
                if any(part in authors_set for part in parts):
                    matched_obra = obra
                    break

            if matched_obra:
                apply_update_insert(matched_obra, custom_id)
            else:
                records = []
                for obra in candidate_obras:
                    autores = dict_obra_to_authors.get(obra, set()) or {"—SIN AUTORES—"}
                    records.append(
                        {
                            "obra_id": obra,
                            "titulo": title,
                            "autores_asociados": "|".join(sorted(autores)),
                        }
                    )
                unmatched_filename = OUTPUT_DIR / (
                    f"{sanitize_filename(title)}_{sanitize_filename(writers)}_{sanitize_filename(custom_id)}.xlsx"
                )
                save_if_not_empty(pd.DataFrame(records), unmatched_filename)

        batch_counter += 1
        if batch_counter >= BATCH_SIZE:
            flush_batches()
            batch_counter = 0

flush_batches()

# ─────────────────────── Archivos de salida ────────────────────── #
if iswc_not_found:
    nf_path = OUTPUT_DIR / "iswc_not_found.xlsx"
    pd.DataFrame(iswc_not_found, columns=["custom_id", "iswc"]).to_excel(
        nf_path, index=False
    )
    print(f"➜ ISWC no encontrados guardados en {nf_path}")

if title_not_found:
    tn_path = OUTPUT_DIR / "title_not_found.xlsx"
    pd.DataFrame(title_not_found, columns=["title", "writers", "custom_id"]).to_excel(
        tn_path, index=False
    )
    print(f"➜ Títulos sin ninguna coincidencia guardados en {tn_path}")

if duplicates_by_obra:
    dup_rows = [
        {"obra_id": obra, "custom_ids": "|".join(customs)}
        for obra, customs in duplicates_by_obra.items()
        if len(customs) > 1
    ]
    dup_path = OUTPUT_DIR / "custom_ids_duplicados_por_obra.xlsx"
    pd.DataFrame(dup_rows).to_excel(dup_path, index=False)
    print(f"➜ custom_id duplicados por obra guardados en {dup_path}")

if duplicate_custom_ids:
    print(
        f"⚠️ Se ignoraron {len(duplicate_custom_ids)} custom_id duplicados dentro del Excel: "
        f"{', '.join(list(duplicate_custom_ids)[:10])} …"
    )

print(f"\n✓ Proceso completado. Filas procesadas: {total_rows:,}")
print("   ¡Listo!")
