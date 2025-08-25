#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import mysql.connector
from mysql.connector import errorcode
import bcrypt
from typing import Optional, Tuple

# ============== Usuarios a cargar ==============
USERS = [
    ("ADMINISTRADOR",     "97072201144Ss.", "David Cubillos",                                         "Administrador", None),
    ("AlejandraCardona",  "ACKlaim2025.",  "Maria Alejandra Cardona",                                 "Superstaff",    None),
    ("Karinavence",       "KAVKlaim2024.", "Karina Vence",                                            "Superstaff",    None),
    ("Alejandroromulo",   "ALRKlaim2024.", "Alejandro Romulo",                                        "Superstaff",    None),
    ("Andresotalora",     "AFKlaim2024.",  "Andres Otalora",                                          "Superstaff",    None),
    ("Franciscoguerrero", "FGKlaim2024.",  "Francisco Guerrero",                                      "Superstaff",    None),
    ("Karencastillo",     "KCKlaim2024.",  "Karen Castillo",                                          "Staff",         None),
    ("Blancagutierrez",   "BGKlaim2025.",  "Blanca Gutierrez",                                        "Staff",         None),

    # Clientes (IDs existentes en dev: 1 SAYCO, 2 SAYCE, 3 PRUEBA, 4 SACVEN)
    ("Clienteprueba",     "clienteprueba", "PRUEBA",                                                  "Cliente",       3),
    ("SAYCO",             "COKlaim2025.",  "SAYCO",                                                   "Cliente",       1),
    ("SAYCE",             "CEKlaim2025,",  "SAYCE",                                                   "Cliente",       2),
    ("SACVEN",            "VENKlaim2025#", "SACVEN",                                                  "Cliente",       4),
]

# ============== Perfiles por entorno ==============
DEFAULT_PROFILES = {
    "prod": {"user":"ADMINISTRADOR","password":"97072201144Ss.","host":"localhost","database":"base_datos_klaim","port":3306},
    "dev":  {"user":"ADMINISTRADOR","password":"97072201144Ss.","host":"localhost","database":"base_datos_klaim_dev","port":3306},
}

VALID_ROLES = {"Administrador", "Superstaff", "Staff", "Cliente"}
VALID_ALGOS = {"bcrypt_sha256", "bcrypt"}

# ============== Hashing compatible con Django ==============
def make_bcrypt_sha256(plain: str) -> str:
    pre = hashlib.sha256(plain.encode("utf-8")).hexdigest().encode("utf-8")
    b = bcrypt.hashpw(pre, bcrypt.gensalt())              # -> b'$2b$12$...'
    h = b.decode("utf-8").lstrip("$")                     # -> '2b$12$...'
    return "bcrypt_sha256$$" + h                          # -> 'bcrypt_sha256$$2b$12$...'

def make_bcrypt(plain: str) -> str:
    b = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    h = b.decode("utf-8").lstrip("$")
    return "bcrypt$$" + h                                 # -> 'bcrypt$$2b$12$...'


def hash_password(plain: str, algo: str) -> str:
    if algo == "bcrypt_sha256":
        return make_bcrypt_sha256(plain)
    elif algo == "bcrypt":
        return make_bcrypt(plain)
    raise ValueError(f"Algoritmo no soportado: {algo!r}")

# ============== Utilidades BD ==============
def split_name(fullname: str) -> Tuple[str, str]:
    fullname = (fullname or "").strip()
    if not fullname:
        return "", ""
    parts = fullname.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])

def ensure_group(cur, name: str) -> int:
    cur.execute("SELECT id FROM auth_group WHERE name=%s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO auth_group (name) VALUES (%s)", (name,))
    return cur.lastrowid

def resolve_cliente_id(cur, cliente_id: Optional[int], nombre_cliente_hint: Optional[str]) -> Optional[int]:
    if cliente_id is not None:
        cur.execute("SELECT id_cliente FROM clientes WHERE id_cliente=%s", (int(cliente_id),))
        row = cur.fetchone()
        return int(row[0]) if row else None
    if nombre_cliente_hint:
        cur.execute("SELECT id_cliente FROM clientes WHERE nombre_cliente=%s", (nombre_cliente_hint,))
        row = cur.fetchone()
        return int(row[0]) if row else None
    return None

