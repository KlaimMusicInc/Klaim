"""
Carga un catálogo **solo de obras nuevas** y las añade al catálogo ACTIVO del
cliente indicado sin tocar las obras que ya están en la base.

– Python 3.10+  
– pandas, SQLAlchemy, mysql-connector-python, tkinter, unidecode

Columnas esperadas en el Excel  
--------------------------------------------------------
Título | Código ISWC | Código SGS | Número IP Autor | Nombre Autor
Tipo de Autor | Porcentaje Reclamado de Autor | Artistas
"""

from pathlib import Path
from datetime import date
from tkinter import Tk, filedialog

import pandas as pd
from unidecode import unidecode                  # ← necesario para validar duplicados
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection


# --------------------------------------------------------------------------- #
# 1) CONEXIÓN
# --------------------------------------------------------------------------- #
def connect() -> Connection:
    """Devuelve una conexión SQLAlchemy."""
    engine = create_engine(
        "mysql+mysqlconnector://ADMINISTRADOR:97072201144Ss.@localhost/base_datos_klaim_dev",
        pool_pre_ping=True,
    )
    return engine.connect()


# --------------------------------------------------------------------------- #
# 2) SELECCIÓN DE CLIENTE Y CATÁLOGO
# --------------------------------------------------------------------------- #
def get_cliente(conn: Connection) -> int:
    while True:
        id_cliente = input("ID del cliente: ").strip()
        row = conn.execute(
            text("SELECT 1 FROM clientes WHERE id_cliente = :id"),
            {"id": id_cliente},
        ).fetchone()
        if row:
            break
        print("❌  El ID no existe, inténtalo de nuevo.")
    return int(id_cliente)


def get_catalogo_activo(conn: Connection, id_cliente: int) -> int:
    row = conn.execute(
        text(
            """
            SELECT id_catalogo
            FROM Catalogos
            WHERE id_cliente = :id AND estado = 'Activo'
            """
        ),
        {"id": id_cliente},
    ).fetchone()
    if not row:
        raise RuntimeError(
            f"⚠️  El cliente {id_cliente} no tiene un catálogo activo."
        )
    return row[0]


# --------------------------------------------------------------------------- #
# 3) CARGA DEL EXCEL
# --------------------------------------------------------------------------- #
def pick_excel() -> pd.DataFrame:
    root = Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Seleccione el catálogo (Excel)",
        filetypes=[("Archivos Excel", "*.xlsx *.xls")],
    )
    if not path:
        raise SystemExit("🚫  No se seleccionó archivo.")

    df = pd.read_excel(path).fillna("")

    # Normalizar tipos
    df["Código SGS"] = pd.to_numeric(df["Código SGS"], errors="coerce").astype(int)
    df["Porcentaje Reclamado de Autor"] = pd.to_numeric(
        df["Porcentaje Reclamado de Autor"], errors="coerce"
    )

    return df


# --------------------------------------------------------------------------- #
# 4) FUNCIONES AUXILIARES DE INSERCIÓN
# --------------------------------------------------------------------------- #
def insert_obra(conn, titulo, sgs, iswc, catalogo_id) -> int:
    conn.execute(
        text(
            """
            INSERT INTO Obras (titulo, codigo_sgs, codigo_iswc, catalogo_id)
            VALUES (:t, :s, :i, :c)
            """
        ),
        {"t": titulo, "s": sgs, "i": iswc or None, "c": catalogo_id},
    )
    return conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()


def get_or_create_artista_unico(conn, nombre: str) -> int:
    """Devuelve el id_artista_unico; lo crea si no existe."""
    row = conn.execute(
        text(
            "SELECT id_artista_unico "
            "FROM artistas_unicos WHERE nombre_artista = :n"
        ),
        {"n": nombre},
    ).fetchone()
    if row:
        return row[0]

    conn.execute(
        text(
            "INSERT INTO artistas_unicos (nombre_artista) VALUES (:n)"
        ),
        {"n": nombre},
    )
    return conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()


def insert_artista(conn, nombre_artista: str, obra_id: int):
    """Inserta el artista y su vínculo con la obra."""
    artista_unico_id = get_or_create_artista_unico(conn, nombre_artista.strip())
    conn.execute(
        text(
            """
            INSERT INTO Artistas
            (nombre_artista, obra_id, id_artista_unico)
            VALUES (:nombre, :obra, :unico)
            """
        ),
        {"nombre": nombre_artista.strip(),
         "obra": obra_id,
         "unico": artista_unico_id},
    )


