# -------------------------------------------------------------------------------------------
# AUTOR: [Tu Nombre]
# FECHA: [Fecha de uso]
#
# DESCRIPCIÓN GENERAL:
# -------------------------------------------------------------------------------------------
# Este script en Python sirve para identificar los códigos MLC (de la columna "MLC SONG CODE")
# presentes en un archivo Excel que aún no han sido cargados a la base de datos `subidas_plataforma`.
#
# La idea principal es detectar qué canciones todavía no tienen su código MLC registrado en la base
# de datos, para poder hacer una carga posterior o analizarlas manualmente.
#
# FUNCIONALIDAD PRINCIPAL:
# -------------------------------------------------------------------------------------------
# 1. Carga el archivo Excel (por defecto: "work_report_2025-06-09-08-36-52.xlsx").
#    Este archivo debe contener al menos las columnas "MLC SONG CODE" y "ISWC".
#
# 2. Se conecta a la base de datos MySQL llamada "base_datos_klaim".
#
# 3. Consulta todos los códigos ya existentes en la columna `codigo_MLC` de la tabla
#    `subidas_plataforma`, para tener una lista de los que ya están cargados.
#
# 4. Compara los códigos del Excel con los que están en la base:
#    ▸ Si el código MLC ya está en la base, lo ignora.
#    ▸ Si **no** está en la base, lo guarda en un nuevo DataFrame llamado `df_no`.
#
# 5. Luego, a cada fila del nuevo DataFrame `df_no`, le intenta asignar su correspondiente
#    `cod_klaim` (ID interno de la obra en la base), buscando en la tabla `obras` mediante
#    el código ISWC.
#    ▸ Para esto, primero carga un diccionario completo de {ISWC → cod_klaim} desde la base.
#    ▸ Después lo aplica a cada fila mediante una función auxiliar.
#
# 6. Finalmente, exporta el resultado con las filas que aún no están cargadas (las "no encontradas")
#    a un nuevo archivo Excel llamado "codigos_mlc_no_encontrados.xlsx".
#
# Este archivo de salida contiene:
#   ▸ El título de la canción,
#   ▸ Su código ISWC,
#   ▸ Su código MLC propuesto,
#   ▸ Y el cod_klaim si se logró identificar a partir del ISWC.
#
# USOS TÍPICOS:
# -------------------------------------------------------------------------------------------
# ✔️ Verificar qué registros del catálogo aún no han sido cargados a `subidas_plataforma`.
# ✔️ Hacer seguimiento a las canciones pendientes de registrar en plataformas.
# ✔️ Identificar errores o faltantes en la carga automatizada.
# ✔️ Apoyar procesos de control de calidad o auditoría musical.
# ✔️ Generar un listado para carga manual o revisión con el cliente.
#
# REQUISITOS:
# -------------------------------------------------------------------------------------------
# ▸ Tener el archivo Excel con la estructura adecuada (MLC SONG CODE y ISWC).
# ▸ Tener acceso a la base de datos `base_datos_klaim`.
# ▸ La tabla `subidas_plataforma` debe contener la columna `codigo_MLC`.
# ▸ La tabla `obras` debe tener `codigo_iswc` y `cod_klaim`.
#
# ARCHIVOS INVOLUCRADOS:
# -------------------------------------------------------------------------------------------
# ✅ Entrada:  work_report_2025-06-09-08-36-52.xlsx
# ✅ Salida:   codigos_mlc_no_encontrados.xlsx
#
# -------------------------------------------------------------------------------------------


import mysql.connector
import pandas as pd
from mysql.connector import Error

EXCEL_IN = "catalogo_sayce_mlc_julio.xlsx"
EXCEL_OUT = "codigos_mlc_no_encontrados_sayce.xlsx"


def obtener_diccionario_iswc(connection):
    """
    Devuelve un dict {codigo_iswc:str -> cod_klaim:int}
    Leer todo de una sola vez evita el bucle de consultas.
    """
    sql = """SELECT codigo_iswc, cod_klaim
             FROM obras
             WHERE codigo_iswc IS NOT NULL"""
    with connection.cursor(buffered=True) as cur:
        cur.execute(sql)
        return {codigo.strip(): klaim for codigo, klaim in cur}


def main():
    # ---------- 1. Cargar Excel ----------
    df = pd.read_excel(EXCEL_IN)
    df["MLC SONG CODE"] = df["MLC SONG CODE"].astype(str).str.strip()

    # ---------- 2. Conexión ----------
    try:
        conn = mysql.connector.connect(
            host="localhost",
            database="base_datos_klaim_dev",
            user="root",
            password="97072201144Ss.",
        )

        # ---------- 3. Códigos MLC ya cargados ----------
        with conn.cursor(buffered=True) as cur:
            cur.execute("SELECT codigo_MLC FROM subidas_plataforma")
            codigos_mlc_db = {str(r[0]).strip() for r in cur if r[0]}

        # ---------- 4. Filtrar los no encontrados ----------
        df_no = df[~df["MLC SONG CODE"].isin(codigos_mlc_db)].copy()

        # ---------- 5. Mapear ISWC → cod_klaim ----------
        mapa_iswc = obtener_diccionario_iswc(conn)

        def mapear(iswc):
            iswc = str(iswc).strip()
            return mapa_iswc.get(iswc) if iswc and iswc.lower() != "nan" else None

        df_no["cod_klaim"] = df_no["ISWC"].apply(mapear)

        # ---------- 6. Exportar ----------
        df_no.to_excel(EXCEL_OUT, index=False)
        print(f"✅ Archivo generado: {EXCEL_OUT}")

    except Error as err:
        print("❌ MySQL error:", err)

    finally:
        if "conn" in locals() and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()
