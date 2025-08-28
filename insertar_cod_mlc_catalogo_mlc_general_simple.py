import mysql.connector
import pandas as pd
from tqdm import tqdm  # Para mostrar progreso en consola
from unidecode import unidecode

# 🚀 Conectar a la base de datos
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="97072201144Ss.",
    database="base_datos_klaim",
)
cursor = conexion.cursor(dictionary=True)

# 🚀 Cargar el archivo Excel
archivo_excel = "catalogo_mlc.xlsx"
df = pd.read_excel(archivo_excel)


# 🚀 Función para separar nombres en conjuntos de palabras (sin importar el orden)
def nombre_a_set(nombre):
    if pd.notna(nombre):
        # 🔹 Convertir a minúsculas y eliminar tildes
        nombre_limpio = unidecode(nombre.strip().lower())
        # 🔹 Convertir en conjunto de palabras para comparación flexible
        return set(nombre_limpio.split())
    return set()


# 🚀 Extraer los autores de cada fila como listas de conjuntos de palabras
def obtener_claves_autores(row):
    autores = [
        nombre_a_set(
            f"{row.get(f'WRITER FIRST NAME {i}', '').strip()} {row.get(f'WRITER LAST NAME {i}', '').strip()}"
        )
        for i in range(1, 44)
        if pd.notna(row.get(f"WRITER FIRST NAME {i}"))
        and pd.notna(row.get(f"WRITER LAST NAME {i}"))
    ]
    return autores


df["clave_unica_autor"] = df.apply(obtener_claves_autores, axis=1)

# 🚀 Preparar DataFrames para Reporte
actualizados, sin_cambios, no_encontrados = [], [], []

# 🚀 Obtener todas las obras y autores en caché
cursor.execute(
    "SELECT o.cod_klaim, o.codigo_iswc, o.titulo, au.nombre_autor FROM obras o JOIN obrasautores oa ON o.cod_klaim = oa.obra_id JOIN autoresunicos au ON oa.autor_id = au.id_autor"
)
obras_dict = {row["codigo_iswc"]: row for row in cursor.fetchall()}
autores_dict = {
    tuple(sorted(nombre_a_set(row["nombre_autor"]))): row["cod_klaim"]
    for row in obras_dict.values()
}
# 🚀 Obtener todas las subidas de la plataforma
cursor.execute("SELECT obra_id, codigo_MLC FROM subidas_plataforma")
subidas_dict = {row["obra_id"]: row["codigo_MLC"] for row in cursor.fetchall()}

# 🚀 Procesar cada obra con una barra de progreso
print("\n🔄 Procesando obras...")
for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="Progreso", unit="obra"):
    titulo = row["PRIMARY TITLE"].strip()
    codigo_mlc = (
        row["MLC SONG CODE"].strip() if pd.notna(row["MLC SONG CODE"]) else None
    )
    iswc = row["ISWC"].strip() if pd.notna(row["ISWC"]) else None
    clave_unica_autor = row["clave_unica_autor"]

    obra = None
    if iswc and iswc in obras_dict:
        obra = obras_dict[iswc]

    if not obra and clave_unica_autor:
        for autor_set in clave_unica_autor:
            for db_autor_set, obra_id in autores_dict.items():
                if (
                    autor_set == db_autor_set
                ):  # 🔹 Comparación exacta sin importar el orden
                    obra = obras_dict.get(obra_id)
                    break
            if obra:
                break

    if obra:
        cod_klaim = obra["cod_klaim"]
        codigo_existente = subidas_dict.get(cod_klaim)

        if codigo_existente:  # Ya tiene código MLC
            sin_cambios.append(
                [titulo, iswc if iswc else clave_unica_autor, codigo_existente]
            )
        else:
            actualizados.append((cod_klaim, codigo_mlc))
            subidas_dict[cod_klaim] = codigo_mlc  # Actualizar cache

    else:
        no_encontrados.append(
            [
                titulo,
                iswc if iswc else "N/A",
                ", ".join([" ".join(a) for a in clave_unica_autor]),
                codigo_mlc,
            ]
        )

# 🚀 Insertar los códigos en una sola consulta optimizada
if actualizados:
    cursor.executemany(
        "INSERT INTO subidas_plataforma (obra_id, codigo_MLC) VALUES (%s, %s)",
        actualizados,
    )
    conexion.commit()

# 🚀 Convertir DataFrames y Guardar Reporte
df_actualizados = pd.DataFrame(
    actualizados, columns=["Obra ID", "Código MLC Insertado"]
)
df_sin_cambios = pd.DataFrame(
    sin_cambios, columns=["Título", "ISWC o Clave Única", "Código MLC Existente"]
)
df_no_encontrados = pd.DataFrame(
    no_encontrados, columns=["Título", "ISWC", "Clave Única Autor", "Código MLC"]
)

archivo_salida = "reporte_cambios.xlsx"
with pd.ExcelWriter(archivo_salida, engine="xlsxwriter") as writer:
    df_actualizados.to_excel(writer, sheet_name="Actualizados", index=False)
    df_sin_cambios.to_excel(writer, sheet_name="Sin Cambios", index=False)
    df_no_encontrados.to_excel(writer, sheet_name="No Encontrados", index=False)

print(f"\n✅ Proceso completado. El reporte se ha guardado como '{archivo_salida}'")

# 🚀 Cerrar conexión
cursor.close()
conexion.close()
