import pandas as pd
import mysql.connector
from mysql.connector import Error

EXCEL_IN   = "work_report_2025-06-09-08-36-52.xlsx"
EXCEL_OUT  = "codigos_mlc_no_encontrados.xlsx"

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
            host     = "localhost",
            database = "base_datos_klaim",
            user     = "root",
            password = "97072201144Ss."
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
