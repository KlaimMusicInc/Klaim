from datetime import date
from tkinter import Tk, filedialog

import pandas as pd
from sqlalchemy import create_engine, text
from unidecode import unidecode  # YA está en tu script original


# Conexión a la base de datos MySQL
def create_connection():
    try:
        print("Intentando conectar a la base de datos...")
        engine = create_engine(
            "mysql+mysqlconnector://ADMINISTRADOR:97072201144Ss.@localhost/base_datos_klaim"
        )
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
    result = connection.execute(query, {"id_cliente": id_cliente}).fetchone()
    if result:
        print(f"ID de cliente {id_cliente} encontrado.")
        return id_cliente
    else:
        raise ValueError(
            "ID de cliente incorrecto. Por favor verifique el ID ingresado."
        )


# Obtener las obras del cliente en la base de datos
def obtener_obras_cliente(connection, id_cliente):
    print(f"Obteniendo obras del cliente con ID {id_cliente}...")
    query = text(
        "SELECT codigo_sgs FROM Obras WHERE catalogo_id IN (SELECT id_catalogo FROM Catalogos WHERE id_cliente = :id_cliente)"
    )
    result = connection.execute(query, {"id_cliente": id_cliente}).fetchall()
    obras = set(int(row[0]) for row in result)  # Convertir los códigos SGS a enteros
    print(f"Obras obtenidas: {len(obras)} códigos SGS encontrados.")
    return obras


# Leer catálogo desde un archivo Excel seleccionado por el usuario
def seleccionar_archivo_excel():
    print("Abriendo diálogo para seleccionar el archivo Excel del catálogo...")
    root = Tk()
    root.withdraw()  # Ocultar la ventana principal de Tkinter
    file_path = filedialog.askopenfilename(
        title="Seleccione el archivo Excel del catálogo"
    )
    if file_path:
        print(f"Catálogo seleccionado: {file_path}")
        return pd.read_excel(file_path)
    else:
        raise ValueError("No se seleccionó ningún archivo.")


# Optimización de la extracción de códigos SGS únicos en el DataFrame
def obtener_codigos_sgs_nuevo_catalogo(catalogo_df):
    """
    Devuelve un set de códigos SGS únicos (int).  NO altera el DataFrame original.
    ▸ Hace forward-fill en una copia para que las filas hijas hereden el SGS
      de la fila principal.
    """
    tmp = catalogo_df["Código SGS"].copy().ffill()  # heredar SGS
    tmp = pd.to_numeric(tmp, errors="coerce")  # convertir a num
    codigos_sgs = set(tmp.dropna().astype(int).unique())  # únicos y limpios
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


def exportar_listas_excel(registrar, liberar, continuan):
    pd.DataFrame({"Código SGS": registrar}).to_excel("registrar.xlsx", index=False)
    pd.DataFrame({"Código SGS": liberar}).to_excel("liberar.xlsx", index=False)
    pd.DataFrame({"Código SGS": continuan}).to_excel("continuan.xlsx", index=False)


