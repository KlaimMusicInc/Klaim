#!/usr/bin/env python3
"""
Inserta o actualiza códigos ADREV en la tabla subidas_plataforma
a partir del Excel INSERTAR_CODIGO_aDREV_COD_KLAIM.xlsx.

• Un COMMIT por cada fila (transacción segura).
• Detecta cod_klaim duplicados en el Excel y detiene la ejecución.
• Si el registro existe → UPDATE código_ADREV.
• Si no existe → INSERT con los valores por defecto pactados.
"""

import sys
from datetime import date
from pathlib import Path

import mysql.connector
import pandas as pd
from mysql.connector import errorcode
from tqdm import tqdm  # barra de progreso opcional

# ─────────────── Parámetros ─────────────── #
EXCEL_FILE = Path("INSERTAR_CODIGO_aDREV_COD_KLAIM.xlsx")
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",
    "database": "base_datos_klaim_dev",
    "port": 3306,
    "autocommit": False,  # control manual de commits
}
# ─────────────────────────────────────────── #


def cargar_excel(path: Path) -> pd.DataFrame:
    """Carga el Excel y valida duplicados en cod_klaim."""
    df = pd.read_excel(path, dtype={"cod_klaim": "int64", "custom_id": "string"})
    duplicados = df[df.duplicated(subset="cod_klaim", keep=False)]
    if not duplicados.empty:
        raise ValueError(
            f"ERROR: se encontraron cod_klaim duplicados en el Excel:\n{duplicados}"
        )
    return df


def procesar_fila(cursor, cod_klaim: int, custom_id: str, hoy: date):
    """Actualiza o inserta una fila según exista o no en la BD."""
    # 1. ¿Ya existe el cod_klaim en subidas_plataforma?
    cursor.execute(
        "SELECT id_subida FROM subidas_plataforma WHERE obra_id = %s",
        (cod_klaim,),
    )
    existe = cursor.fetchone()

    if existe:
        # UPDATE
        cursor.execute(
            """
            UPDATE subidas_plataforma
               SET codigo_ADREV = %s
             WHERE obra_id      = %s
            """,
            (custom_id, cod_klaim),
        )
    else:
        # INSERT con valores por defecto pactados
        cursor.execute(
            """
            INSERT INTO subidas_plataforma
                (obra_id, codigo_ADREV, estado_ADREV, fecha_subida, matching_tool)
            VALUES
                (%s,      %s,          'OK',        %s,            0)
            """,
            (cod_klaim, custom_id, hoy),
        )


def main() -> None:
    try:
        df = cargar_excel(EXCEL_FILE)
        hoy = date.today()

        cnx = mysql.connector.connect(**MYSQL_CONFIG)
        cur = cnx.cursor(prepared=True)

        for cod_klaim, custom_id in tqdm(
            df[["cod_klaim", "custom_id"]].itertuples(index=False),
            total=len(df),
            desc="Procesando filas",
        ):
            procesar_fila(cur, int(cod_klaim), str(custom_id), hoy)
            cnx.commit()  # COMMIT por fila

        print("Proceso completado sin errores ✔")

    except (KeyboardInterrupt, SystemExit):
        print("\nEjecución interrumpida.")
        sys.exit(1)

    except Exception as e:
        print(f"\n{type(e).__name__}: {e}")
        sys.exit(1)

    finally:
        try:
            cur.close()
            cnx.close()
        except Exception:
            pass  # conexión no creada o ya cerrada


if __name__ == "__main__":
    main()
