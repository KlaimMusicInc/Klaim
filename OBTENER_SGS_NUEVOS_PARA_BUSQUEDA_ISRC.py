# -*- coding: utf-8 -*-
"""
Clasifica códigos SGS de un nuevo catálogo en: registrar, liberar, continuar.
NO modifica la base de datos: solo lee y exporta Excel.
"""
from tkinter import Tk, filedialog

import pandas as pd
from sqlalchemy import create_engine, text


# -----------------------------------
# 1. Conexión a MySQL (solo lectura)
# -----------------------------------
def create_connection():
    url = (
        "mysql+mysqlconnector://ADMINISTRADOR:97072201144Ss."
        "@localhost/base_datos_klaim"
    )
    engine = create_engine(url)
    return engine.connect()


# -----------------------------------
# 2. SGS existentes del cliente
# -----------------------------------
def obtener_sgs_base(connection, id_cliente):
    query = text(
        """
        SELECT o.codigo_sgs
          FROM Obras o
          JOIN Catalogos c ON o.catalogo_id = c.id_catalogo
         WHERE c.id_cliente = :id_cliente
    """
    )
    rows = connection.execute(query, {"id_cliente": id_cliente}).fetchall()
    return {int(r[0]) for r in rows}  # set de enteros


# -----------------------------------
# 3. Leer Excel y extraer SGS
# -----------------------------------
def seleccionar_excel():
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Seleccione el catálogo Excel")
    if not file_path:
        raise ValueError("No se seleccionó archivo.")
    return pd.read_excel(file_path)


def extraer_sgs_excel(df):
    # Acepta columna 'Código SGS', 'SGS' o similar
    posibles = [c for c in df.columns if "sgs" in c.lower()]
    if not posibles:
        raise ValueError("No se encontró columna SGS en el Excel.")
    col = posibles[0]
    serie = (
        df[col]
        .ffill()  # heredar SGS a filas hijas
        .astype("Int64")  # pandas entero que soporta NaN
        .dropna()
        .astype(int)
    )
    return set(serie.unique())


# -----------------------------------
# 4. Clasificación
# -----------------------------------
def clasificar(sgs_excel, sgs_base):
    registrar = sgs_excel - sgs_base
    liberar = sgs_base - sgs_excel
    continuan = sgs_excel & sgs_base
    return registrar, liberar, continuan


# -----------------------------------
# 5. Exportar a un solo Excel (3 hojas)
# -----------------------------------
def exportar_excel(registrar, liberar, continuan, salida="sgs_clasificados.xlsx"):
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        pd.DataFrame({"codigo_sgs": sorted(registrar)}).to_excel(
            writer, sheet_name="registrar", index=False
        )
        pd.DataFrame({"codigo_sgs": sorted(liberar)}).to_excel(
            writer, sheet_name="liberar", index=False
        )
        pd.DataFrame({"codigo_sgs": sorted(continuan)}).to_excel(
            writer, sheet_name="continuan", index=False
        )
    print(f"✅ Archivo generado: {salida}")


# -----------------------------------
# MAIN
# -----------------------------------
if __name__ == "__main__":
    # 1) Conectar
    conn = create_connection()

    try:
        # 2) Pedir id_cliente
        id_cliente = input("Ingrese el ID de cliente: ").strip()
        if not id_cliente.isdigit():
            raise ValueError("El ID de cliente debe ser numérico.")

        sgs_en_bd = obtener_sgs_base(conn, id_cliente)
        print(f"SGS en base para cliente {id_cliente}: {len(sgs_en_bd)}")

        # 3) Elegir Excel y extraer SGS
        df_excel = seleccionar_excel()
        sgs_excel = extraer_sgs_excel(df_excel)
        print(f"SGS en catálogo nuevo: {len(sgs_excel)}")

        # 4) Clasificar
        registrar, liberar, continuan = clasificar(sgs_excel, sgs_en_bd)
        print(
            f"Registrar: {len(registrar)} | "
            f"Liberar: {len(liberar)} | "
            f"Continúan: {len(continuan)}"
        )

        # 5) Exportar
        exportar_excel(registrar, liberar, continuan)

    finally:
        conn.close()