def liberar_obras(connection, liberar, id_cliente):
    """
    - Inserta en obras_liberadas solo los cod_klaim que aún no existan.
    - Para **todos** los cod_klaim liberados (nuevos o ya existentes) actualiza
      subidas_plataforma →  estado_MLC = estado_ADREV = 'LIBERADA'.
    """
    print("Liberando obras en la base de datos...")

    # ▶ 1.  cod_klaim ya liberados → para no duplicar inserciones
    cod_liberados = {
        row[0]
        for row in connection.execute(
            text("SELECT cod_klaim FROM obras_liberadas WHERE id_cliente = :id"),
            {"id": id_cliente},
        )
    }
    if cod_liberados:
        print(
            f"{len(cod_liberados)} obras ya estaban liberadas; se omitirá su reinserción."
        )

    registros = []  # registros a insertar en obras_liberadas
    cods_a_actualizar = set()  # siempre se actualizarán sus estados de plataforma

    # ▶ 2.  Recorremos la lista de códigos SGS a liberar
    for codigo_sgs in liberar:
        # Traer info de la obra
        obra_q = text(
            """
            SELECT o.cod_klaim, o.titulo, o.codigo_iswc,
                   GROUP_CONCAT(a.nombre_autor  SEPARATOR ';') AS nombre_autor,
                   GROUP_CONCAT(oa.porcentaje_autor SEPARATOR ';') AS porcentaje_autor
            FROM Obras o
            LEFT JOIN obrasautores oa ON o.cod_klaim = oa.obra_id
            LEFT JOIN autoresunicos a ON oa.autor_id = a.id_autor
            LEFT JOIN Catalogos c    ON o.catalogo_id = c.id_catalogo
            WHERE o.codigo_sgs = :codigo_sgs AND c.id_cliente = :id_cliente
            GROUP BY o.cod_klaim, o.titulo, o.codigo_iswc
        """
        )
        row = connection.execute(
            obra_q, {"codigo_sgs": codigo_sgs, "id_cliente": id_cliente}
        ).fetchone()
        if not row:
            print(f"⚠️  SGS {codigo_sgs} no encontrado para cliente {id_cliente}.")
            continue

        cod_klaim, titulo, codigo_iswc, nombre_autor, porcentaje_autor = row
        cods_a_actualizar.add(cod_klaim)  # siempre se actualiza plataforma

        # Si ya estaba liberada, no insertamos de nuevo
        if cod_klaim in cod_liberados:
            print(f"Obra {cod_klaim} ya liberada – solo se actualiza plataforma.")
            continue

        registros.append(
            {
                "cod_klaim": cod_klaim,
                "titulo": titulo,
                "codigo_sgs": codigo_sgs,
                "codigo_iswc": codigo_iswc,
                "id_cliente": id_cliente,
                "nombre_autor": nombre_autor,
                "porcentaje_autor": porcentaje_autor,
                "fecha_creacion": date.today(),
                "estado_liberacion": "vigente",
            }
        )
        cod_liberados.add(cod_klaim)

    # ▶ 3.  Inserción en obras_liberadas (en lotes de 10 000)
    ins_q = text(
        """
        INSERT INTO obras_liberadas
        (cod_klaim, titulo, codigo_sgs, codigo_iswc, id_cliente,
         nombre_autor, porcentaje_autor, fecha_creacion, estado_liberacion)
        VALUES (:cod_klaim, :titulo, :codigo_sgs, :codigo_iswc, :id_cliente,
                :nombre_autor, :porcentaje_autor, :fecha_creacion, :estado_liberacion)
    """
    )
    batch = 10_000
    for i in range(0, len(registros), batch):
        sub = registros[i : i + batch]
        connection.execute(ins_q, sub)
        connection.commit()
        print(f"{len(sub)} nuevas obras liberadas insertadas.")

    # ▶ 4.  Actualizar estados en subidas_plataforma
    upd_q = text(
        """
        UPDATE subidas_plataforma
           SET estado_MLC   = 'LIBERADA',
               estado_ADREV = 'LIBERADA'
         WHERE obra_id = :obra_id
    """
    )
    for obra_id in cods_a_actualizar:
        connection.execute(upd_q, {"obra_id": obra_id})

    connection.commit()
    print(f"Estados de plataforma actualizados para {len(cods_a_actualizar)} obras.")


def generar_excel_obras_liberadas(connection, liberar, id_cliente):
    print("Generando el archivo Excel con las obras liberadas...")
    registros = []

    for codigo_sgs in liberar:
        # Consulta mejorada para obtener los detalles de la obra, incluyendo cod_klaim, codigo_MLC y codigo_ADREV
        query_obras_liberadas = text(
            """
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
        """
        )

        # Usar mappings() para obtener diccionarios en lugar de tuplas
        results = (
            connection.execute(
                query_obras_liberadas,
                {"codigo_sgs": codigo_sgs, "id_cliente": id_cliente},
            )
            .mappings()
            .all()
        )

        # Agregar cada resultado al listado de registros
        for row in results:
            registros.append(row)

    # Convertir los registros en un DataFrame de pandas
    df = pd.DataFrame(registros)

    # Guardar el DataFrame en un archivo Excel
    output_path = "obras_liberadas.xlsx"
    df.to_excel(output_path, index=False)
    print(f"Archivo Excel generado con éxito: {output_path}")


def obtener_id_catalogo_existente(connection, id_cliente):
    # Recupera el id_catalogo activo para el id_cliente especificado
    query = text(
        "SELECT id_catalogo FROM Catalogos WHERE id_cliente = :id_cliente AND estado = 'Activo'"
    )
    result = connection.execute(query, {"id_cliente": id_cliente}).fetchone()
    if result:
        return result[0]  # Retorna el id_catalogo si existe
    else:
        raise ValueError(
            f"No se encontró un catálogo activo para el cliente con ID {id_cliente}"
        )


