#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reconciliar catálogos SAYCO · SAYCE · SACVEN con la BD (base_datos_klaim_dev)

❶ Diagnóstico: compara obra-por-obra contra los Excels oficiales y genera
   un .xlsx con el plan de acción + posible pérdida de ISRC.
❷ Corrección: aplica INSERT / UPDATE / DELETE en Obras, ObrasAutores,
   artistas y codigos_isrc (solo cuando mueve artistas).

Uso:
    python reconciliar_clientes.py --cliente SAYCE          # solo diagnóstico
    python reconciliar_clientes.py --cliente ALL --apply    # diagnóstico + aplicar

Autor: ChatGPT (simulación de experto Python)
"""

import argparse
import datetime as dt
import os
import sys
from pathlib import Path
from textwrap import dedent

import pandas as pd
from sqlalchemy import create_engine, text
from tabulate import tabulate

# === CONFIGURACIÓN ==========================================================

ENGINE = create_engine(
    "mysql+mysqlconnector://ADMINISTRADOR:97072201144Ss.@localhost/base_datos_klaim",
    pool_recycle=3600,
)

# Rutas absolutas de los catálogos originales
EXCELS = {
    "SAYCO": [
        r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\CATALOGO_SAYCO.xlsx"
    ],
    "SAYCE": [
        r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\CATALOGO_SAYCE.xlsx",
        # r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\OBRAS_SAYCE_ACTUALIZACIÓN_ENERO_MARZO_2025.xlsx",
    ],
    "SACVEN": [
        r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\CATALOGO_SACVEN_DICIEMBRE.xlsx"
    ],
}

# Mapas auxiliares -----------------------------------------------------------
SQL_CLIENTE_ID = text(
    "SELECT id_cliente FROM clientes WHERE UPPER(nombre_cliente)=UPPER(:nom)"
)
SQL_CATALOGO_ACTIVO = text(
    "SELECT id_catalogo FROM catalogos WHERE id_cliente=:cid AND estado='Activo'"
)

SQL_OBRAS_CLIENTE = text(
    """
