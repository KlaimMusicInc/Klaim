"""
Cargar artistas e ISRC desde Excel a MySQL (versión DEBUG + tracking SGS).

Requisitos:
    pip install pandas mysql-connector-python openpyxl
"""

import getpass
import sys
from datetime import datetime
from pathlib import Path

import mysql.connector
import pandas as pd

# ───────────────────────── Ajustes rápidos ───────────────────────── #
EXCEL_FILE = Path("SAYCO_ISRC_OK_NORMALIZADOS_JULIO.xlsx")  # ruta de tu archivo
SHEET_NAME = 0  # índice o nombre de hoja
DEBUG = True  # deja True hasta estabilizar

DB_CFG = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",  # se pedirá si lo dejas vacío
    "database": "base_datos_klaim_dev",
    "charset": "utf8mb4",
    "use_unicode": True,
    "autocommit": False,
}


# ───────────────────────── Utilidades ───────────────────────── #
def log(msg):
    if DEBUG:
        print(msg)


def get_cnx(cfg):
    if not cfg["password"]:
        cfg["password"] = getpass.getpass("Contraseña MySQL: ")
    return mysql.connector.connect(**cfg)


def fetchone(cur, query, params):
    cur.execute(query, params)
    return cur.fetchone()


# ---------- Artistas únicos ---------- #
def get_or_create_artista_unico(cur, nombre):
    row = fetchone(
        cur,
        "SELECT id_artista_unico FROM artistas_unicos WHERE nombre_artista = %s",
        (nombre,),
    )
    if row:
        log(f"      🔎 Artista único ya existe ➜ id={row[0]}")
        return row[0], False

    cur.execute("INSERT INTO artistas_unicos (nombre_artista) VALUES (%s)", (nombre,))
    new_id = cur.lastrowid
    log(f"      ➕ Artista único creado ➜ id={new_id}")
    return new_id, True


# ---------- Vínculo artista-obra ---------- #
def link_artista_a_obra(cur, obra_id, artista_id, nombre_artista):
    if fetchone(
        cur,
        "SELECT 1 FROM artistas WHERE obra_id=%s AND id_artista_unico=%s",
        (obra_id, artista_id),
    ):
        log("      🔗 Vínculo artista-obra ya presente")
        return False

    cur.execute(
        """INSERT INTO artistas (nombre_artista, obra_id, id_artista_unico)
           VALUES (%s, %s, %s)""",
        (nombre_artista, obra_id, artista_id),
    )
    log("      ➕ Vínculo artista-obra insertado")
    return True


# ---------- ISRC ---------- #
def create_isrc(cur, obra_id, artista_id, codigo_isrc, nombre_alt, titulo_alt, rating):
    if fetchone(
        cur,
        """SELECT 1 FROM codigos_isrc
           WHERE obra_id=%s AND id_artista_unico=%s AND codigo_isrc=%s""",
        (obra_id, artista_id, codigo_isrc),
    ):
        log("      ⚠️  ISRC ya existía (obra_id + artista_id + isrc)")
        return False

    cur.execute(
        """INSERT INTO codigos_isrc
           (codigo_isrc, obra_id, id_artista_unico,
            name_artista_alternativo, titulo_alternativo,
            matching_tool_isrc, rating)
           VALUES (%s,%s,%s,%s,%s,0,%s)""",
        (
            codigo_isrc,
            obra_id,
            artista_id,
            nombre_alt or None,
            titulo_alt or None,
            rating or None,
        ),
    )
    log("      ➕ ISRC insertado")
    return True


# ---------- Fichero con SGS faltantes ---------- #
def write_missing_sgs_excel(missing_sgs: set, id_cliente: int):
    if not missing_sgs:
        log("🟢  No hay SGS faltantes; no se genera archivo.")
        return None

    out_name = (
        f"SGS_no_encontrados_cliente_{id_cliente}_" f"{datetime.now():%Y%m%d%H%M}.xlsx"
    )
    pd.DataFrame({"codigo_sgs": sorted(missing_sgs)}).to_excel(out_name, index=False)
    log(f"📂  Archivo creado: {out_name}")
    return out_name


