#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Depura duplicados en obrasautores (mismo nombre de autor) cuando la suma de
porcentajes > 100 %.
Genera un reporte Excel con la marca "permanece" / "para eliminar".
"""

import datetime as dt
import logging
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from unidecode import unidecode

# ──────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────
DB_URL = os.getenv(
    "KLAIM_DB_URL",
    "mysql+mysqlconnector://ADMINISTRADOR:97072201144Ss.@localhost/base_datos_klaim",
)
BACKUP_DIR = "backups"
REPORT_FILE = f"duplicados_autor_obras_{dt.datetime.now():%Y%m%d_%H%M}.xlsx"
LOG_FILE = f"depuracion_autor_obras_{dt.datetime.now():%Y%m%d_%H%M}.log"

TABLA_RELACION = "obrasautores"
ID_RELACION = "id"
OBRA_FK = "obra_id"
AUTOR_FK = "autor_id"
PORC_COL = "porcentaje_autor"

# ──────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logging.getLogger().addHandler(console)


# ──────────────────────────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────────────────────────
def normalizar(nombre: str) -> str:
    """Quita tildes, pasa a minúsculas y colapsa espacios."""
    nombre = unidecode(nombre or "")
    return re.sub(r"\s+", " ", nombre).strip().lower()


def backup_tablas(tables: list[str]) -> None:
    """Ejecuta mysqldump. Permite continuar sin backup si no se encuentra."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dump_path = (
        Path(os.environ["MYSQL_BIN"]) / "mysqldump.exe"
        if "MYSQL_BIN" in os.environ
        else None
    )

    if not dump_path or not dump_path.exists():
        dump_path = shutil.which("mysqldump.exe") or shutil.which("mysqldump")

    if not dump_path:
        if (
            input("⚠️  No se encontró mysqldump. Continuar sin backup? (s/N): ").lower()
            != "s"
        ):
            sys.exit("Abortado.")
        logging.warning("Se procede SIN backup.")
        return

    salida = Path(BACKUP_DIR) / f"klaim_backup_{dt.datetime.now():%Y%m%d_%H%M}.sql"
    usuario = DB_URL.split("//")[1].split(":")[0]
    contrasena = DB_URL.split(":")[2].split("@")[0]
    base = DB_URL.split("/")[-1]

    cmd = [
        dump_path,
        f"--user={usuario}",
        f"--password={contrasena}",
        "--host=localhost",
        base,
        *tables,
    ]

    logging.info("Generando backup en: %s", salida)
    with open(salida, "w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        logging.error("mysqldump error: %s", proc.stderr.strip())
        sys.exit("Backup fallido; abortando.")
    logging.info("Backup completo.")


# ──────────────────────────────────────────────────────────────────
# CONEXIÓN
# ──────────────────────────────────────────────────────────────────
engine = create_engine(DB_URL, future=True)

# ──────────────────────────────────────────────────────────────────
# 1) OBRAS CON TOTAL > 100 %
# ──────────────────────────────────────────────────────────────────
query_conflictivas = text(
    f"""
SELECT
    o.cod_klaim          AS obra_id,
    o.titulo,
    o.codigo_sgs,
    cl.nombre_cliente,
    SUM(oa.{PORC_COL})   AS total_porcentaje
FROM obras                AS o
JOIN catalogos            AS c   ON c.id_catalogo = o.catalogo_id
JOIN clientes             AS cl  ON cl.id_cliente = c.id_cliente
JOIN {TABLA_RELACION}     AS oa  ON oa.{OBRA_FK} = o.cod_klaim
GROUP BY o.cod_klaim
HAVING total_porcentaje > 100
"""
)

with engine.connect() as conn:
    df_obras = pd.read_sql(query_conflictivas, conn)

if df_obras.empty:
    logging.info("No hay obras conflictivas.")
    sys.exit()

logging.info("Obras conflictivas encontradas: %d", len(df_obras))

# ──────────────────────────────────────────────────────────────────
# 2) DETECCIÓN DE DUPLICADOS
# ──────────────────────────────────────────────────────────────────
revision_rows: list[dict] = []  # incluye permanece / para eliminar
ids_eliminar: list[int] = []  # solo los que se eliminarán

with engine.connect() as conn:
    for _, obra in df_obras.iterrows():
        obra_id = obra["obra_id"]

        df_autores = pd.read_sql(
            text(
                f"""
            SELECT
                oa.{ID_RELACION},
                oa.{AUTOR_FK},
                au.nombre_autor,
                oa.{PORC_COL}
            FROM {TABLA_RELACION} oa
            JOIN autoresunicos au ON au.id_autor = oa.{AUTOR_FK}
            WHERE oa.{OBRA_FK} = :obra_id
        """
            ),
            conn,
            params={"obra_id": obra_id},
        )

        # Agrupar por nombre normalizado
        grupos = defaultdict(list)
        for _, fila in df_autores.iterrows():
            grupos[normalizar(fila["nombre_autor"])].append(fila)

        for filas in grupos.values():
            if len(filas) <= 1:
                # Solo una fila → no duplicada pero sigue en conflicto (>100 %)
                fila = filas[0]
                revision_rows.append(
                    {
                        **obra,
                        "rel_id": fila[ID_RELACION],
                        "autor_id": fila[AUTOR_FK],
                        "nombre_autor": fila["nombre_autor"],
                        "porcentaje": fila[PORC_COL],
                        "accion": "permanece",
                    }
                )
                continue

            # Elegir la fila que se queda (mayor porcentaje)
            fila_keep = max(filas, key=lambda f: f[PORC_COL])

            for fila in filas:
                accion = (
                    "permanece"
                    if fila[ID_RELACION] == fila_keep[ID_RELACION]
                    else "para eliminar"
                )
                revision_rows.append(
                    {
                        **obra,
                        "rel_id": fila[ID_RELACION],
                        "autor_id": fila[AUTOR_FK],
                        "nombre_autor": fila["nombre_autor"],
                        "porcentaje": fila[PORC_COL],
                        "accion": accion,
                    }
                )
                if accion == "para eliminar":
                    ids_eliminar.append(fila[ID_RELACION])

df_revision = pd.DataFrame(revision_rows)
if ids_eliminar:
    logging.info("Duplicados detectados: %d filas a eliminar.", len(ids_eliminar))
else:
    logging.info("No hay duplicados de nombre; nada que eliminar.")
    sys.exit()

# ──────────────────────────────────────────────────────────────────
# 3) BACKUP Y REPORTE
# ──────────────────────────────────────────────────────────────────
backup_tablas([TABLA_RELACION])

with pd.ExcelWriter(REPORT_FILE, engine="openpyxl") as writer:
    df_obras.to_excel(writer, sheet_name="Obras_conflictivas", index=False)
    df_revision.to_excel(writer, sheet_name="Revisar_autores", index=False)

logging.info("Reporte Excel generado: %s", REPORT_FILE)
print(f"\n✅  Reporte disponible en: {REPORT_FILE}")

# ──────────────────────────────────────────────────────────────────
# 4) CONFIRMACIÓN Y DELETE  (SECCIÓN CORREGIDA)
# ──────────────────────────────────────────────────────────────────
if (
    input("\n¿Eliminar ahora las filas marcadas como 'para eliminar'? (s/N): ").lower()
    != "s"
):
    logging.info("Operación cancelada por el usuario.")
    sys.exit("Cancelado.")

ids_eliminar = [int(x) for x in ids_eliminar]  # aseguramos lista de int
logging.info("Filas a eliminar: %d", len(ids_eliminar))

from sqlalchemy import \
    bindparam  # ← import local para evitar tocar la cabecera

delete_stmt = text(
    f"DELETE FROM {TABLA_RELACION} " f"WHERE {ID_RELACION} IN :ids"
).bindparams(bindparam("ids", expanding=True))

with engine.begin() as conn:  # transacción
    conn.execute(delete_stmt, {"ids": ids_eliminar})

logging.info("Filas duplicadas eliminadas correctamente.")
print("🎉  Duplicados eliminados. Consulta el log y el Excel generado.")
