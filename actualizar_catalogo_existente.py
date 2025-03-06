from sqlalchemy import create_engine, text
import pandas as pd
from datetime import date
from tkinter import filedialog, Tk

# Conexión a la base de datos MySQL
def create_connection():
    try:
        print("Intentando conectar a la base de datos...")
        engine = create_engine('mysql+mysqlconnector://ADMINISTRADOR:97072201144Ss.@localhost/base_datos_klaim')
        connection = engine.connect()
        print("Conexión exitosa a la base de datos")
        return connection
    except Exception as e:
        print(f"Error en la conexión: {e}")
        return None

# Pedir el id_cliente al usuario
def obtener_id_cliente(connection):
    id_cliente = input("Ingrese el ID del cliente existente: ")
    print(f"Verificando el ID del cliente {id_cliente} en la base de datos...")
    query = text("SELECT id_cliente FROM Clientes WHERE id_cliente = :id_cliente")
    result = connection.execute(query, {'id_cliente': id_cliente}).fetchone()
    if result:
        print(f"ID de cliente {id_cliente} encontrado.")
        return id_cliente
    else:
        raise ValueError("ID de cliente incorrecto. Por favor verifique el ID ingresado.")

# Obtener las obras del cliente en la base de datos
def obtener_obras_cliente(connection, id_cliente):
    print(f"Obteniendo obras del cliente con ID {id_cliente}...")
    query = text("SELECT codigo_sgs FROM Obras WHERE catalogo_id IN (SELECT id_catalogo FROM Catalogos WHERE id_cliente = :id_cliente)")
    result = connection.execute(query, {'id_cliente': id_cliente}).fetchall()
    obras = set(int(row[0]) for row in result)  # Convertir los códigos SGS a enteros
    print(f"Obras obtenidas: {len(obras)} códigos SGS encontrados.")
    return obras

# Leer catálogo desde un archivo Excel seleccionado por el usuario
def seleccionar_archivo_excel():
    print("Abriendo diálogo para seleccionar el archivo Excel del catálogo...")
    root = Tk()
    root.withdraw()  # Ocultar la ventana principal de Tkinter
    file_path = filedialog.askopenfilename(title="Seleccione el archivo Excel del catálogo")
    if file_path:
        print(f"Catálogo seleccionado: {file_path}")
        return pd.read_excel(file_path)
    else:
        raise ValueError("No se seleccionó ningún archivo.")

# Optimización de la extracción de códigos SGS únicos en el DataFrame
def obtener_codigos_sgs_nuevo_catalogo(catalogo_df):
    print("Extrayendo códigos SGS únicos del nuevo catálogo...")
    catalogo_df['Código SGS'] = catalogo_df['Código SGS'].astype(int)  # Convertir a entero para asegurar consistencia
    codigos_sgs = set(catalogo_df[['Título', 'Código SGS']].drop_duplicates()['Código SGS'])
    print(f"{len(codigos_sgs)} códigos SGS únicos encontrados en el nuevo catálogo.")
    return codigos_sgs

# Procesar el catálogo y crear las listas para registrar, liberar y continuar
def procesar_catalogo_nuevo(connection, catalogo_df, obras_existentes):
    print("Procesando el catálogo nuevo y comparando con obras existentes...")
    
    # Lista de códigos SGS del nuevo catálogo
    lista_1 = obtener_codigos_sgs_nuevo_catalogo(catalogo_df)
    lista_2 = obras_existentes

    # Crear listas para registrar, liberar y continuar usando operaciones de conjuntos para mejorar rendimiento
    registrar = lista_1 - lista_2
    liberar = lista_2 - lista_1
    continúan = lista_1 & lista_2

    print(f"Códigos a registrar: {len(registrar)}")
    print(f"Códigos a liberar: {len(liberar)}")
    print(f"Códigos que continúan: {len(continúan)}")
    
    return list(registrar), list(liberar), list(continúan)