# Insertar datos en la tabla Obras si no existen
def registrar_obras(connection, catalogo_df, registrar, id_cliente):
    """
    Inserta las nuevas obras y todos sus autores / artistas.
    Utiliza una COPIA del DataFrame donde SGS y Título se han
    rellenado con forward-fill para poder agrupar las filas hijas.
    """
    print("Registrando nuevas obras en la base de datos...")

    id_catalogo = connection.execute(
        text(
            "SELECT id_catalogo FROM Catalogos WHERE id_cliente = :id AND estado = 'Activo'"
        ),
        {"id": id_cliente},
    ).fetchone()[0]

    # ---- copia de trabajo con SGS y Título forward-fill ----
    df_proc = catalogo_df.copy()
    df_proc["Código SGS"] = df_proc["Código SGS"].ffill()
    df_proc["Título"] = df_proc["Título"].ffill()
    df_proc["Código SGS"] = pd.to_numeric(df_proc["Código SGS"], errors="coerce")

    # rastreador interno para evitar duplicados en la misma corrida
    obras_insertadas = set()

    for codigo_sgs in registrar:
        # seleccionar todas las filas (padre + hijas) de esa obra
        obra_rows = df_proc[df_proc["Código SGS"] == codigo_sgs]

        if obra_rows.empty:
            print(f"⚠️ No se encontraron filas para SGS {codigo_sgs} en el Excel.")
            continue

        titulo = obra_rows.iloc[0]["Título"]
        codigo_iswc = (
            obra_rows.iloc[0]["Código ISWC"]
            if pd.notna(obra_rows.iloc[0]["Código ISWC"])
            else None
        )
        codigo_sgs_i = int(codigo_sgs)  # aseguramos int
        # ── VALIDACIONES PREVIAS ────────────────────────────────────────────
        nombres_normalizados = set()
        autores_filtrados = []  # filas únicas, sin duplicar autores
        suma_pct = 0.0

        for _, fila in obra_rows.iterrows():
            n_autor = fila["Nombre Autor"]
            pct = fila["Porcentaje Reclamado de Autor"]

            if pd.isna(n_autor) or pd.isna(pct):
                continue  # saltar filas vacías

            # normalizar nombre (sin tildes, trim, lower)
            nombre_norm = unidecode(str(n_autor).strip().lower())

            # 1) autor duplicado dentro de la misma obra  → omitir duplicado
            if nombre_norm in nombres_normalizados:
                print(
                    f"Autor duplicado '{n_autor}' en SGS {codigo_sgs} – se ignora el duplicado."
                )
                continue

            nombres_normalizados.add(nombre_norm)
            suma_pct += float(pct)
            autores_filtrados.append(fila)

        # 2) porcentaje total > 100 %  → omitir toda la obra
        if suma_pct > 100.0 + 1e-6:  # margen minúsculo por flotantes
            print(
                f"⚠️  Porcentajes ({suma_pct:.2f} %) > 100 % en SGS {codigo_sgs}. "
                f"Obra NO registrada."
            )
            continue
        # ── FIN VALIDACIONES ────────────────────────────────────────────────

        # evitar doble inserción dentro de la misma ejecución
        if (titulo, codigo_sgs_i) in obras_insertadas:
            continue

        obra_id_actual = insert_obras(
            connection, titulo, codigo_sgs_i, codigo_iswc, id_catalogo
        )
        obras_insertadas.add((titulo, codigo_sgs_i))

        # ---------- ARTISTAS ----------
        artistas_raw = obra_rows.iloc[0]["Artistas"]
        if pd.notna(artistas_raw):
            for artista in str(artistas_raw).split(";"):
                insert_artistas(connection, artista.strip(), obra_id_actual)

        # ---------- AUTORES (filtrados y únicos) ----------
        for fila in autores_filtrados:
            n_autor = fila["Nombre Autor"]
            ipi = fila["Número IP Autor"]
            t_autor = fila["Tipo de Autor"]
            pct = float(fila["Porcentaje Reclamado de Autor"])

            autor_id = get_or_create_autor_unico(
                connection, n_autor.strip(), ipi, t_autor.strip()
            )
            insert_obras_autores(connection, obra_id_actual, autor_id, pct)

    connection.execute(text("COMMIT"))
    print("Nuevas obras registradas exitosamente.")


