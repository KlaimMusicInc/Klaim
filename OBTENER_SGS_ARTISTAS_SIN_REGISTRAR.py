"""
Exporta a Excel las obras del cliente 2 que no tienen código_ADREV.
Además genera un segundo Excel excluyendo también las obras que ya poseen ISRC.

Requisitos:
    pip install mysql-connector-python pandas openpyxl
"""

from pathlib import Path

import mysql.connector
import pandas as pd

# ─────────────── Configuración de conexión ─────────────── #
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",
    "database": "base_datos_klaim_dev",  # nombre de la BD restaurada desde el dump
    "charset": "utf8mb4",
    "use_unicode": True,
    "autocommit": True,
}

CLIENT_ID = 2  # id_cliente solicitado

# ─────────────── Plantilla de consulta ─────────────── #
BASE_SQL = f"""
SELECT
    o.titulo,
    o.codigo_sgs,
    COALESCE(        -- Agrupo artistas únicos separados por |
        GROUP_CONCAT(DISTINCT au.nombre_artista
                     ORDER BY au.nombre_artista
                     SEPARATOR '|'),
        '') AS artistas
FROM obras o
JOIN catalogos c                 ON c.id_catalogo      = o.catalogo_id
LEFT JOIN subidas_plataforma sp  ON sp.obra_id         = o.cod_klaim
LEFT JOIN artistas               ar ON ar.obra_id      = o.cod_klaim
LEFT JOIN artistas_unicos        au ON au.id_artista_unico = ar.id_artista_unico
WHERE
      c.id_cliente = %s
  AND (sp.codigo_ADREV IS NULL OR sp.codigo_ADREV = '')
{ '{extra_condition}' }                        -- se sustituirá dinámicamente
GROUP BY
    o.cod_klaim, o.titulo, o.codigo_sgs
ORDER BY
    o.titulo;
"""


# ─────────────── Funciones auxiliares ─────────────── #
def obtener_df(conn, extra_condition: str = "") -> pd.DataFrame:
    """
    Ejecuta la consulta con la condición adicional indicada y la devuelve como DataFrame.
    """
    sql = BASE_SQL.format(extra_condition=extra_condition)
    return pd.read_sql(sql, conn, params=(CLIENT_ID,))


def exportar_a_excel(df: pd.DataFrame, nombre_archivo: str) -> None:
    """
    Guarda el DataFrame en un archivo Excel en la carpeta actual.
    """
    df.to_excel(Path(nombre_archivo), index=False)
    print(f"▶ Exportado {len(df)} registros a «{nombre_archivo}»")


# ─────────────── Ejecución principal ─────────────── #
def main() -> None:
    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        # 1) Obras sin código_ADREV
        df_sin_adrev = obtener_df(conn)
        exportar_a_excel(df_sin_adrev, "obras_cliente2_sin_adrev.xlsx")

        # 2) Obras sin código_ADREV y SIN ISRC
        condicion_isrc = """
  AND NOT EXISTS (
        SELECT 1
        FROM codigos_isrc ci
        WHERE ci.obra_id = o.cod_klaim
          AND ci.codigo_isrc IS NOT NULL
          AND ci.codigo_isrc <> ''
  )
"""
        df_sin_adrev_sin_isrc = obtener_df(conn, condicion_isrc)
        exportar_a_excel(
            df_sin_adrev_sin_isrc, "obras_cliente2_sin_adrev_sin_isrc.xlsx"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
