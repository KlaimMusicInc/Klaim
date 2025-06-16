from sqlalchemy import create_engine, text
import pandas as pd
from tkinter import Tk, filedialog          # ← añadido

# ════════════════ 1) CONEXIÓN ════════════════
def create_connection():
    """
    Devuelve un objeto connection de SQLAlchemy ya conectado a MySQL.
    """
    try:
        engine = create_engine(
            "mysql+mysqlconnector://ADMINISTRADOR:97072201144Ss.@localhost/base_datos_klaim",
            pool_pre_ping=True,         # evita conexiones muertas
        )
        conn = engine.connect()
        print("Conexión exitosa a la base de datos")
        return conn
    except Exception as e:
        print(f"Error en la conexión: {e}")
        return None


# ════════════════ 2) HELPERS ════════════════
def normalize_sgs(value):
    """
    Normaliza cualquier valor de SGS a una **cadena sin espacios**
    preservando ceros a la izquierda.  Regla:
      • Se quitan únicamente espacios al inicio/fin.
      • Si el valor llega como float terminado en '.0', se convierte a int
        para eliminar el punto decimal.
    """
    if pd.isna(value):
        return ""
    # 12345.0  →  12345
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = str(value).strip()
    if s.endswith(".0"):           # seguridad adicional
        s = s[:-2]
    return s


def get_obras_by_catalogo(connection, id_catalogo):
    """
    Devuelve un dict {codigo_sgs(str) → cod_klaim(int)}
    para todas las obras del catálogo indicado, con SGS normalizado.
    """
    query = text("""
        SELECT cod_klaim  AS obra_id,
               codigo_sgs AS codigo_sgs
        FROM   obras
        WHERE  catalogo_id = :id_catalogo
    """)
    rows = connection.execute(query, {"id_catalogo": id_catalogo}).fetchall()
    return {normalize_sgs(r.codigo_sgs): r.obra_id for r in rows}


def get_or_create_artista_unico(connection, nombre_artista):
    """
    Busca un artista único (case-insensitive).
    Si no existe lo crea y devuelve su id.
    """
    row = connection.execute(
        text("""SELECT id_artista_unico
                FROM   artistas_unicos
                WHERE  LOWER(nombre_artista) = LOWER(:name)
                LIMIT  1"""),
        {"name": nombre_artista},
    ).fetchone()

    if row:
        return row.id_artista_unico

    connection.execute(
        text("INSERT INTO artistas_unicos(nombre_artista) VALUES (:name)"),
        {"name": nombre_artista},
    )
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]


# ════════════════ 3) INSERCIÓN DE ISRC ════════════════
def insert_codigo_isrc(
    connection,
    codigo_isrc,
    obra_id,
    id_artista_unico,
    name_artista_alternativo,
    titulo_alternativo,
    rating,
):
    """
    Inserta un registro completo en codigos_isrc.
    """
    connection.execute(
        text(
            """
        INSERT INTO codigos_isrc (
            codigo_isrc,
            obra_id,
            id_artista_unico,
            name_artista_alternativo,
            titulo_alternativo,
            rating
        )
        VALUES (
            :codigo_isrc,
            :obra_id,
            :id_artista_unico,
            :name_artista_alternativo,
            :titulo_alternativo,
            :rating
        )
        """
        ),
        {
            "codigo_isrc": codigo_isrc,
            "obra_id": obra_id,
            "id_artista_unico": id_artista_unico,
            "name_artista_alternativo": name_artista_alternativo,
            "titulo_alternativo": titulo_alternativo,
            "rating": rating,
        },
    )


# ════════════════ 4) PROCESAR UNA FILA ════════════════
def process_row(row, obras_dict, connection):
    """
    Procesa una fila del DataFrame.
    Devuelve la fila original si el SGS no está en el catálogo.
    """
    codigo_sgs_raw  = row["CODIGO_SGS"]
    codigo_sgs      = normalize_sgs(codigo_sgs_raw)          # ← normalizado
    codigo_isrc     = str(row["ISRC"]).strip()

    # Campos de texto con valores por defecto
    nombre_artista  = row.get("Nombre_artista",  pd.NA)
    artista_real    = row.get("Artista_REAL",    pd.NA)
    cancion_real    = row.get("Cancion_REAL",    pd.NA)

    nombre_artista  = nombre_artista if pd.notna(nombre_artista) else "NO IDENTIFICADO"
    artista_real    = artista_real   if pd.notna(artista_real)   else "NO IDENTIFICADO"
    cancion_real    = cancion_real   if pd.notna(cancion_real)   else "NO IDENTIFICADO"

    # RATE
    rating = None
    rate_val = row.get("RATE", pd.NA)
    if pd.notna(rate_val) and str(rate_val).strip() != "":
        try:
            rating = float(rate_val)
        except ValueError:
            print(f"[SGS {codigo_sgs}] RATE «{rate_val}» inválido → ignorado.")

    # Obra en catálogo
    obra_id = obras_dict.get(codigo_sgs)
    if obra_id is None:
        return row  # fila quedará en no_encontrados

    # Crear/obtener artista único
    artista_unico_id = get_or_create_artista_unico(connection, nombre_artista)

    # Insertar
    insert_codigo_isrc(
        connection,
        codigo_isrc,
        obra_id,
        artista_unico_id,
        artista_real,
        cancion_real,
        rating,
    )
    return None


# ════════════════ 5) PROCESAR ARCHIVO COMPLETO ════════════════
def process_isrc_file(connection, id_catalogo, excel_path):
    obras_dict = get_obras_by_catalogo(connection, id_catalogo)

    df = pd.read_excel(excel_path, dtype=str)   # ← lee todo como STR para conservar ceros
    df = df.fillna("")                          # evita NaN

    total = len(df)
    no_encontrados = []

    for idx, row in df.iterrows():
        nf = process_row(row, obras_dict, connection)
        if nf is not None:
            no_encontrados.append(nf)

        if (idx + 1) % 10 == 0 or (idx + 1) == total:
            print(f"Procesando fila {idx + 1}/{total}…")

    if no_encontrados:
        pd.DataFrame(no_encontrados).to_excel("ISRC_no_encontrados.xlsx", index=False)
        print("Generado 'ISRC_no_encontrados.xlsx' con registros no encontrados.")

    connection.execute(text("COMMIT"))
    print("Códigos ISRC insertados correctamente.")


# ════════════════ 6) MAIN ════════════════
if __name__ == "__main__":
    conn = create_connection()
    if not conn:
        raise SystemExit("No fue posible establecer conexión a la base de datos.")

    try:
        # ── Selección del archivo Excel ──
        root = Tk()
        root.withdraw()                        # Oculta la ventana principal de Tkinter
        excel_path = filedialog.askopenfilename(
            title="Seleccionar archivo de Excel",
            filetypes=[("Archivos Excel", "*.xlsx *.xls")]
        )
        if not excel_path:
            raise SystemExit("No se seleccionó ningún archivo de Excel.")

        # Solicitar ID del catálogo
        catalogo_id = input("Ingrese el ID del catálogo: ").strip()

        # Procesar
        process_isrc_file(conn, catalogo_id, excel_path)
    finally:
        conn.close()
        print("Conexión cerrada.")
