import pandas as pd
import mysql.connector

# Configuración de la conexión a la base de datos
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '97072201144Ss.',
    'database': 'base_datos_klaim'
}

# Archivo Excel con las columnas 'cod_klaim' y 'codigo_mlc'
excel_file = r'C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject\codigos_mlc_sayco2.xlsx'

# Leer el archivo Excel
df = pd.read_excel(excel_file)

# Conectar a la base de datos
conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

# Iterar sobre cada fila del archivo Excel
for index, row in df.iterrows():
    cod_klaim = row['cod_klaim']
    codigo_mlc = row['codigo_mlc']
    
    try:
        # Verificar si existe el cod_klaim en la tabla subidas_plataforma
        cursor.execute("SELECT id_subida FROM subidas_plataforma WHERE obra_id = %s", (cod_klaim,))
        result = cursor.fetchone()
        
        # Consumir todos los resultados para evitar errores de "Unread result found"
        if cursor.with_rows:
            cursor.fetchall()
        
        if result:
            # Si existe, actualizar el valor de codigo_MLC
            cursor.execute(
                "UPDATE subidas_plataforma SET codigo_MLC = %s WHERE obra_id = %s",
                (codigo_mlc, cod_klaim)
            )
            print(f"Actualizado: cod_klaim = {cod_klaim}, codigo_mlc = {codigo_mlc}")
        else:
            # Si no existe, insertar un nuevo registro
            cursor.execute(
                """
                INSERT INTO subidas_plataforma (obra_id, codigo_MLC, estado_MLC, estado_ADREV, matching_tool)
                VALUES (%s, %s, 'OK', 'NO CARGADA', 0)
                """,
                (cod_klaim, codigo_mlc)
            )
            print(f"Insertado: cod_klaim = {cod_klaim}, codigo_mlc = {codigo_mlc}")
    except mysql.connector.Error as e:
        print(f"Error en cod_klaim = {cod_klaim}: {e}")

# Confirmar los cambios y cerrar la conexión
conn.commit()
cursor.close()
conn.close()

print("Proceso completado.")