def get_or_create_autor(conn, nombre, ipi, tipo) -> int:
    row = conn.execute(
        text(
            """
            SELECT id_autor FROM AutoresUnicos
            WHERE nombre_autor = :n AND codigo_ipi = :i AND tipo_autor = :t
            """
        ),
        {"n": nombre, "i": ipi or None, "t": tipo},
    ).fetchone()
    if row:
        return row[0]

    conn.execute(
        text(
            """
            INSERT INTO AutoresUnicos (nombre_autor, codigo_ipi, tipo_autor)
            VALUES (:n, :i, :t)
            """
        ),
        {"n": nombre, "i": ipi or None, "t": tipo},
    )
    return conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()


def insert_obra_autor(conn, obra_id, autor_id, porcentaje):
    conn.execute(
        text(
            """
            INSERT INTO ObrasAutores (obra_id, autor_id, porcentaje_autor)
            VALUES (:o, :a, :p)
            """
        ),
        {"o": obra_id, "a": autor_id, "p": porcentaje},
    )


# --------------------------------------------------------------------------- #
# 5) PROCESO PRINCIPAL
# --------------------------------------------------------------------------- #
def main():
    with connect() as conn, conn.begin():  # transacción atómica
        id_cliente = get_cliente(conn)
        id_catalogo = get_catalogo_activo(conn, id_cliente)

        # SGS ya existentes en ese catálogo -> evitamos duplicados
        existentes = {
            int(r[0])
            for r in conn.execute(
                text(
                    """
                    SELECT codigo_sgs
                    FROM Obras
                    WHERE catalogo_id = :cat
                    """
                ),
                {"cat": id_catalogo},
            )
        }

        df = pick_excel()
        nuevos_sgs = sorted(set(df["Código SGS"]) - existentes)
        if not nuevos_sgs:
            print("✔️  No hay obras nuevas que insertar.")
            return

        for sgs in nuevos_sgs:
            obra_rows = df[df["Código SGS"] == sgs]

            # ── VALIDACIONES PREVIAS ───────────────────────────────────────
            nombres_norm = set()
            autores_filtrados = []
            suma_pct = 0.0

            for _, fila in obra_rows.iterrows():
                n_autor = str(fila["Nombre Autor"]).strip()
                pct     = fila["Porcentaje Reclamado de Autor"]
                t_autor = str(fila["Tipo de Autor"]).strip()

                if not n_autor or pd.isna(pct) or not t_autor:
                    # fila incompleta -> se ignora
                    continue

                nombre_norm = unidecode(n_autor.lower())

                # Autor duplicado en la misma obra
                if nombre_norm in nombres_norm:
                    print(
                        f"Autor duplicado '{n_autor}' en SGS {sgs} – se ignora el duplicado."
                    )
                    continue

                nombres_norm.add(nombre_norm)
                suma_pct += float(pct)
                autores_filtrados.append(fila)

            # exceso de porcentaje
            if suma_pct > 100.0 + 1e-6:
                print(
                    f"⚠️  Porcentajes ({suma_pct:.2f} %) > 100 % en SGS {sgs}. "
                    f"Obra NO registrada."
                )
                continue
            # ── FIN VALIDACIONES ───────────────────────────────────────────

            # --- inserta obra -------------------------------------------------
            first = obra_rows.iloc[0]
            obra_id = insert_obra(
                conn,
                first["Título"],
                sgs,
                first["Código ISWC"] or None,
                id_catalogo,
            )

            # --- inserta artistas -------------------------------------------
            for art in first["Artistas"].split(";"):
                if art.strip():
                    insert_artista(conn, art, obra_id)

            # --- inserta autores + vínculo -----------------------------------
            for fila in autores_filtrados:
                autor_id = get_or_create_autor(
                    conn,
                    str(fila["Nombre Autor"]).strip(),
                    fila["Número IP Autor"] or None,
                    str(fila["Tipo de Autor"]).strip(),
                )
                insert_obra_autor(
                    conn,
                    obra_id,
                    autor_id,
                    float(fila["Porcentaje Reclamado de Autor"]),
                )

        print(f"🎉  Obras nuevas insertadas: {len(nuevos_sgs)}")


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()