def upsert_user(cur, username: str, password_plain: str, name: str,
                role: str, cliente_id: Optional[int], algo: str) -> None:
    if role not in VALID_ROLES:
        raise ValueError(f"Role inválido: {role!r}. Debe ser uno de {sorted(VALID_ROLES)}")

    first_name, last_name = split_name(name)
    encoded = hash_password(password_plain, algo)

    is_staff     = 1 if role in {"Administrador", "Superstaff", "Staff"} else 0
    is_superuser = 1 if role == "Administrador" else 0

    cur.execute("SELECT id FROM auth_user WHERE username=%s", (username,))
    row = cur.fetchone()
    if row:
        user_id = row[0]
        cur.execute("""
            UPDATE auth_user
               SET password=%s,
                   first_name=%s,
                   last_name=%s,
                   is_active=1,
                   is_staff=%s,
                   is_superuser=%s
             WHERE id=%s
        """, (encoded, first_name, last_name, is_staff, is_superuser, user_id))
        action = "actualizado"
    else:
        cur.execute("""
            INSERT INTO auth_user
                (password, username, first_name, last_name, email,
                 is_staff, is_active, is_superuser, date_joined)
            VALUES (%s, %s, %s, %s, %s, %s, 1, %s, NOW())
        """, (encoded, username, first_name, last_name, f"{username}@example.com",
              is_staff, is_superuser))
        user_id = cur.lastrowid
        action = "creado"

    group_id = ensure_group(cur, role)
    cur.execute("DELETE FROM auth_user_groups WHERE user_id=%s", (user_id,))
    cur.execute("INSERT INTO auth_user_groups (user_id, group_id) VALUES (%s, %s)", (user_id, group_id))

    if role == "Cliente":
        resolved_id = resolve_cliente_id(cur, cliente_id, name)
        if not resolved_id:
            cur.execute("SELECT id_cliente, nombre_cliente FROM clientes ORDER BY id_cliente")
            catalog = cur.fetchall()
            listado = ", ".join(f"{cid}:{nom}" for cid, nom in catalog) or "(sin registros)"
            print(f"⚠ No se pudo vincular cliente para {username}: "
                  f"cliente_id={cliente_id} no existe y nombre='{name}' no coincide. "
                  f"Clientes disponibles: {listado}")
        else:
            cur.execute("DELETE FROM cliente_account WHERE user_id=%s", (user_id,))
            cur.execute("""
                INSERT INTO cliente_account (user_id, cliente_id, creado)
                VALUES (%s, %s, NOW())
            """, (user_id, resolved_id))

    print(f"✔ Usuario {username} ({role}) {action} (id={user_id})")

# ============== Input interactivo para elegir la BD ==============
def interactive_pick_config(base_cfg: dict) -> dict:
    print("\nSelecciona a qué base de datos quieres insertar:")
    print("  1) prod  → base_datos_klaim")
    print("  2) dev   → base_datos_klaim_dev")
    print("  3) personalizar (ingresar parámetros manualmente)")
    choice = input("Opción [1/2/3]: ").strip() or "1"

    if choice == "1":
        cfg = base_cfg["prod"].copy()
    elif choice == "2":
        cfg = base_cfg["dev"].copy()
    else:
        cfg = {}
        cfg["host"]     = input("Host (localhost): ").strip() or "localhost"
        cfg["port"]     = int(input("Puerto (3306): ").strip() or "3306")
        cfg["user"]     = input("Usuario (ADMINISTRADOR): ").strip() or "ADMINISTRADOR"
        cfg["password"] = input("Password: ").strip()
        cfg["database"] = input("Base de datos: ").strip()

    print(f"\nVas a usar: {cfg['user']}@{cfg['host']}:{cfg['port']} DB={cfg['database']}")
    confirm = input("¿Confirmar? [S/n]: ").strip().lower()
    if confirm in ("", "s", "si", "sí"):
        return cfg
    else:
        print("Cancelado por el usuario.")
        raise SystemExit(0)

# ============== Main ==============
def main():
    ap = argparse.ArgumentParser(description="Seed de usuarios (auth_user) compatible con Django.")
    ap.add_argument("--env", choices=["prod", "dev"], default=None, help="Perfil predefinido de BD.")
    ap.add_argument("--db-name", default=None); ap.add_argument("--db-user", default=None)
    ap.add_argument("--db-pass", default=None); ap.add_argument("--db-host", default=None)
    ap.add_argument("--db-port", type=int, default=None)
    ap.add_argument("--algo", choices=list(VALID_ALGOS), default="bcrypt_sha256",
                   help="Algoritmo de hash. Default: bcrypt_sha256 (coincide con tu settings).")
    ap.add_argument("--reset", action="store_true", help="Trunca tablas de usuarios antes de sembrar (peligroso).")
    ap.add_argument("--no-interactive", action="store_true",
                   help="No preguntar por consola (usa --env o --db-*).")
    args = ap.parse_args()

    if args.no_interactive:
        cfg = (DEFAULT_PROFILES[args.env].copy() if args.env else DEFAULT_PROFILES["prod"].copy())
        if args.db_name: cfg["database"] = args.db_name
        if args.db_user: cfg["user"]     = args.db_user
        if args.db_pass: cfg["password"] = args.db_pass
        if args.db_host: cfg["host"]     = args.db_host
        if args.db_port: cfg["port"]     = args.db_port
        print(f"Conectando a {cfg['user']}@{cfg['host']}:{cfg['port']} DB={cfg['database']} | ALGO={args.algo}")
    else:
        cfg = interactive_pick_config(DEFAULT_PROFILES)

    try:
        conn = mysql.connector.connect(**cfg)
        cur = conn.cursor()

        if args.reset:
            print("⚠️  RESET: truncando tablas de usuarios...")
            cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
            for table in ("cliente_account","auth_user_groups","auth_user_user_permissions","auth_user"):
                cur.execute(f"TRUNCATE TABLE {table};")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1;")

        for username, password, name, role, cliente_id in USERS:
            upsert_user(cur, username, password, name, role, cliente_id, args.algo)

        conn.commit(); cur.close(); conn.close()
        print("✅ Proceso completado con éxito")

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR: print("❌ Credenciales de DB inválidas")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:      print("❌ La base de datos no existe")
        else:                                             print("❌ Error MySQL:", err)
    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    main()
