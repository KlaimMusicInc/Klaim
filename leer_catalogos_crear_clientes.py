from sqlalchemy import create_engine, text
import pandas as pd
from datetime import date

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

# Leer catálogo desde Excel
def read_catalog_from_excel(file_path):
    try:
        df = pd.read_excel(file_path)
        print(f"Catálogo leído correctamente desde {file_path}")
        return df
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        return None

# Verificar si el cliente ya está en la base de datos
def cliente_ya_insertado(connection, nombre_cliente):
    query = text("SELECT id_cliente FROM Clientes WHERE nombre_cliente = :nombre_cliente")
    result = connection.execute(query, {'nombre_cliente': nombre_cliente}).fetchone()
    if result:
        return result[0]  # Retornar el id_cliente si existe
    return None

# Insertar datos en la tabla Clientes si no están ya insertados
def insert_client(connection, nombre_cliente, tipo_cliente):
    id_cliente_existente = cliente_ya_insertado(connection, nombre_cliente)
    if id_cliente_existente:
        return id_cliente_existente
    query = text("INSERT INTO Clientes (nombre_cliente, tipo_cliente) VALUES (:nombre_cliente, :tipo_cliente)")
    connection.execute(query, {'nombre_cliente': nombre_cliente, 'tipo_cliente': tipo_cliente})
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

# Insertar datos en la tabla Catálogos
def insert_catalog(connection, id_cliente, fecha_recibido, estado='Activo'):
    query = text("INSERT INTO Catalogos (id_cliente, fecha_recibido, estado) VALUES (:id_cliente, :fecha_recibido, :estado)")
    connection.execute(query, {'id_cliente': id_cliente, 'fecha_recibido': fecha_recibido, 'estado': estado})
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

# Insertar datos en la tabla Obras
def insert_obras(connection, titulo, codigo_sgs, codigo_iswc, catalogo_id):
    query = text("INSERT INTO Obras (titulo, codigo_sgs, codigo_iswc, catalogo_id) VALUES (:titulo, :codigo_sgs, :codigo_iswc, :catalogo_id)")
    connection.execute(query, {'titulo': titulo, 'codigo_sgs': codigo_sgs, 'codigo_iswc': codigo_iswc, 'catalogo_id': catalogo_id})
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

# Verificar si el artista ya existe en artistas_unicos y devolver el id_artista_unico
def artista_unico_ya_insertado(connection, nombre_artista):
    query = text("SELECT id_artista_unico FROM artistas_unicos WHERE nombre_artista = :nombre_artista")
    result = connection.execute(query, {'nombre_artista': nombre_artista}).fetchone()
    return result[0] if result else None

# Insertar datos en la tabla artistas_unicos y devolver el id_artista_unico
def insert_artista_unico(connection, nombre_artista):
    artista_id_existente = artista_unico_ya_insertado(connection, nombre_artista)
    if artista_id_existente:
        return artista_id_existente
    query = text("INSERT INTO artistas_unicos (nombre_artista) VALUES (:nombre_artista)")
    connection.execute(query, {'nombre_artista': nombre_artista})
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

# Insertar datos en la tabla artistas con relación a artistas_unicos y la obra
def insert_artistas(connection, nombre_artista, obra_id):
    # Obtener el id_artista_unico (insertar si no existe)
    id_artista_unico = insert_artista_unico(connection, nombre_artista)
    # Insertar el artista en la tabla artistas con la referencia a la obra
    query = text("INSERT INTO artistas (nombre_artista, obra_id, id_artista_unico) VALUES (:nombre_artista, :obra_id, :id_artista_unico)")
    connection.execute(query, {'nombre_artista': nombre_artista, 'obra_id': obra_id, 'id_artista_unico': id_artista_unico})
# Verificar si el autor ya existe en AutoresUnicos y devolver el id_autor_unico
def autor_ya_insertado(connection, nombre_autor, codigo_ipi, tipo_autor):
    query = text("SELECT id_autor FROM AutoresUnicos WHERE nombre_autor = :nombre_autor AND codigo_ipi = :codigo_ipi AND tipo_autor = :tipo_autor")
    result = connection.execute(query, {
        'nombre_autor': nombre_autor, 
        'codigo_ipi': codigo_ipi, 
        'tipo_autor': tipo_autor
    }).fetchone()
    return result[0] if result else None

# Insertar datos en la tabla AutoresUnicos y devolver el id_autor_unico
def insert_autores_unicos(connection, nombre_autor, codigo_ipi, tipo_autor):
    autor_id_existente = autor_ya_insertado(connection, nombre_autor, codigo_ipi, tipo_autor)
    if autor_id_existente:
        return autor_id_existente
    query = text("INSERT INTO AutoresUnicos (nombre_autor, codigo_ipi, tipo_autor) VALUES (:nombre_autor, :codigo_ipi, :tipo_autor)")
    connection.execute(query, {'nombre_autor': nombre_autor, 'codigo_ipi': codigo_ipi, 'tipo_autor': tipo_autor})
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