# ───────────────────────── Programa principal ───────────────────────── #
def main():

    # 1) Leer Excel
    if not EXCEL_FILE.exists():
        print(f"❌  No encuentro el archivo: {EXCEL_FILE}")
        return

    df_raw = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, dtype=str).fillna("")
    df_raw.columns = df_raw.columns.str.lower()

    required_cols = {
        "codigo_sgs",
        "nombre_artista",
        "name_artista_alternativo",
        "titulo_alternativo",
        "codigo_isrc",
        "rating",
    }
    missing_cols = required_cols - set(df_raw.columns)
    if missing_cols:
        print("❌  Columnas faltantes en Excel:", ", ".join(missing_cols))
        return

    total_filas_excel = len(df_raw)
    sgs_unicos_excel = set(df_raw["codigo_sgs"].astype(str).str.strip())

    log(f"📄  Filas del Excel: {total_filas_excel}")
    log(f"🔢  SGS únicos en Excel: {len(sgs_unicos_excel)}")

    # 2) Conectar y pedir id_cliente
    cnx = get_cnx(DB_CFG)
    cur = cnx.cursor()
    try:
        id_cliente = int(input("🔢  Ingrese id_cliente: ").strip())
    except ValueError:
        print("❌  id_cliente inválido.")
        return

    if not fetchone(cur, "SELECT 1 FROM clientes WHERE id_cliente=%s", (id_cliente,)):
        print(f"❌  El cliente {id_cliente} no existe.")
        return
    log(f"✅  Cliente {id_cliente} verificado.")

    # 3) Mapping código_sgs → cod_klaim de las obras del cliente
    cur.execute(
        """SELECT o.codigo_sgs, o.cod_klaim
           FROM obras o
           JOIN catalogos c ON o.catalogo_id = c.id_catalogo
           WHERE c.id_cliente = %s""",
        (id_cliente,),
    )
    mapping = {str(k): v for k, v in cur.fetchall()}

    log(f"🔗  Obras encontradas para cliente: {len(mapping)}")

    sgs_en_bd = set(mapping.keys())
    sgs_matched = sgs_unicos_excel & sgs_en_bd
    sgs_missing = sgs_unicos_excel - sgs_en_bd

    log(f"✅  SGS que sí existen en BD: {len(sgs_matched)}")
    log(f"❌  SGS que NO existen en BD: {len(sgs_missing)}")

    archivo_faltantes = write_missing_sgs_excel(sgs_missing, id_cliente)

    # 4) Filtrar DataFrame
    df = df_raw[df_raw["codigo_sgs"].astype(str).str.strip().isin(sgs_matched)]
    log(f"🏷️  Filas después de filtrar por SGS del cliente: {len(df)}\n")

    if df.empty:
        print("⚠️  Ningún SGS del Excel coincide con las obras del cliente.")
        return

    # ---------- Contadores ----------
    nuevos_artist_unicos = nuevos_vinculos = nuevos_isrc = 0
    filas_procesadas = 0

    # 5) Procesar fila por fila
    for ix, row in df.iterrows():
        filas_procesadas += 1
        codigo_sgs = row["codigo_sgs"].strip()
        obra_id = mapping[codigo_sgs]

        log(f"\n🔸 Fila {ix} → SGS={codigo_sgs} ➜ obra_id={obra_id}")

        nombre_artista = row["nombre_artista"].strip()
        if not nombre_artista:
            log("    ⚠️  nombre_artista vacío, fila omitida")
            continue

        # Artista único
        artista_id, creado = get_or_create_artista_unico(cur, nombre_artista)
        if creado:
            nuevos_artist_unicos += 1

        # Vínculo obra-artista
        if link_artista_a_obra(cur, obra_id, artista_id, nombre_artista):
            nuevos_vinculos += 1

        # ISRC
        codigo_isrc = row["codigo_isrc"].strip()
        if not codigo_isrc:
            log("      ⚠️  ISRC vacío, no se inserta")
            continue

        if create_isrc(
            cur,
            obra_id,
            artista_id,
            codigo_isrc,
            row["name_artista_alternativo"].strip(),
            row["titulo_alternativo"].strip(),
            row["rating"].strip(),
        ):
            nuevos_isrc += 1

    # 6) Guardar / deshacer
    try:
        cnx.commit()
        log("\n💾  Cambios guardados en BD.")
    except mysql.connector.Error as e:
        cnx.rollback()
        print("❌  Error, se hizo rollback:", e)
        return
    finally:
        cur.close()
        cnx.close()

    # 7) Resumen
    print("\n========== RESUMEN ==========")
    print(f"Filas procesadas:              {filas_procesadas}")
    print(f"Artistas únicos nuevos:        {nuevos_artist_unicos}")
    print(f"Vínculos obra-artista nuevos:  {nuevos_vinculos}")
    print(f"ISRC insertados nuevos:        {nuevos_isrc}")
    print("================================")

    if archivo_faltantes:
        print(f"👉  Se generó el archivo con SGS faltantes: {archivo_faltantes}")


if __name__ == "__main__":
    main()
