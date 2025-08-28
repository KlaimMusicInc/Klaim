#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inserta o actualiza codigo_MLC en subidas_plataforma
siguiendo el mapeo COD_KLAIM ↔︎ MLC SONG CODE.
Si el cod_klaim existe en obras pero no en subidas_plataforma,
crea el registro con los valores por defecto solicitados.
"""

import sys
from datetime import date
from getpass import getpass
from pathlib import Path

import mysql.connector
import pandas as pd
from mysql.connector import Error, errorcode

# ───────────────────── Configuración rápida ───────────────────── #
EXCEL_FILE = Path("COD_MLC_COD_KLAIM.xlsx")  # nombre del Excel
SHEET_NAME = 0  # índice u hoja

DB_CFG = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",  # se pedirá si está vacío
    "database": "base_datos_klaim",
    "charset": "utf8mb4",
    "use_unicode": True,
    "autocommit": False,
}


# ────────────────────── Funciones auxiliares ──────────────────── #
def pedir_password(cfg):
    if not cfg.get("password"):
        cfg["password"] = getpass("Contraseña MySQL: ")
    return cfg


def leer_excel(path: Path, sheet):
    if not path.exists():
        sys.exit(f"❌ No se encontró el archivo {path}")
    df = pd.read_excel(
        path, sheet_name=sheet, dtype={"COD_KLAIM": "Int64", "MLC SONG CODE": str}
    ).dropna(subset=["COD_KLAIM", "MLC SONG CODE"])
    df["MLC SONG CODE"] = df["MLC SONG CODE"].str.strip()
    return df


def obra_existe(cur, obra_id: int) -> bool:
    cur.execute("SELECT 1 FROM obras WHERE cod_klaim = %s", (obra_id,))
    return cur.fetchone() is not None


def filas_subida(cur, obra_id: int):
    """Devuelve lista de id_subida existentes para la obra (ordenados)."""
    cur.execute(
        "SELECT id_subida FROM subidas_plataforma "
        "WHERE obra_id = %s ORDER BY id_subida ASC",
        (obra_id,),
    )
    return [row[0] for row in cur.fetchall()]


def actualizar_primera_fila(cur, id_subida: int, codigo_mlc: str) -> None:
    cur.execute(
        "UPDATE subidas_plataforma " "SET codigo_MLC = %s " "WHERE id_subida = %s",
        (codigo_mlc, id_subida),
    )


def insertar_fila(cur, obra_id: int, codigo_mlc: str) -> None:
    cur.execute(
        "INSERT INTO subidas_plataforma "
        "(obra_id, codigo_MLC, estado_MLC, fecha_subida, matching_tool) "
        "VALUES (%s, %s, 'OK', CURDATE(), 0)",
        (obra_id, codigo_mlc),
    )


# ──────────────────────────── Main ────────────────────────────── #
def main():
    df = leer_excel(EXCEL_FILE, SHEET_NAME)
    print(f"✔️  Filas a procesar: {len(df)}")

    cfg = pedir_password(DB_CFG.copy())

    try:
        with mysql.connector.connect(**cfg) as conn, conn.cursor() as cur:
            insertados = actualizados = sin_obra = 0
            warnings_dup = []

            for _, row in df.iterrows():
                obra_id = int(row["COD_KLAIM"])
                codigo_mlc = row["MLC SONG CODE"]

                if not obra_existe(cur, obra_id):
                    sin_obra += 1
                    print(f"⚠️  cod_klaim {obra_id} NO existe en obras → omitido")
                    continue

                ids_subida = filas_subida(cur, obra_id)

                if ids_subida:
                    if len(ids_subida) > 1:
                        warnings_dup.append(obra_id)
                    actualizar_primera_fila(cur, ids_subida[0], codigo_mlc)
                    actualizados += 1
                else:
                    insertar_fila(cur, obra_id, codigo_mlc)
                    insertados += 1

            conn.commit()

            # ──────────── Reporte ────────────
            print("\n======= RESUMEN =======")
            print(f"✅ Filas actualizadas : {actualizados}")
            print(f"➕ Filas insertadas   : {insertados}")
            print(f"🚫 Sin obra en BD     : {sin_obra}")
            if warnings_dup:
                print(f"⚠️  Duplicados encontrados en obra_id: {warnings_dup}")

    except Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("❌ Credenciales incorrectas o sin permiso.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("❌ La base de datos no existe.")
        else:
            print(f"❌ Error MySQL: {err}")
    except KeyboardInterrupt:
        print("\n⏹️  Operación cancelada.")
    except Exception as exc:
        print(f"❌ Error inesperado: {exc}")


if __name__ == "__main__":
    main()
