#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exporta un “bulk” de obras sin código MLC para un cliente dado.
Requisitos:  pip install pandas mysql-connector-python openpyxl
"""

import getpass
import sys
from pathlib import Path
from typing import List

import mysql.connector
import pandas as pd
from mysql.connector import errorcode

# ───────────────────────── Configuración ───────────────────────── #
DB_CFG = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",  # Si lo dejas vacío, se pide por consola
    "database": "base_datos_klaim_dev",
    "charset": "utf8mb4",
    "use_unicode": True,
    "autocommit": False,
}
OUTPUT_DIR = Path(".")  # Carpeta donde se crea el Excel


# ───────────────────────── Funciones auxiliares ───────────────────────── #
def get_connection(cfg: dict):
    if not cfg["password"]:
        cfg["password"] = getpass.getpass("Contraseña MySQL: ")
    try:
        conn = mysql.connector.connect(**cfg)
        return conn, conn.cursor(dictionary=True)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            sys.exit("Credenciales MySQL incorrectas.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            sys.exit(f"No existe la base de datos: {cfg['database']}")
        else:
            sys.exit(str(err))


def pad_df(df: pd.DataFrame, target_len: int) -> pd.DataFrame:
    if len(df) == 0:
        df = pd.DataFrame([["######"] * df.shape[1]], columns=df.columns)
    while len(df) < target_len:
        df = pd.concat(
            [df, pd.DataFrame([["######"] * df.shape[1]], columns=df.columns)],
            ignore_index=True,
        )
    return df.reset_index(drop=True)


def fetch_one(cursor, query: str, params=None):
    cursor.execute(query, params or ())
    return cursor.fetchone()


def fetch_all(cursor, query: str, params=None) -> List[dict]:
    cursor.execute(query, params or ())
    return cursor.fetchall()


# ───────────────────────── Script principal ───────────────────────── #
def main():
    conn, cur = get_connection(DB_CFG)
    try:
        id_cliente = input("ID del cliente: ").strip()
        if not id_cliente.isdigit():
            sys.exit("El id_cliente debe ser un número entero positivo.")

        # 1) Validar cliente
        if not fetch_one(
            cur, "SELECT 1 FROM clientes WHERE id_cliente=%s", (id_cliente,)
        ):
            sys.exit(f"No existe el cliente con id_cliente={id_cliente}.")

        # 2) Catálogos activos del cliente
        cur.execute(
            """
            SELECT id_catalogo
            FROM catalogos
            WHERE id_cliente=%s AND estado='Activo'
            """,
            (id_cliente,),
        )
        id_catalogos = [str(r["id_catalogo"]) for r in cur.fetchall()]
        if not id_catalogos:
            sys.exit("El cliente no tiene catálogos activos.")

        # 3) Obras SIN código_MLC  (FIX → usamos catalogo_id)
        formato_in = ",".join(["%s"] * len(id_catalogos))
        cur.execute(
            f"""
            SELECT o.cod_klaim AS obra_id
            FROM obras o
            WHERE o.catalogo_id IN ({formato_in})
              AND NOT EXISTS (
                  SELECT 1
                  FROM subidas_plataforma sp
                  WHERE sp.obra_id = o.cod_klaim
                    AND sp.codigo_MLC IS NOT NULL
                    AND sp.codigo_MLC <> ''
              )
            """,
            id_catalogos,
        )
        obra_ids = [row["obra_id"] for row in cur.fetchall()]
        if not obra_ids:
            sys.exit("No hay obras que cumplan las condiciones.")

        print(f"Se procesarán {len(obra_ids)} obras…")
        piezas = []

        for idx, obra_id in enumerate(obra_ids, 1):
            # (a) Datos principales
            row = fetch_one(
                cur,
                """
                SELECT titulo,
                       COALESCE(codigo_iswc, '') AS codigo_iswc,
                       codigo_sgs
                FROM obras
                WHERE cod_klaim=%s
                """,
                (obra_id,),
            )
            df_obras = pd.DataFrame(
                [[row["titulo"], row["codigo_iswc"], row["codigo_sgs"]]],
                columns=["titulo", "codigo_iswc", "codigo_sgs"],
            )

            # (b) Autores  (FIX → join por autor_id / id_autor)
            autores = fetch_all(
                cur,
                """
                SELECT au.nombre_autor,
                       oa.porcentaje_autor,
                       COALESCE(au.codigo_ipi, '') AS codigo_ipi
                FROM obrasautores oa
                JOIN autoresunicos au
                  ON oa.autor_id = au.id_autor
                WHERE oa.obra_id=%s
                """,
                (obra_id,),
            )
            df_autores = pd.DataFrame(
                autores,
                columns=["nombre_autor", "porcentaje_autor", "codigo_ipi"],
            )

            # (c) Artistas
            artistas_directos = fetch_all(
                cur,
                "SELECT nombre_artista FROM artistas WHERE obra_id=%s",
                (obra_id,),
            )
            artistas_isrc = fetch_all(
                cur,
                """
                SELECT DISTINCT au.nombre_artista
                FROM codigos_isrc ci
                JOIN artistas_unicos au
                  ON ci.id_artista_unico = au.id_artista_unico
                WHERE ci.obra_id=%s
                """,
                (obra_id,),
            )
            nombres_artistas = {r["nombre_artista"] for r in artistas_directos}.union(
                {r["nombre_artista"] for r in artistas_isrc}
            )
            df_artistas = pd.DataFrame(
                [[n] for n in sorted(nombres_artistas)],
                columns=["nombre_artista"],
            )

            # (d) ISRC
            isrcs = fetch_all(
                cur,
                "SELECT codigo_isrc FROM codigos_isrc WHERE obra_id=%s",
                (obra_id,),
            )
            df_isrc = pd.DataFrame(isrcs, columns=["codigo_isrc"])

            # (e) Normalizar tamaños
            max_rows = max(
                len(df_obras), len(df_autores), len(df_artistas), len(df_isrc)
            )
            df_obras = pad_df(df_obras, max_rows)
            df_autores = pad_df(df_autores, max_rows)
            df_artistas = pad_df(df_artistas, max_rows)
            df_isrc = pad_df(df_isrc, max_rows)

            # (f) Unión horizontal y acumulación
            piezas.append(
                pd.concat([df_obras, df_autores, df_artistas, df_isrc], axis=1)
            )

            if idx % 500 == 0 or idx == len(obra_ids):
                print(f"  • Procesadas {idx}/{len(obra_ids)} obras")

        bulk_mlc = pd.concat(piezas, axis=0, ignore_index=True)

        # 4) Exportar
        outfile = OUTPUT_DIR / f"bulk_mlc_{id_cliente}.xlsx"
        bulk_mlc.to_excel(outfile, index=False)
        print(f"\nArchivo generado: {outfile.resolve()}")

        conn.commit()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
