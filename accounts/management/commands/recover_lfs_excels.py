import os
import sys
import shutil
import subprocess
from datetime import datetime

# === AJUSTA RUTAS AQUÍ (si lo necesitas) ===
REPO_ROOT = r"C:\Users\USER\Documents\PORTATIL\FLASK_DJANGO_KLAIM\django_secure_app\myproject"
DATA_REL  = os.path.join("static", "data")
DATA_DIR  = os.path.join(REPO_ROOT, DATA_REL)

# Dónde dejar la copia “normal” en Documentos
DEST_BASE = r"C:\Users\USER\Documents"
DEST_DIR  = os.path.join(DEST_BASE, f"KLAIM_Data_Recovery_{datetime.now().strftime('%Y%m%d-%H%M%S')}")

def run(cmd, cwd=None):
    print(f"[RUN] {' '.join(cmd)}  (cwd={cwd or os.getcwd()})")
    try:
        out = subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.STDOUT, shell=False, text=True)
        print(out.strip())
        return 0
    except subprocess.CalledProcessError as e:
        print(e.output.strip())
        return e.returncode

def is_lfs_pointer(filepath):
    """
    Devuelve True si el archivo parece un puntero de Git LFS.
    Los punteros son archivos de texto con cabecera tipo:
        version https://git-lfs.github.com/spec/v1
        oid sha256:...
        size 123456
    """
    try:
        # Si pesa > 4KB probablemente ya es binario (heurística rápida)
        if os.path.getsize(filepath) > 4096:
            return False
        with open(filepath, "rb") as f:
            head = f.read(512)
        return b"git-lfs.github.com/spec/v1" in head
    except Exception:
        return False

def looks_like_real_xlsx(filepath):
    """
    XLSX es un ZIP: debe empezar con b'PK\x03\x04'
    """
    try:
        with open(filepath, "rb") as f:
            sig = f.read(4)
        return sig.startswith(b"PK\x03\x04")
    except Exception:
        return False

def main():
    # 0) Validaciones básicas
    if not os.path.isdir(REPO_ROOT):
        print(f"[ERROR] REPO_ROOT no existe: {REPO_ROOT}")
        sys.exit(1)
    if not os.path.isdir(DATA_DIR):
        print(f"[ERROR] No existe la carpeta de datos: {DATA_DIR}")
        sys.exit(1)

    # 1) git lfs install (por si no estaba inicializado)
    rc = run(["git", "lfs", "install"], cwd=REPO_ROOT)
    if rc != 0:
        print("[ADVERTENCIA] No se pudo ejecutar 'git lfs install'. Asegúrate de tener Git LFS instalado.")
        # seguimos, por si ya estaba instalado

    # 2) git lfs pull (descarga los binarios reales al working copy)
    rc = run(["git", "lfs", "pull"], cwd=REPO_ROOT)
    if rc != 0:
        print("[ERROR] Falló 'git lfs pull'. No se pueden recuperar los binarios.")
        sys.exit(2)

    # 3) Crear carpeta destino y copiar
    print(f"[INFO] Copiando '{DATA_DIR}' -> '{DEST_DIR}' ...")
    shutil.copytree(DATA_DIR, DEST_DIR)
    print("[OK] Copia completada.")

    # 4) Verificación: buscar punteros LFS residuales y .xlsx “reales”
    lfs_pointers = []
    xlsx_checks = []
    for root, _, files in os.walk(DEST_DIR):
        for name in files:
            path = os.path.join(root, name)
            lower = name.lower()
            if lower.endswith((".xlsx", ".xlsm", ".xlsb")):
                xlsx_checks.append((path, looks_like_real_xlsx(path)))
            else:
                # Heurística: si es muy pequeño y parece puntero
                if is_lfs_pointer(path):
                    lfs_pointers.append(path)

    # Reporte
    print("\n===== VERIFICACIÓN =====")
    if xlsx_checks:
        bad = [p for p, ok in xlsx_checks if not ok]
        print(f"XLSX verificados: {len(xlsx_checks)} archivos.")
        if bad:
            print("[ALERTA] Algunos .xlsx NO parecen binarios reales (¿siguen siendo punteros?):")
            for p in bad[:15]:
                print(" -", p)
            if len(bad) > 15:
                print(f" ... y {len(bad)-15} más")
        else:
            print("[OK] Todos los .xlsx parecen archivos válidos (firma ZIP detectada).")
    else:
        print("No se encontraron .xlsx en la copia.")

    if lfs_pointers:
        print(f"\n[ALERTA] Se detectaron {len(lfs_pointers)} archivos que aún parecen punteros LFS:")
        for p in lfs_pointers[:15]:
            print(" -", p)
        if len(lfs_pointers) > 15:
            print(f" ... y {len(lfs_pointers)-15} más")
        print("Sugerencia: vuelve a ejecutar 'git lfs pull' en el repo y repite la copia.")
    else:
        print("\n[OK] No se detectaron punteros LFS residuales en la copia.")

    print(f"\n[LISTO] Carpeta clon creada en: {DEST_DIR}")

if __name__ == "__main__":
    main()
