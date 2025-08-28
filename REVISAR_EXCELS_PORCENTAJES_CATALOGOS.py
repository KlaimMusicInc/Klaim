#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detecta obras cuya suma de porcentajes de autor supera 100 %.

Crea un archivo  <nombre_catálogo>_sobre100.xlsx  con:
    SGS · Título · Suma_% · Detalle_Filas

Si no hay sobre-100, solo imprime “Sin incidencias”.
"""

from pathlib import Path

import pandas as pd

# --- rutas de los catálogos -------------------------------------------------
CATALOGOS = [
    Path(
        r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\CATALOGO_SAYCO.xlsx"
    ),
    Path(
        r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\CATALOGO_SAYCE.xlsx"
    ),
    Path(
        r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\OBRAS_SAYCE_ACTUALIZACIÓN_ENERO_MARZO_2025.xlsx"
    ),
    Path(
        r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\CATALOGO_SACVEN_DICIEMBRE.xlsx"
    ),
]

# --- columnas obligatorias --------------------------------------------------
COL_SGS = "Código SGS"
COL_PCT = "Porcentaje Reclamado de Autor"
COL_TIT = "Título"


def revisar_catalogo(path: Path):
    print(f"\n▶ Revisando {path.name} …")

    # 1) leer
    df = pd.read_excel(path)

    # 2) rellenar SGS y Título para que las filas hijas hereden el valor
    df[COL_SGS] = df[COL_SGS].ffill()
    df[COL_TIT] = df[COL_TIT].ffill()

    # 3) convertir porcentaje a float (coerce ignora celdas vacías)
    df[COL_PCT] = pd.to_numeric(df[COL_PCT], errors="coerce")

    # 4) agrupar y sumar
    suma_pct = (
        df.groupby(COL_SGS)[COL_PCT]
        .sum(min_count=1)  # NaN si todos vacíos
        .reset_index(name="Suma_%")
    )

    # 5) unir título y filtrar >100
    titulos = df[[COL_SGS, COL_TIT]].drop_duplicates(subset=[COL_SGS])
    resumen = suma_pct.merge(titulos, on=COL_SGS)[[COL_SGS, COL_TIT, "Suma_%"]]
    sobre_100 = resumen[resumen["Suma_%"] > 100.0]

    if sobre_100.empty:
        print("   ▸ Sin incidencias (>100 %).")
        return

    # 6) Detalle de filas que suman el exceso
    detalles = df[df[COL_SGS].isin(sobre_100[COL_SGS])].loc[
        :, [COL_SGS, "Nombre Autor", COL_PCT]
    ]

    # 7) exportar
    out = path.with_name(f"{path.stem}_sobre100.xlsx")
    with pd.ExcelWriter(out) as writer:
        sobre_100.to_excel(writer, sheet_name="Resumen", index=False)
        detalles.to_excel(writer, sheet_name="Detalle_filas", index=False)

    print(f"   ▸ {len(sobre_100)} obras >100 %. Archivo generado: {out.name}")


if __name__ == "__main__":
    for cat in CATALOGOS:
        if cat.exists():
            revisar_catalogo(cat)
        else:
            print(f"⚠️  No se encontró {cat}")