# Funciones de apoyo para insertar datos en las tablas (las mismas de registrar_catalogo_nuevo)


def insert_obras(connection, titulo, codigo_sgs, codigo_iswc, catalogo_id):
    query = text(
        "INSERT INTO Obras (titulo, codigo_sgs, codigo_iswc, catalogo_id) VALUES (:titulo, :codigo_sgs, :codigo_iswc, :catalogo_id)"
    )
    connection.execute(
        query,
        {
            "titulo": titulo,
            "codigo_sgs": codigo_sgs,
            "codigo_iswc": codigo_iswc,
            "catalogo_id": catalogo_id,
        },
    )
    return connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]


def get_or_create_artista_unico(connection, nombre_artista):
    """
    Devuelve el id_artista_unico correspondiente al nombre.
    Si no existe, lo crea y devuelve el nuevo id.
    La búsqueda es case-insensitive y sin espacios extra.
    """
    nombre_normalizado = nombre_artista.strip()

    # 1. Intentar recuperar
    query_sel = text(
        """
        SELECT id_artista_unico
        FROM artistas_unicos
        WHERE nombre_artista = :nombre
        LIMIT 1
    """
    )
    result = connection.execute(query_sel, {"nombre": nombre_normalizado}).fetchone()
    if result:
        return result[0]

    # 2. No existe → insertar
    query_ins = text(
        """
        INSERT INTO artistas_unicos (nombre_artista)
        VALUES (:nombre)
    """
    )
    connection.execute(query_ins, {"nombre": nombre_normalizado})
    new_id = connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
    return new_id


def insert_artistas(connection, nombre_artista, obra_id):
    # 1. Obtener id_artista_unico
    id_artista_unico = get_or_create_artista_unico(connection, nombre_artista)

    # 2. Insertar relación obra-artista
    query = text(
        """
        INSERT INTO artistas (nombre_artista, obra_id, id_artista_unico)
        VALUES (:nombre_artista, :obra_id, :id_unico)
    """
    )
    connection.execute(
        query,
        {
            "nombre_artista": nombre_artista,
            "obra_id": obra_id,
            "id_unico": id_artista_unico,
        },
    )


def get_or_create_autor_unico(connection, nombre_autor, codigo_ipi, tipo_autor):
    """
    Devuelve id_autor correspondiente al trío (nombre, ipi, tipo).
    Si no existe, lo crea y devuelve el nuevo id.
    """
    nombre_norm = nombre_autor.strip()

    # 1. Buscar existente
    sel = text(
        """
        SELECT id_autor
        FROM autoresunicos
        WHERE nombre_autor = :nombre
          AND codigo_ipi   = :ipi
          AND tipo_autor   = :tipo
        LIMIT 1
    """
    )
    row = connection.execute(
        sel, {"nombre": nombre_norm, "ipi": codigo_ipi, "tipo": tipo_autor}
    ).fetchone()
    if row:
        return row[0]

    # 2. Insertar si no existe
    ins = text(
        """
        INSERT INTO autoresunicos (nombre_autor, codigo_ipi, tipo_autor)
        VALUES (:nombre, :ipi, :tipo)
    """
    )
    connection.execute(
        ins, {"nombre": nombre_norm, "ipi": codigo_ipi, "tipo": tipo_autor}
    )
    new_id = connection.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
    return new_id


def insert_autores_unicos(connection, nombre_autor, codigo_ipi, tipo_autor):
    return get_or_create_autor_unico(connection, nombre_autor, codigo_ipi, tipo_autor)


def insert_obras_autores(connection, obra_id, autor_id, porcentaje_autor):
    query = text(
        "INSERT INTO ObrasAutores (obra_id, autor_id, porcentaje_autor) VALUES (:obra_id, :autor_id, :porcentaje_autor)"
    )
    connection.execute(
        query,
        {
            "obra_id": obra_id,
            "autor_id": autor_id,
            "porcentaje_autor": porcentaje_autor,
        },
    )


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
            registrar, liberar, continúan = procesar_catalogo_nuevo(
                connection, catalogo_df, obras_existentes
            )
            exportar_listas_excel(registrar, liberar, continúan)
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