def liberar_obras(connection, liberar, id_cliente):
    print("Liberando obras en la base de datos...")
    registros = []

    for codigo_sgs in liberar:
        # Consulta mejorada para obtener los detalles de la obra y concatenar autores y porcentajes
        query_obras = text("""
            SELECT o.cod_klaim, o.titulo, o.codigo_iswc, 
                   GROUP_CONCAT(a.nombre_autor SEPARATOR ';') AS nombre_autor,
                   GROUP_CONCAT(oa.porcentaje_autor SEPARATOR ';') AS porcentaje_autor
            FROM Obras o
            LEFT JOIN obrasautores oa ON o.cod_klaim = oa.obra_id
            LEFT JOIN autoresunicos a ON oa.autor_id = a.id_autor
            LEFT JOIN Catalogos c ON o.catalogo_id = c.id_catalogo
            WHERE o.codigo_sgs = :codigo_sgs AND c.id_cliente = :id_cliente
            GROUP BY o.cod_klaim, o.titulo, o.codigo_iswc
        """)
        
        result = connection.execute(query_obras, {'codigo_sgs': codigo_sgs, 'id_cliente': id_cliente}).fetchone()
        
        if result:
            cod_klaim, titulo, codigo_iswc, nombre_autor, porcentaje_autor = result
            registros.append({
                'cod_klaim': cod_klaim,
                'titulo': titulo,
                'codigo_sgs': codigo_sgs,
                'codigo_iswc': codigo_iswc,
                'id_cliente': id_cliente,
                'nombre_autor': nombre_autor,
                'porcentaje_autor': porcentaje_autor,
                'fecha_creacion': date.today(),
                'estado_liberacion': 'vigente'
            })
        else:
            print(f"No se encontró obra con código SGS {codigo_sgs} para el cliente con ID {id_cliente}")

    # Insertar en lotes de hasta 10,000 registros
    lote_tamano = 10000
    for i in range(0, len(registros), lote_tamano):
        lote = registros[i:i + lote_tamano]
        query_liberar = text("""
            INSERT INTO obras_liberadas 
            (cod_klaim, titulo, codigo_sgs, codigo_iswc, id_cliente, nombre_autor, porcentaje_autor, fecha_creacion, estado_liberacion) 
            VALUES (:cod_klaim, :titulo, :codigo_sgs, :codigo_iswc, :id_cliente, :nombre_autor, :porcentaje_autor, :fecha_creacion, :estado_liberacion)
        """)
        connection.execute(query_liberar, lote)
        connection.commit()  # Confirmar cada lote en la base de datos
        print(f"Se han liberado {len(lote)} registros en este lote.")

    print(f"Se han liberado {len(registros)} registros en total.")

def generar_excel_obras_liberadas(connection, liberar, id_cliente):
    print("Generando el archivo Excel con las obras liberadas...")
    registros = []

    for codigo_sgs in liberar:
        # Consulta mejorada para obtener los detalles de la obra, incluyendo cod_klaim, codigo_MLC y codigo_ADREV
        query_obras_liberadas = text("""
            SELECT o.cod_klaim AS `Cod_Klaim`, o.titulo AS `Título`, o.codigo_sgs AS `Código SGS`, 
                   o.codigo_iswc AS `Código ISWC`, a.nombre_autor AS `Nombre Autor`, 
                   a.codigo_ipi AS `Número IP Autor`, a.tipo_autor AS `Tipo de Autor`, 
                   oa.porcentaje_autor AS `Porcentaje Reclamado de Autor`,
                   GROUP_CONCAT(ar.nombre_artista SEPARATOR ';') AS Artistas,
                   sp.codigo_MLC AS `Código MLC`, sp.codigo_ADREV AS `Código ADREV`
            FROM obras_liberadas o
            LEFT JOIN obrasautores oa ON o.cod_klaim = oa.obra_id
            LEFT JOIN autoresunicos a ON oa.autor_id = a.id_autor
            LEFT JOIN artistas ar ON o.cod_klaim = ar.obra_id
            LEFT JOIN subidas_plataforma sp ON o.cod_klaim = sp.obra_id
            WHERE o.codigo_sgs = :codigo_sgs AND o.id_cliente = :id_cliente
            GROUP BY o.cod_klaim, o.titulo, o.codigo_sgs, o.codigo_iswc, a.nombre_autor, 
                     a.codigo_ipi, a.tipo_autor, oa.porcentaje_autor, sp.codigo_MLC, sp.codigo_ADREV
        """)

        # Usar mappings() para obtener diccionarios en lugar de tuplas
        results = connection.execute(query_obras_liberadas, {'codigo_sgs': codigo_sgs, 'id_cliente': id_cliente}).mappings().all()

        # Agregar cada resultado al listado de registros
        for row in results:
            registros.append(row)

    # Convertir los registros en un DataFrame de pandas
    df = pd.DataFrame(registros)

    # Guardar el DataFrame en un archivo Excel
    output_path = 'obras_liberadas.xlsx'
    df.to_excel(output_path, index=False)
    print(f"Archivo Excel generado con éxito: {output_path}")


def obtener_id_catalogo_existente(connection, id_cliente):
    # Recupera el id_catalogo activo para el id_cliente especificado
    query = text("SELECT id_catalogo FROM Catalogos WHERE id_cliente = :id_cliente AND estado = 'Activo'")
    result = connection.execute(query, {'id_cliente': id_cliente}).fetchone()
    if result:
        return result[0]  # Retorna el id_catalogo si existe
    else:
        raise ValueError(f"No se encontró un catálogo activo para el cliente con ID {id_cliente}")