SELECT  o.cod_klaim, o.codigo_sgs, o.titulo
FROM    obras o
JOIN    catalogos c ON c.id_catalogo = o.catalogo_id
WHERE   c.id_cliente = :cid
"""
)

SQL_AUTORES_OBRA = text(
    "SELECT a.nombre_autor, oa.porcentaje_autor "
    "FROM obrasautores oa "
    "JOIN autoresunicos a ON a.id_autor = oa.autor_id "
    "WHERE oa.obra_id = :ok"
)

SQL_ARTISTAS_OBRA = text(
    "SELECT au.nombre_artista "
    "FROM artistas ar "
    "JOIN artistas_unicos au ON au.id_artista_unico = ar.id_artista_unico "
    "WHERE ar.obra_id = :ok"
)

SQL_SUM_PCT = text("SELECT SUM(porcentaje_autor) FROM obrasautores WHERE obra_id=:ok")

SQL_ISRC_BY_OBRA_ARTISTA = text(
    "SELECT * FROM codigos_isrc WHERE obra_id=:ok AND id_artista_unico=:aid"
)
SQL_UPDATE_ISRC_OBRA = text(
    "UPDATE codigos_isrc SET obra_id=:new_ok WHERE id_isrc=:iid"
)

# Inserciones / borrados simplificados (usamos exec_many)
INS_OBRA = text(
    "INSERT INTO obras (titulo,codigo_sgs,codigo_iswc,catalogo_id) "
    "VALUES (:tit,:sgs,NULL,:cid)"
)
INS_AUTORUNICO = text(
    "INSERT IGNORE INTO autoresunicos (nombre_autor,codigo_ipi,tipo_autor) "
    "VALUES (:nom,:ipi,:tipo)"
)
SEL_AUTORUNICO_ID = text(
    "SELECT id_autor FROM autoresunicos WHERE nombre_autor=:nom AND "
    "IFNULL(codigo_ipi,'')=IFNULL(:ipi,'') AND IFNULL(tipo_autor,'')=IFNULL(:tipo,'') "
)
INS_OBRASAUTORES = text(
    "INSERT INTO obrasautores (obra_id,autor_id,porcentaje_autor) "
    "VALUES (:ok,:au,:pct)"
)
DEL_OBRASAUTOR = text("DELETE FROM obrasautores WHERE obra_id=:ok AND autor_id=:au")
UPD_OBRASAUTOR_PCT = text(
    "UPDATE obrasautores SET porcentaje_autor=:pct "
    "WHERE obra_id=:ok AND autor_id=:au"
)
INS_ARTISTA_UNICO = text(
    "INSERT IGNORE INTO artistas_unicos (nombre_artista) VALUES (:nom)"
)
SEL_ARTISTA_UNICO_ID = text(
    "SELECT id_artista_unico FROM artistas_unicos WHERE nombre_artista=:nom"
)
INS_ARTISTA = text(
    "INSERT INTO artistas (nombre_artista,obra_id,id_artista_unico) "
    "VALUES (:nom,:ok,:au)"
)
DEL_ARTISTA = text("DELETE FROM artistas WHERE obra_id=:ok AND id_artista_unico=:au")


# === FUNCIONES DE APOYO =====================================================
def resumen_autor(nom: str, pct: float | None):
    """Devuelve 'Nombre (xx%)' o solo nombre si pct es None."""
    return f"{nom} ({pct:.2f}%)" if pct is not None else nom


def pct_list_str(pcts: list[float]) -> str:
    """Convierte [33.33, 66.67] -> '33.33|66.67' con 2 decimales."""
    return "|".join(f"{p:.2f}" for p in pcts)


def load_excels(cliente: str) -> pd.DataFrame:
    """
    Une todos los catálogos de un cliente, rellena SGS/Título
    y elimina filas duplicadas (mismo SGS, Título, Autor, %, Artistas…).
    """
    # 1) Leer y concatenar
    frames = [pd.read_excel(fp) for fp in EXCELS[cliente]]
    df = pd.concat(frames, ignore_index=True)

    # 2) Propagar SGS y Título hacia abajo
    df["Código SGS"] = df["Código SGS"].ffill()
    df["Título"] = df["Título"].ffill()

    # 3) Normalizaciones básicas
    df["Código SGS"] = df["Código SGS"].astype(str).str.strip()
    df["Nombre Autor"] = df["Nombre Autor"].astype(str).str.strip()

    # 4) Eliminar duplicados exactos en las columnas clave
    COLS_CLAVE = [
        "Código SGS",
        "Título",
        "Nombre Autor",
        "Número IP Autor",
        "Tipo de Autor",
        "Porcentaje Reclamado de Autor",
        "Artistas",
    ]
    # si alguna columna no existe en algún Excel, la añadimos vacía para evitar KeyError
    for col in COLS_CLAVE:
        if col not in df.columns:
            df[col] = pd.NA

    antes = len(df)
    df = df.drop_duplicates(subset=COLS_CLAVE, keep="first").reset_index(drop=True)
    depurados = antes - len(df)
    if depurados:
        print(f"   · {cliente}: {depurados} filas duplicadas eliminadas")

    return df


def build_excel_dict(df: pd.DataFrame):
    """Devuelve dict[sgs] -> info dict sin artistas vacíos."""
    info = {}
    for sgs, grp in df.groupby("Código SGS"):
        rec = {
            "titulo": grp.iloc[0]["Título"],
            "autores": [],
            "porcentajes": [],
            "artistas": [],
        }
        for _, row in grp.iterrows():
            # ---------- autores ----------
            if pd.notna(row["Nombre Autor"]) and pd.notna(
                row["Porcentaje Reclamado de Autor"]
            ):
                rec["autores"].append(
                    (
                        row["Nombre Autor"].strip(),
                        row.get("Número IP Autor", None),
                        row.get("Tipo de Autor", None),
                    )
                )
                rec["porcentajes"].append(float(row["Porcentaje Reclamado de Autor"]))

            # ---------- artistas ----------
            if pd.notna(row["Artistas"]):
                artistas_raw = [a.strip() for a in str(row["Artistas"]).split(";")]
                rec["artistas"].extend(artistas_raw)

        # Limpieza final: quitamos vacíos, espacios y textos 'nan'
        rec["artistas"] = list(
            {a for a in rec["artistas"] if a and a.strip() and a.lower() != "nan"}
        )

        info[sgs] = rec
    return info


def build_db_dict(conn, cid: int):
    """Recupera obras + autores + artistas para un cliente."""
    obras = conn.execute(SQL_OBRAS_CLIENTE, {"cid": cid}).fetchall()
    d = {}
    for ok, sgs, tit in obras:
        autores = conn.execute(SQL_AUTORES_OBRA, {"ok": ok}).fetchall()
        artistas = conn.execute(SQL_ARTISTAS_OBRA, {"ok": ok}).fetchall()
        d[sgs] = {
            "cod_klaim": ok,
            "titulo": tit,
            "autores": [(a, None, None) for a, _ in autores],
            "porcentajes": [float(p) for _, p in autores],
            "artistas": [a for (a,) in artistas],
        }
    return d


def diff_lists(ref, cur):
    """Devuelve (faltan, sobran, comunes) según valor string."""
    faltan = [x for x in ref if x not in cur]
    sobran = [x for x in cur if x not in ref]
    comunes = [x for x in ref if x in cur]
    return faltan, sobran, comunes


# === PROCESO POR CLIENTE ====================================================


def reconcile_cliente(conn, cliente: str, apply: bool):
    cid_row = conn.execute(SQL_CLIENTE_ID, {"nom": cliente}).fetchone()
    if not cid_row:
        print(f"⚠️  Cliente {cliente} no existe en BD.")
        return
    cid = cid_row[0]

    catalogo_id = conn.execute(SQL_CATALOGO_ACTIVO, {"cid": cid}).scalar()
    if not catalogo_id:
        print(f"⚠️  Cliente {cliente} no tiene catálogo activo.")
        return

    df_excel = load_excels(cliente)
    excel_info = build_excel_dict(df_excel)
    db_info = build_db_dict(conn, cid)

    plan_rows = []
    isrc_rows = []

    # --- 1. Crear obras que faltan -----------------------------------------
    for sgs, rec in excel_info.items():
        if sgs not in db_info:
            plan_rows.append(
                {
                    "SGS": sgs,
                    "Accion": "CREAR_OBRA",
                    "Detalle": f"Obra nueva con {len(rec['autores'])} autores y {len(rec['artistas'])} artistas",
                }
            )

    # --- 2. Reconciliar las existentes ------------------------------------
    for sgs, db in db_info.items():
        if sgs not in excel_info:
            continue  # obras extra → se ignoran

        ex = excel_info[sgs]

        # ---------- autores ----------
        ex_aut_nombres = [a[0] for a in ex["autores"]]
        db_aut_nombres = [a[0] for a in db["autores"]]

        faltan_aut, sobran_aut, comunes_aut = diff_lists(ex_aut_nombres, db_aut_nombres)

        # INSERT_AUTOR
        for nom in faltan_aut:
            idx = ex_aut_nombres.index(nom)
            plan_rows.append(
                {
                    "SGS": sgs,
                    "Accion": "INSERT_AUTOR",
                    "Detalle": nom,
                    "Valor_BD": "—",
                    "Valor_Excel": resumen_autor(nom, ex["porcentajes"][idx]),
                }
            )

        # DELETE_AUTOR
        for nom in sobran_aut:
            idx = db_aut_nombres.index(nom)
            plan_rows.append(
                {
                    "SGS": sgs,
                    "Accion": "DELETE_AUTOR",
                    "Detalle": nom,
                    "Valor_BD": resumen_autor(nom, db["porcentajes"][idx]),
                    "Valor_Excel": "—",
                }
            )

        # UPDATE_PCT (si la lista coincide pero % difieren, o longitud distinta)
        if len(ex["porcentajes"]) != len(db["porcentajes"]) or any(
            abs(p_db - p_ex) > 0.01
            for p_db, p_ex in zip(db["porcentajes"], ex["porcentajes"])
        ):
            plan_rows.append(
                {
                    "SGS": sgs,
                    "Accion": "UPDATE_PCT",
                    "Detalle": "Ajustar porcentajes según Excel",
                    "Valor_BD": pct_list_str(db["porcentajes"]),
                    "Valor_Excel": pct_list_str(ex["porcentajes"]),
                }
            )

        # ---------- artistas ----------
        faltan_art, sobran_art, _ = diff_lists(ex["artistas"], db["artistas"])

        for art in faltan_art:
            plan_rows.append(
                {
                    "SGS": sgs,
                    "Accion": "INSERT_ARTISTA",
                    "Detalle": art,
                    "Valor_BD": "—",
                    "Valor_Excel": art,
                }
            )

        for art in sobran_art:
            plan_rows.append(
                {
                    "SGS": sgs,
                    "Accion": "DELETE_ARTISTA",
                    "Detalle": art,
                    "Valor_BD": art,
                    "Valor_Excel": "—",
                }
            )

    # ---------- Imprimir diagnóstico --------------------------------------
    diag_df = pd.DataFrame(
        plan_rows, columns=["SGS", "Accion", "Detalle", "Valor_BD", "Valor_Excel"]
    )

    fname_diag = f"diag_{cliente}_{dt.date.today():%Y%m%d}.xlsx"
    diag_df.to_excel(fname_diag, index=False)
    print(
        f"\n▶ Diagnóstico {cliente}: {len(plan_rows)} acciones. "
        f"Archivo: {fname_diag}"
    )
    if not apply:
        return

    # ---------- Confirmación en consola -----------------------------------
    print(tabulate(diag_df.head(20), headers="keys", tablefmt="github"))
    ans = input(f"\nCONFIRMAR y aplicar los cambios para {cliente}? (S/N): ").strip()
    if ans.lower() != "s":
        print("⏩  Saltado.")
        return

    # ---------- Aplicar ----------------------------------------------------
    before = conn.execute(text("SELECT ROW_COUNT()")).scalar()
    savept = conn.begin_nested()  # Savepoint por cliente
    try:
        # 2.1 Crear obras nuevas
        for row in plan_rows:
            if row["Accion"] == "CREAR_OBRA":
                sgs = row["SGS"]
                ex = excel_info[sgs]
                res = conn.execute(
                    INS_OBRA, {"tit": ex["titulo"], "sgs": sgs, "cid": catalogo_id}
                )
                new_ok = res.lastrowid

                # insertar autores
                for (nom, ipi, tipo), pct in zip(ex["autores"], ex["porcentajes"]):
                    conn.execute(INS_AUTORUNICO, {"nom": nom, "ipi": ipi, "tipo": tipo})
                    au_id = conn.execute(
                        SEL_AUTORUNICO_ID, {"nom": nom, "ipi": ipi, "tipo": tipo}
                    ).scalar()
                    conn.execute(
                        INS_OBRASAUTORES, {"ok": new_ok, "au": au_id, "pct": pct}
                    )

                # insertar artistas
                for art in ex["artistas"]:
                    conn.execute(INS_ARTISTA_UNICO, {"nom": art})
                    art_u = conn.execute(SEL_ARTISTA_UNICO_ID, {"nom": art}).scalar()
                    conn.execute(
                        INS_ARTISTA,
                        {"nom": art, "ok": new_ok, "au": art_u},
                    )

        # 2.2 Sincronizar existentes
        for row in plan_rows:
            sgs = row["SGS"]
            if sgs not in db_info:
                continue
            ok = db_info[sgs]["cod_klaim"]
            ex = excel_info[sgs]
            db = db_info[sgs]

            if row["Accion"] == "INSERT_AUTOR":
                nom = row["Detalle"]
                idx = [a[0] for a in ex["autores"]].index(nom)
                nom, ipi, tipo = ex["autores"][idx]
                pct = ex["porcentajes"][idx]

                conn.execute(INS_AUTORUNICO, {"nom": nom, "ipi": ipi, "tipo": tipo})
                au_id = conn.execute(
                    SEL_AUTORUNICO_ID, {"nom": nom, "ipi": ipi, "tipo": tipo}
                ).scalar()
                conn.execute(INS_OBRASAUTORES, {"ok": ok, "au": au_id, "pct": pct})

            elif row["Accion"] == "DELETE_AUTOR":
                nom = row["Detalle"]
                au_id = conn.execute(
                    SEL_AUTORUNICO_ID, {"nom": nom, "ipi": None, "tipo": None}
                ).scalar()
                if au_id:
                    conn.execute(DEL_OBRASAUTOR, {"ok": ok, "au": au_id})

            elif row["Accion"] == "UPDATE_PCT":
                # borrar todos y reinsertar según Excel
                conn.execute(
                    text("DELETE FROM obrasautores WHERE obra_id=:ok"), {"ok": ok}
                )
                for (nom, ipi, tipo), pct in zip(ex["autores"], ex["porcentajes"]):
                    conn.execute(INS_AUTORUNICO, {"nom": nom, "ipi": ipi, "tipo": tipo})
                    au_id = conn.execute(
                        SEL_AUTORUNICO_ID, {"nom": nom, "ipi": ipi, "tipo": tipo}
                    ).scalar()
                    conn.execute(INS_OBRASAUTORES, {"ok": ok, "au": au_id, "pct": pct})

            elif row["Accion"] == "INSERT_ARTISTA":
                art = row["Detalle"]
                conn.execute(INS_ARTISTA_UNICO, {"nom": art})
                art_u = conn.execute(SEL_ARTISTA_UNICO_ID, {"nom": art}).scalar()
                conn.execute(INS_ARTISTA, {"nom": art, "ok": ok, "au": art_u})

            elif row["Accion"] == "DELETE_ARTISTA":
                art = row["Detalle"]
                art_u = conn.execute(SEL_ARTISTA_UNICO_ID, {"nom": art}).scalar()
                if not art_u:
                    continue
                # mover ISRC antes de borrar relación
                isrcs = (
                    conn.execute(SQL_ISRC_BY_OBRA_ARTISTA, {"ok": ok, "aid": art_u})
                    .mappings()
                    .all()
                )
                if isrcs:
                    isrc_rows.extend(isrcs)
                    # Si existe otra obra con mismo SGS?  Buscar obra correcta
                    new_ok = ok  # por defecto; no sabemos dónde mover
                    conn.execute(
                        SQL_UPDATE_ISRC_OBRA,
                        {"new_ok": new_ok, "iid": isrcs[0]["id_isrc"]},
                    )
                conn.execute(DEL_ARTISTA, {"ok": ok, "au": art_u})

        # ---------- Guardar ISRC posibles perdidos -------------------------
        if isrc_rows:
            pd.DataFrame(isrc_rows).to_excel(
                f"isrc_afectados_{cliente}_{dt.date.today():%Y%m%d}.xlsx", index=False
            )
        after = conn.execute(text("SELECT ROW_COUNT()")).scalar()
        print(f"Filas afectadas en {cliente}: {after - before}")
        savept.commit()
        print(f"✅  Cambios aplicados para {cliente}")

    except Exception as e:
        savept.rollback()
        print(f"❌  Error en {cliente}: {e}")
        raise

    # Verificar obras >100 %
    pendientes = []
    for sgs, db in db_info.items():
        ok = db["cod_klaim"]
        total = conn.execute(SQL_SUM_PCT, {"ok": ok}).scalar() or 0
        if total > 100.0 + 1e-2:
            pendientes.append((sgs, total))
    if pendientes:
        with open(f"log_correccion_{cliente}_{dt.date.today():%Y%m%d}.txt", "w") as f:
            for sgs, tot in pendientes:
                f.write(f"{sgs}\t{tot}\n")
        print(
            f"⚠️  {len(pendientes)} obras de {cliente} siguen >100 % "
            "(ver log_correccion_*.txt)"
        )


# === MAIN ===================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Reconciliar catálogos oficiales con la BD"
    )
    parser.add_argument(
        "--cliente",
        choices=["SAYCO", "SAYCE", "SACVEN", "ALL"],
        required=True,
        help="Cliente a procesar",
    )
    parser.add_argument("--apply", action="store_true", help="Aplicar cambios")
    args = parser.parse_args()

    clientes = ["SAYCO", "SAYCE", "SACVEN"] if args.cliente == "ALL" else [args.cliente]

    with ENGINE.begin() as conn:
        for cli in clientes:
            reconcile_cliente(conn, cli, apply=args.apply)


if __name__ == "__main__":
    main()
