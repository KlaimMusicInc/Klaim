#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exporta un “bulk” de obras SIN código ADREV para un cliente dado,
en una sola fila por obra con listas separadas por '|'.

Requisitos:
    pip install pandas mysql-connector-python openpyxl
"""

import getpass
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Dict, Iterable, List

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
OUTPUT_DIR = Path(".")
CHUNK = 1000  # Tamaño de lote para consultas IN (...)


# ───────────────────────── Utilidades ───────────────────────── #
def get_connection(cfg: dict):
    if not cfg.get("password"):
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


def chunked(iterable: List[int], n: int):
    for i in range(0, len(iterable), n):
        yield iterable[i : i + n]


def join_pipe(values: Iterable[str]) -> str:
    clean = []
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        s = s.replace("|", " ")  # evitar romper separador
        if s:
            clean.append(s)
    return "|".join(clean)


def d2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)


# ───────────────────────── Carga de IDs de obra ───────────────────────── #
def obtener_obras_sin_adrev(cur, id_cliente: int) -> List[int]:
    """
    Retorna cod_klaim de obras del cliente (catálogos 'Activo') que:
      - NO tengan ningún codigo_ADREV no vacío en subidas_plataforma
      - NO estén 'vigente' en obras_liberadas
    """
    cur.execute(
        """
        SELECT o.cod_klaim
        FROM obras o
        JOIN catalogos c ON o.catalogo_id = c.id_catalogo
        WHERE c.id_cliente = %s
          AND c.estado = 'Activo'
          AND NOT EXISTS (
              SELECT 1
              FROM subidas_plataforma sp
              WHERE sp.obra_id = o.cod_klaim
                AND sp.codigo_ADREV IS NOT NULL
                AND sp.codigo_ADREV <> ''
          )
          AND NOT EXISTS (
              SELECT 1
              FROM obras_liberadas ol
              WHERE ol.cod_klaim = o.cod_klaim
                AND ol.estado_liberacion = 'vigente'
          )
        """,
        (id_cliente,),
    )
    return [r["cod_klaim"] for r in cur.fetchall()]


# ───────────────────────── Cargas en bloque ───────────────────────── #
def cargar_obras_base(cur, obra_ids: List[int]) -> Dict[int, dict]:
    base = {}
    for lote in chunked(obra_ids, CHUNK):
        fmt = ",".join(["%s"] * len(lote))
        cur.execute(
            f"""
            SELECT cod_klaim, titulo,
                   COALESCE(codigo_iswc,'') AS codigo_iswc,
                   codigo_sgs
            FROM obras
            WHERE cod_klaim IN ({fmt})
            """,
            lote,
        )
        for r in cur.fetchall():
            base[r["cod_klaim"]] = {
                "titulo": r["titulo"],
                "codigo_iswc": r["codigo_iswc"],
                "codigo_sgs": r["codigo_sgs"],
            }
    return base


def cargar_autores_y_total(cur, obra_ids: List[int]) -> Dict[int, dict]:
    """
    Devuelve por obra_id:
      { 'autores': [nombres], 'total': Decimal suma_total }
    (Suma por autor_id por si hay duplicados; exporta solo la suma total)
    """
    res: Dict[int, dict] = {}
    for lote in chunked(obra_ids, CHUNK):
        fmt = ",".join(["%s"] * len(lote))
        cur.execute(
            f"""
            SELECT
                oa.obra_id,
                au.id_autor,
                au.nombre_autor,
                oa.porcentaje_autor
            FROM obrasautores oa
            JOIN autoresunicos au ON oa.autor_id = au.id_autor
            WHERE oa.obra_id IN ({fmt})
            """,
            lote,
        )
        rows = cur.fetchall()
        # agrupar por obra → por autor
        by_obra: Dict[int, Dict[int, dict]] = {}
        for r in rows:
            obra_id = r["obra_id"]
            aid = r["id_autor"]
            if obra_id not in by_obra:
                by_obra[obra_id] = {}
            if aid not in by_obra[obra_id]:
                by_obra[obra_id][aid] = {
                    "nombre": r["nombre_autor"],
                    "suma": Decimal("0"),
                }
            by_obra[obra_id][aid]["suma"] += Decimal(str(r["porcentaje_autor"]))

        for obra_id, autores_map in by_obra.items():
            # ordenar por nombre para consistencia
            orden = sorted(
                autores_map.values(), key=lambda info: info["nombre"].strip().lower()
            )
            nombres = [x["nombre"] for x in orden]
            total_raw = sum((x["suma"] for x in orden), Decimal("0"))
            # regla de tolerancia
            if total_raw > Decimal("100") and total_raw < Decimal("100.5"):
                total = Decimal("100.00")
            else:
                total = d2(total_raw)
            res[obra_id] = {"autores": nombres, "total": total}

    # obras sin autores
    for oid in obra_ids:
        if oid not in res:
            res[oid] = {"autores": [], "total": Decimal("0.00")}
    return res


def cargar_artistas(cur, obra_ids: List[int]) -> Dict[int, List[str]]:
    out: Dict[int, set] = {oid: set() for oid in obra_ids}

    # Artistas directos
    for lote in chunked(obra_ids, CHUNK):
        fmt = ",".join(["%s"] * len(lote))
        cur.execute(
            f"""
            SELECT obra_id, nombre_artista
            FROM artistas
            WHERE obra_id IN ({fmt})
            """,
            lote,
        )
        for r in cur.fetchall():
            out[r["obra_id"]].add((r["nombre_artista"] or "").strip())

    # Artistas desde ISRC
    for lote in chunked(obra_ids, CHUNK):
        fmt = ",".join(["%s"] * len(lote))
        cur.execute(
            f"""
            SELECT ci.obra_id, au.nombre_artista
            FROM codigos_isrc ci
            JOIN artistas_unicos au
              ON ci.id_artista_unico = au.id_artista_unico
            WHERE ci.obra_id IN ({fmt})
            """,
            lote,
        )
        for r in cur.fetchall():
            out[r["obra_id"]].add((r["nombre_artista"] or "").strip())

    return {k: sorted(v) for k, v in out.items()}


def cargar_isrcs(cur, obra_ids: List[int]) -> Dict[int, List[str]]:
    out: Dict[int, List[str]] = {oid: [] for oid in obra_ids}
    for lote in chunked(obra_ids, CHUNK):
        fmt = ",".join(["%s"] * len(lote))
        cur.execute(
            f"""
            SELECT obra_id, codigo_isrc
            FROM codigos_isrc
            WHERE obra_id IN ({fmt})
            """,
            lote,
        )
        for r in cur.fetchall():
            if r["codigo_isrc"]:
                out[r["obra_id"]].append(r["codigo_isrc"].strip())
    return {k: sorted(set(v)) for k, v in out.items()}


# ───────────────────────── Principal ───────────────────────── #
def main():
    conn, cur = get_connection(DB_CFG)
    try:
        raw = input("ID del cliente: ").strip()
        if not raw.isdigit():
            sys.exit("El id_cliente debe ser un número entero positivo.")
        id_cliente = int(raw)

        # Validar cliente
        cur.execute("SELECT 1 FROM clientes WHERE id_cliente=%s", (id_cliente,))
        if not cur.fetchone():
            sys.exit(f"No existe el cliente con id_cliente={id_cliente}.")

        obra_ids = obtener_obras_sin_adrev(cur, id_cliente)
        if not obra_ids:
            sys.exit(
                "No hay obras que cumplan las condiciones (sin ADREV y no liberadas vigentes)."
            )

        print(f"Se procesarán {len(obra_ids)} obras…")

        base = cargar_obras_base(cur, obra_ids)
        autores_info = cargar_autores_y_total(cur, obra_ids)
        artistas = cargar_artistas(cur, obra_ids)
        isrcs = cargar_isrcs(cur, obra_ids)

        filas = []
        omitidas = 0
        for oid in obra_ids:
            info = base.get(oid, {})
            aut = autores_info.get(oid, {"autores": [], "total": Decimal("0.00")})

            # Omisión por superar 100.5
            if aut["total"] >= Decimal("100.50") and aut["total"] != Decimal("100.00"):
                print(
                    f"[OMITIDA] Obra {oid} ('{info.get('titulo','?')}'): suma porcentajes = {aut['total']} ≥ 100.5"
                )
                omitidas += 1
                continue

            fila = {
                "cod_klaim": oid,
                "titulo": info.get("titulo", ""),
                "codigo_iswc": info.get("codigo_iswc", ""),
                "codigo_sgs": info.get("codigo_sgs", ""),
                "autores": join_pipe(aut["autores"]),
                "porcentaje_autores": f"{d2(aut['total']):.2f}",
                "artistas": join_pipe(artistas.get(oid, [])),
                "codigos_isrc": join_pipe(isrcs.get(oid, [])),
            }
            filas.append(fila)

        if not filas:
            sys.exit(
                "Todas las obras fueron omitidas por reglas de validación (p.ej., porcentajes ≥ 100.5)."
            )

        df = pd.DataFrame(
            filas,
            columns=[
                "cod_klaim",
                "titulo",
                "codigo_iswc",
                "codigo_sgs",
                "autores",
                "porcentaje_autores",
                "artistas",
                "codigos_isrc",
            ],
        )

        outfile = OUTPUT_DIR / f"bulk_adrev_{id_cliente}.xlsx"
        df.to_excel(outfile, index=False)
        print(f"\nArchivo generado: {outfile.resolve()}")
        if omitidas:
            print(f"Aviso: {omitidas} obra(s) omitida(s) por superar 100.5%.")

        conn.commit()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