# Insertar datos en la tabla Obras si no existen
def registrar_obras(connection, catalogo_df, registrar, id_cliente):
    print("Registrando nuevas obras en la base de datos...")
    
    # Obtener el id_catalogo del cliente ingresado por el usuario
    query_catalogo = text("""
        SELECT id_catalogo 
        FROM Catalogos 
        WHERE id_cliente = :id_cliente AND estado = 'Activo'
    """)
    id_catalogo = connection.execute(query_catalogo, {'id_cliente': id_cliente}).fetchone()[0]

    # Variables para rastrear obras ya insertadas
    obras_existentes = set()

    for codigo_sgs in registrar:
        # Filtrar el DataFrame para obtener solo las filas correspondientes a esta obra específica
        obra_rows = catalogo_df[catalogo_df['Código SGS'] == codigo_sgs]

        # Verificar si esta obra ya fue insertada usando `titulo` y `codigo_sgs`
        titulo = obra_rows.iloc[0]['Título']
        codigo_iswc = obra_rows.iloc[0]['Código ISWC'] if pd.notna(obra_rows.iloc[0]['Código ISWC']) else None
        
        if (titulo, codigo_sgs) in obras_existentes:
            continue

        # Insertar la obra en `Obras` y obtener `obra_id`
        obra_id_actual = insert_obras(connection, titulo, codigo_sgs, codigo_iswc, id_catalogo)
        obras_existentes.add((titulo, codigo_sgs))  # Marcar la obra como registrada

        # Procesar artistas (en caso de múltiples artistas)
        artistas = obra_rows.iloc[0]['Artistas'] if pd.notna(obra_rows.iloc[0]['Artistas']) else None
        if artistas:
            artistas_lista = artistas.split(';')
            for artista in artistas_lista:
                insert_artistas(connection, artista.strip(), obra_id_actual)

        # Procesar autores y porcentajes para cada fila de la misma obra
        for _, row in obra_rows.iterrows():
            nombre_autor = row['Nombre Autor'] if pd.notna(row['Nombre Autor']) else None
            numero_ip_autor = row['Número IP Autor'] if pd.notna(row['Número IP Autor']) else None
            tipo_autor = row['Tipo de Autor'] if pd.notna(row['Tipo de Autor']) else None
            porcentaje_autor = row['Porcentaje Reclamado de Autor'] if pd.notna(row['Porcentaje Reclamado de Autor']) else None

            if nombre_autor and tipo_autor and porcentaje_autor:
                # Insertar o encontrar el autor único
                autor_id = insert_autores_unicos(connection, nombre_autor.strip(), numero_ip_autor, tipo_autor.strip())
                # Insertar el porcentaje en la relación ObrasAutores
                insert_obras_autores(connection, obra_id_actual, autor_id, float(porcentaje_autor))

    connection.execute(text("COMMIT"))
    print("Nuevas obras registradas exitosamente.")

# Funciones de apoyo para insertar datos en las tablas (las mismas de registrar_catalogo_nuevo)

def insert_obras(connection, titulo, codigo_sgs, codigo_iswc, catalogo_id):
    query = text("INSERT INTO Obras (titulo, codigo_sgs, codigo_iswc, catalogo_id) VALUES (:titulo, :codigo_sgs, :codigo_iswc, :catalogo_id)")
    connection.execute(query, {'titulo': titulo, 'codigo_sgs': codigo_sgs, 'codigo_iswc': codigo_iswc, 'catalogo_id': catalogo_id})
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

def insert_artistas(connection, nombre_artista, obra_id):
    query = text("INSERT INTO Artistas (nombre_artista, obra_id) VALUES (:nombre_artista, :obra_id)")
    connection.execute(query, {'nombre_artista': nombre_artista, 'obra_id': obra_id})

def insert_autores_unicos(connection, nombre_autor, codigo_ipi, tipo_autor):
    query = text("INSERT INTO AutoresUnicos (nombre_autor, codigo_ipi, tipo_autor) VALUES (:nombre_autor, :codigo_ipi, :tipo_autor)")
    connection.execute(query, {'nombre_autor': nombre_autor, 'codigo_ipi': codigo_ipi, 'tipo_autor': tipo_autor})
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

def insert_obras_autores(connection, obra_id, autor_id, porcentaje_autor):
    query = text("INSERT INTO ObrasAutores (obra_id, autor_id, porcentaje_autor) VALUES (:obra_id, :autor_id, :porcentaje_autor)")
    connection.execute(query, {'obra_id': obra_id, 'autor_id': autor_id, 'porcentaje_autor': porcentaje_autor})
# Main
if __name__ == "__main__":
    connection = create_connection()
    
    if connection:
        try:
            # Obtener el ID del cliente
            id_cliente = obtener_id_cliente(connection)
            
            # Obtener las obras existentes del cliente en la base de datos
            obras_existentes = obtener_obras_cliente(connection, id_cliente)

            # Seleccionar y leer el archivo Excel del nuevo catálogo
            catalogo_df = seleccionar_archivo_excel()

            # Procesar el catálogo y obtener las listas de registrar, liberar y continuar
            registrar, liberar, continúan = procesar_catalogo_nuevo(connection, catalogo_df, obras_existentes)

            # Registrar las nuevas obras en la base de datos usando el id_catalogo del cliente
            registrar_obras(connection, catalogo_df, registrar, id_cliente)

            # Liberar las obras en la base de datos
            liberar_obras(connection, liberar, id_cliente)

            # Generar el archivo Excel con las listas
            generar_excel_obras_liberadas(connection, liberar, id_cliente)

        except ValueError as ve:
            print(ve)
        finally:
            connection.close()
            print("Conexión cerrada.")
    else:
        print("Error al conectar a la base de datos")