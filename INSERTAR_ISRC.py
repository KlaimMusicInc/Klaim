from sqlalchemy import create_engine, text
import pandas as pd

# Conexión a la base de datos MySQL
def create_connection():
    try:
        engine = create_engine('mysql+mysqlconnector://ADMINISTRADOR:97072201144Ss.@localhost/base_datos_klaim')
        connection = engine.connect()
        print("Conexión exitosa a la base de datos")
        return connection
    except Exception as e:
        print(f"Error en la conexión: {e}")
        return None

# Obtener las obras asociadas a un catálogo
def get_obras_by_catalogo(connection, id_catalogo):
    query = text("""
        SELECT cod_klaim AS obra_id, codigo_sgs
        FROM obras
        WHERE catalogo_id = :id_catalogo
    """)
    result = connection.execute(query, {'id_catalogo': id_catalogo}).fetchall()
    return {int(row[1]): row[0] for row in result}

# Verificar si el artista único ya existe y obtener su ID
def get_or_create_artista_unico(connection, nombre_artista):
    query = text("SELECT id_artista_unico FROM artistas_unicos WHERE LOWER(nombre_artista) = LOWER(:nombre_artista)")
    result = connection.execute(query, {'nombre_artista': nombre_artista}).fetchone()
    if result:
        return result[0]
    insert_query = text("INSERT INTO artistas_unicos (nombre_artista) VALUES (:nombre_artista)")
    connection.execute(insert_query, {'nombre_artista': nombre_artista})
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

# Insertar un registro en la tabla codigos_isrc
def insert_codigo_isrc(connection, codigo_isrc, obra_id, id_artista_unico, name_artista_alternativo, titulo_alternativo):
    query = text("""
        INSERT INTO codigos_isrc (codigo_isrc, obra_id, id_artista_unico, name_artista_alternativo, titulo_alternativo)
        VALUES (:codigo_isrc, :obra_id, :id_artista_unico, :name_artista_alternativo, :titulo_alternativo)
    """)
    connection.execute(query, {
        'codigo_isrc': codigo_isrc,
        'obra_id': obra_id,
        'id_artista_unico': id_artista_unico,
        'name_artista_alternativo': name_artista_alternativo,
        'titulo_alternativo': titulo_alternativo
    })
# Procesar filas con validación de valores nulos y asignación de valores predeterminados
def process_row(row, obras_dict, connection):
    # Extraer valores de la fila y asignar valores predeterminados si son nulos
    codigo_sgs = row['CODIGO SGS']
    codigo_isrc = row['ISRC']
    nombre_artista = row['Nombre_artista'] if pd.notna(row['Nombre_artista']) else "NO IDENTIFICADO"
    artista_real = row['Artista_REAL'] if pd.notna(row['Artista_REAL']) else "NO IDENTIFICADO"
    cancion_real = row['Cancion_REAL'] if pd.notna(row['Cancion_REAL']) else "NO IDENTIFICADO"

    # Verificar si el código SGS está en las obras asociadas
    obra_id = obras_dict.get(codigo_sgs)
    if obra_id is None:
        # Si no se encuentra, devolver la fila como no encontrada
        return row  

    # Advertencias si los valores son predeterminados
    if nombre_artista == "NO IDENTIFICADO":
        print(f"Advertencia: Nombre de artista no identificado para código SGS {codigo_sgs}.")
    if artista_real == "NO IDENTIFICADO":
        print(f"Advertencia: Artista alternativo no identificado para código SGS {codigo_sgs}.")
    if cancion_real == "NO IDENTIFICADO":
        print(f"Advertencia: Título alternativo no identificado para código SGS {codigo_sgs}.")

    # Buscar o crear el artista único
    id_artista_unico = get_or_create_artista_unico(connection, nombre_artista)

    # Insertar el registro en la tabla codigos_isrc
    insert_codigo_isrc(
        connection,
        codigo_isrc=codigo_isrc,
        obra_id=obra_id,
        id_artista_unico=id_artista_unico,
        name_artista_alternativo=artista_real,
        titulo_alternativo=cancion_real
    )
    return None  # Si se procesa correctamente, no devolver la fila

# Procesar el archivo Excel con manejo de valores nulos
def process_isrc_file(connection, id_catalogo, excel_path):
    obras_dict = get_obras_by_catalogo(connection, id_catalogo)
    df = pd.read_excel(excel_path)
    df['CODIGO SGS'] = pd.to_numeric(df['CODIGO SGS'], errors='coerce').fillna(0).astype(int)

    total_rows = len(df)
    not_found_rows = []

    def process_with_progress(row, index):
        result = process_row(row, obras_dict, connection)
        if index % 10 == 0 or index == total_rows - 1:
            print(f"Procesando fila {index + 1}/{total_rows}...")
        return result

    # Procesar filas con progreso y manejo de nulos
    not_found_rows = [process_with_progress(row, index) for index, row in df.iterrows()]
    not_found_df = pd.DataFrame([row for row in not_found_rows if row is not None])

    if not not_found_df.empty:
        not_found_df.to_excel('ISRC_no_encontrados.xlsx', index=False)
        print("Archivo 'ISRC_no_encontrados.xlsx' generado con registros no encontrados.")
    
    connection.execute(text("COMMIT"))
    print("Códigos ISRC procesados y guardados en la base de datos.")

# Main
if __name__ == "__main__":
    connection = create_connection()
    if connection:
        try:
            id_catalogo = input("Ingrese el ID del catálogo: ")
            process_isrc_file(connection, id_catalogo, "ISRC_SAYCO_NUEVAS.xlsx")
        finally:
            connection.close()
            print("Conexión cerrada.")
    else:
        print("Error al conectar a la base de datos")
