#!/usr/bin/env python3
"""
Sincroniza los estados de conflicto entre conflictos_plataforma y subidas_plataforma
• Si plataforma = 'ADREV'  → estado_ADREV = 'Conflicto'
• Si plataforma = 'MLC'    → estado_MLC   = 'Conflicto'
"""

import mysql.connector
from mysql.connector import errorcode

mysql_config = {
    "host": "localhost",
    "user": "root",
    "password": "97072201144Ss.",
    "database": "base_datos_klaim",
    "autocommit": False,
}


def main():
    try:
        cnx = mysql.connector.connect(**mysql_config)
        cursor = cnx.cursor()

        # ———————————————————— UPDATE con CASE (una sola pasada) ——————————————————— #
        update_sql = """
            UPDATE subidas_plataforma AS sp
            INNER JOIN conflictos_plataforma AS cp
                    ON sp.obra_id = cp.obra_id
            SET
                sp.estado_ADREV = CASE
                                     WHEN cp.plataforma = 'ADREV' THEN 'Conflicto'
                                     ELSE sp.estado_ADREV
                                   END,
                sp.estado_MLC   = CASE
                                     WHEN cp.plataforma = 'MLC'   THEN 'Conflicto'
                                     ELSE sp.estado_MLC
                                   END
            WHERE cp.plataforma IN ('ADREV', 'MLC');
        """
        cursor.execute(update_sql)
        cnx.commit()
        print(f"Filas afectadas: {cursor.rowcount}")

        # ————————————————— OPCIÓN 2: dos sentencias simples (descomenta si prefieres) ——————— #
        """
        # ADREV
        cursor.execute(
            \"\"\"UPDATE subidas_plataforma AS sp
                 JOIN conflictos_plataforma AS cp
                   ON sp.obra_id = cp.obra_id
                 SET sp.estado_ADREV = 'Conflicto'
                 WHERE cp.plataforma = 'ADREV'\"\"\")
        # MLC
        cursor.execute(
            \"\"\"UPDATE subidas_plataforma AS sp
                 JOIN conflictos_plataforma AS cp
                   ON sp.obra_id = cp.obra_id
                 SET sp.estado_MLC = 'Conflicto'
                 WHERE cp.plataforma = 'MLC'\"\"\")
        cnx.commit()
        print(f"Filas afectadas (ADREV + MLC): {cursor.rowcount}")
        """

    except mysql.connector.Error as err:
        if cnx.is_connected():
            cnx.rollback()
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Credenciales MySQL incorrectas.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("La base de datos no existe.")
        else:
            print(err)
    finally:
        if cnx.is_connected():
            cursor.close()
            cnx.close()


if __name__ == "__main__":
    main()