# Insertar datos en la tabla ObrasAutores con porcentaje_autor
def insert_obras_autores(connection, obra_id, autor_id, porcentaje_autor):
    query = text("INSERT INTO ObrasAutores (obra_id, autor_id, porcentaje_autor) VALUES (:obra_id, :autor_id, :porcentaje_autor)")
    connection.execute(query, {
        'obra_id': obra_id, 
        'autor_id': autor_id, 
        'porcentaje_autor': porcentaje_autor
    })

# Procesar y cargar un catálogo completo
def process_and_load_catalog(file_path, connection, nombre_cliente, tipo_cliente, fecha_recibido):
    # Leer el catálogo desde el archivo Excel
    catalogo_df = read_catalog_from_excel(file_path)
    
    # Crear o verificar que el cliente existe
    id_cliente = insert_client(connection, nombre_cliente, tipo_cliente)
    # Crear un nuevo registro en la tabla Catálogos
    catalogo_id = insert_catalog(connection, id_cliente, fecha_recibido)
    
    # Variable para recordar la obra actual
    obra_actual = None
    obra_id_actual = None
    
    # Procesar cada fila del DataFrame (cada obra)
    for index, row in catalogo_df.iterrows():
        titulo = row['Título']
        codigo_sgs = row['Código SGS']

        # Verificación para detectar NaN
        if pd.isna(titulo) or pd.isna(codigo_sgs):
            print(f"Fila {index + 1} contiene valores nulos: Título: {titulo}, Código SGS: {codigo_sgs}")
            continue  # Saltamos esta fila si tiene valores NaN
        
        codigo_iswc = row['Código ISWC'] if pd.notna(row['Código ISWC']) else None
        
        # Identificar si estamos en una nueva obra
        if (titulo != obra_actual) or (codigo_sgs != codigo_sgs):
            obra_actual = titulo
            obra_id_actual = insert_obras(connection, titulo, codigo_sgs, codigo_iswc, catalogo_id)
        
        # Procesar artistas (si hay, están separados por ";")
        artistas = row['Artistas'] if pd.notna(row['Artistas']) else None
        if artistas:
            artistas_lista = artistas.split(';')
            for artista in artistas_lista:
                insert_artistas(connection, artista.strip(), obra_id_actual)
        
        # Procesar autor (un autor por fila)
        nombre_autor = row['Nombre Autor'] if pd.notna(row['Nombre Autor']) else None
        numero_ip_autor = row['Número IP Autor'] if pd.notna(row['Número IP Autor']) else None
        tipo_autor = row['Tipo de Autor'] if pd.notna(row['Tipo de Autor']) else None
        porcentaje_autor = row['Porcentaje Reclamado de Autor'] if pd.notna(row['Porcentaje Reclamado de Autor']) else None

        if nombre_autor and tipo_autor and porcentaje_autor:
            # Insertar o encontrar el autor único
            autor_id = insert_autores_unicos(connection, nombre_autor.strip(), numero_ip_autor, tipo_autor.strip())
            # Insertar el porcentaje en la relación ObrasAutores
            insert_obras_autores(connection, obra_id_actual, autor_id, float(porcentaje_autor))
    
    # Confirmar los cambios en la base de datos
    connection.execute(text("COMMIT"))
    print(f"Catálogo procesado y guardado en la base de datos: {file_path}")

# Main
if __name__ == "__main__":
    connection = create_connection()
    
    if connection:
        # Información de los clientes y catálogos
        
        #cliente_1 = {'nombre': 'SAYCO', 'tipo': 'sociedad Gestion colectiva', 'fecha_recibido': date.today().strftime('%Y-%m-%d')}
        #cliente_2 = {'nombre': 'SAYCE', 'tipo': 'sociedad Gestion colectiva', 'fecha_recibido': date.today().strftime('%Y-%m-%d')}
        #cliente_3 = {'nombre': 'PRUEBA', 'tipo': 'sociedad Gestion colectiva', 'fecha_recibido': date.today().strftime('%Y-%m-%d')}
        cliente_4 = {'nombre': 'SACVEN', 'tipo': 'sociedad Gestion colectiva', 'fecha_recibido': date.today().strftime('%Y-%m-%d')}
        
        # Procesar catálogos de diferentes clientes
        #process_and_load_catalog('catalogo_sayco.xlsx', connection, cliente_1['nombre'], cliente_1['tipo'], cliente_1['fecha_recibido'])
        #process_and_load_catalog('catalogo_sayce.xlsx', connection, cliente_2['nombre'], cliente_2['tipo'], cliente_2['fecha_recibido'])
        #process_and_load_catalog('catalogo_para_pruebas.xlsx', connection, cliente_3['nombre'], cliente_3['tipo'], cliente_3['fecha_recibido'])
        process_and_load_catalog('CATALOGO_SACVEN_DICIEMBRE.xlsx', connection, cliente_4['nombre'], cliente_4['tipo'], cliente_4['fecha_recibido'])

        connection.close()
    else:
        print("Error al conectar a la base de datos")