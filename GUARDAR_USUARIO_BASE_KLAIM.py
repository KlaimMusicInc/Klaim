import os
from datetime import datetime

import mysql.connector
from mysql.connector import Error

# ==== 1) Cargar Django para usar sus hashers ====
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
import django

django.setup()
from django.contrib.auth.hashers import make_password

# ==== 2) Config MySQL ====
CONFIG = {
    "user": "root",  # <-- ajusta
    "password": "97072201144Ss.",  # <-- ajusta
    "host": "localhost",
    "database": "base_datos_klaim",  # <-- ajusta (dev/prod)
}

# ==== 3) Utilidades SQL ====
SQL_SELECT_USER = "SELECT id FROM auth_user WHERE username = %s"
SQL_INSERT_USER = """
INSERT INTO auth_user (
    password, last_login, is_superuser, username,
    last_name, email, is_staff, is_active, date_joined, first_name
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
SQL_SELECT_GROUP = "SELECT id FROM auth_group WHERE name = %s"
SQL_INSERT_GROUP = "INSERT INTO auth_group (name) VALUES (%s)"
SQL_INSERT_USER_GROUP = (
    "INSERT IGNORE INTO auth_user_groups (user_id, group_id) VALUES (%s, %s)"
)

ROLE_FLAGS = {
    "Administrador": {"is_staff": 1, "is_superuser": 1, "group": "Administrador"},
    "SuperStaff": {"is_staff": 1, "is_superuser": 0, "group": "SuperStaff"},
    "Staff": {"is_staff": 1, "is_superuser": 0, "group": "Staff"},
    "Cliente": {"is_staff": 0, "is_superuser": 0, "group": "Cliente"},
}


def get_group_id(cursor, name):
    cursor.execute(SQL_SELECT_GROUP, (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    # crear si no existe
    cursor.execute(SQL_INSERT_GROUP, (name,))
    return cursor.lastrowid


def crear_usuario(
    username, password, name="", email="", role="Cliente", is_active=True
):
    """
    Crea usuario en auth_user con hash de Django y lo asigna a su grupo.
    - role: 'Administrador' | 'SuperStaff' | 'Staff' | 'Cliente'
    """
    role = role if role in ROLE_FLAGS else "Cliente"
    flags = ROLE_FLAGS[role]

    try:
        conn = mysql.connector.connect(**CONFIG)
        cursor = conn.cursor()

        # ¿Existe ya?
        cursor.execute(SQL_SELECT_USER, (username,))
        row = cursor.fetchone()
        if row:
            print(f"[SKIP] '{username}' ya existe (id={row[0]}). No se creó.")
            return

        # Hash de Django (usa los hashers de tu settings)
        encoded = make_password(password)  # respeta PRIORIDAD de PASSWORD_HASHERS

        # Parsear nombre rápido -> first/last (opcional)
        first_name, last_name = "", ""
        if name:
            parts = name.strip().split(" ", 1)
            first_name = parts[0][:150]
            last_name = parts[1][:150] if len(parts) > 1 else ""

        # Insertar usuario
        data_user = (
            encoded,  # password
            None,  # last_login
            flags["is_superuser"],  # is_superuser
            username,  # username
            last_name,  # last_name (NOT NULL)
            email or "",  # email (NOT NULL)
            flags["is_staff"],  # is_staff
            1 if is_active else 0,  # is_active
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # date_joined (NOT NULL)
            first_name,  # first_name (NOT NULL)
        )
        cursor.execute(SQL_INSERT_USER, data_user)
        user_id = cursor.lastrowid

        # Asegurar grupo y asignarlo
        group_id = get_group_id(cursor, flags["group"])
        cursor.execute(SQL_INSERT_USER_GROUP, (user_id, group_id))

        conn.commit()
        print(
            f"[OK] Usuario '{username}' creado en auth_user con rol {role} (id={user_id})."
        )

    except Error as e:
        print("Error MySQL:", e)
        if conn and conn.is_connected():
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# ============================
# Ejemplos de uso:
# ============================

if __name__ == "__main__":
    # Cambia los ejemplos por los que necesites crear

    crear_usuario(
        "ADMINISTRADOR", "97072201144Ss.", name="David Cubillos", role="Administrador"
    )
    crear_usuario(
        "AlejandraCardona",
        "ACKlaim2025.",
        name="Maria Alejandra Cardona",
        role="Superstaff",
    )

    crear_usuario("Karinavence", "KKlaim2024.", name="Karina Vence", role="Superstaff")
    crear_usuario(
        "Alejandroromulo", "AKlaim2024.", name="Alejandro Romulo", role="Superstaff"
    )

    crear_usuario(
        "Andresotalora", "AFKlaim2024.", name="Andres Otalora", role="Superstaff"
    )

    crear_usuario(
        "Franciscoguerrero", "FKlaim2024.", name="Francisco Guerrero", role="Superstaff"
    )
    crear_usuario("Karencastillo", "KCKlaim2024.", name="Karen Castillo", role="Staff")
    crear_usuario(
        "Blancagutierrez", "BGKlaim2025.", name="Blanca Gutierrez", role="Staff"
    )
    crear_usuario(
        "Clienteprueba", "clienteprueba", name="cliente prueba", role="Cliente"
    )  # relacionar con cliente_id=3
    crear_usuario(
        "SAYCO",
        "COKlaim2025.",
        name="Sociedad de Autores y Compositores de Colombia",
        role="Cliente",
    )  # relacionar con cliente_id=1
    crear_usuario(
        "SAYCE",
        "CEKlaim2025,",
        name="Sociedad de Autores y Compositores de Ecuador",
        role="Cliente",
    )  # relacionar con cliente_id=2
    crear_usuario(
        "SACVEN",
        "VENKlaim2025#",
        name="Sociedad de Autores y Compositores de Venezuela",
        role="Cliente",
    )  # relacionar con cliente_id=4
