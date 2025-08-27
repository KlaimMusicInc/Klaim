# settings.py — ÚNICO para DEV y PROD (carga auto según .env)
import os
from pathlib import Path
from datetime import timedelta
import environ

# --------------------------------------------------------------------------------------
# RUTAS BASE
# --------------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------------------
# ENV: autoselección .env ( .env.<DJANGO_ENV> -> .env )
# --------------------------------------------------------------------------------------
env = environ.Env(DEBUG=(bool, False))
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").lower()

for candidate in (
    os.path.join(BASE_DIR, f".env.{DJANGO_ENV}"),
    os.path.join(BASE_DIR, ".env"),
):
    if os.path.exists(candidate):
        environ.Env.read_env(candidate)
        break

# --------------------------------------------------------------------------------------
# CORE DJANGO
# --------------------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="America/Bogota")
USE_TZ = env.bool("USE_TZ", default=True)
USE_I18N = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------------------
# APPS
# --------------------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "accounts",

    # Seguridad
    "axes",
]

# (Opcional) django-extensions solo en DEV (o si lo activas por .env)
if env.bool("USE_DJANGO_EXTENSIONS", default=DEBUG):
    INSTALLED_APPS.append("django_extensions")

# --------------------------------------------------------------------------------------
# MIDDLEWARE
# --------------------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]

# WhiteNoise opcional (recomendado en PROD)
USE_WHITENOISE = env.bool("USE_WHITENOISE", default=not DEBUG)
if USE_WHITENOISE:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")

MIDDLEWARE += [
    "axes.middleware.AxesMiddleware",  # anti fuerza-bruta
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "myproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myproject.wsgi.application"

# --------------------------------------------------------------------------------------
# BASE DE DATOS (desde .env)
# --------------------------------------------------------------------------------------
# Persistencia de conexiones (0 en DEV, 60s en PROD por defecto)
CONN_MAX_AGE = env.int("DB_CONN_MAX_AGE", default=(0 if DEBUG else 60))

DATABASES = {
    "default": {
        "ENGINE": env("DB_ENGINE", default="django.db.backends.mysql"),
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="3306"),
        "CONN_MAX_AGE": CONN_MAX_AGE,
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# --------------------------------------------------------------------------------------
# AUTENTICACIÓN / HASHERS / VALIDADORES
# --------------------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.BCryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# En PROD queremos fail_safe=False; en DEV puede ser True
PWNED_FAIL_SAFE = env.bool("PWNED_FAIL_SAFE", default=DEBUG)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {
        "NAME": "pwned_passwords_django.validators.PwnedPasswordsValidator",
        # Sin OPTIONS: usamos la configuración por defecto del paquete
    },
]



PASSWORD_RESET_TIMEOUT = 60 * 60  # 1 hora

# --------------------------------------------------------------------------------------
# STATIC FILES
# --------------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Storage de WhiteNoise solo cuando se usa (normalmente en PROD)
if USE_WHITENOISE:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

STATEMENTS_DATA_ROOT = Path(
    env("STATEMENTS_DATA_ROOT", default=str(BASE_DIR / "static" / "data"))
).resolve()

# --------------------------------------------------------------------------------------
# SESIONES
# --------------------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 2 semanas
SESSION_SAVE_EVERY_REQUEST = True

# --------------------------------------------------------------------------------------
# EMAIL (SMTP) — desde .env
# --------------------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)  # NEW
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER or "webmaster@localhost")  # NEW
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)  # NEW

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# --------------------------------------------------------------------------------------
# django-axes
# --------------------------------------------------------------------------------------
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_RESET_ON_SUCCESS = True
# AXES_USE_USER_AGENT = True

# --------------------------------------------------------------------------------------
# SECURITY: cookies y cabeceras (toggles por .env)
# --------------------------------------------------------------------------------------
# Cookies seguras: por defecto False en DEBUG, True en PROD (cuando tengas HTTPS)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE    = env.bool("CSRF_COOKIE_SECURE",   default=not DEBUG)

# Samesite protege contra CSRF entre sitios
SESSION_COOKIE_SAMESITE = env.str("SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE    = env.str("CSRF_COOKIE_SAMESITE",    default="Lax")

# Si tus formularios son 100% server-rendered puedes poner True en PROD;
# si usas JS para leer la cookie CSRF, déjalo False.
CSRF_COOKIE_HTTPONLY = env.bool("CSRF_COOKIE_HTTPONLY", default=False)

# Cabeceras recomendadas
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = env.str("SECURE_REFERRER_POLICY", default="same-origin")
X_FRAME_OPTIONS = "DENY"  # evita clickjacking

# HTTPS / HSTS (actívalo en PROD cuando tengas TLS)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)  # ej. 31536000 en PROD
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

# Detrás de proxy que termina TLS (Nginx/Caddy/Traefik)
if env.bool("USE_SECURE_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=False)

# --------------------------------------------------------------------------------------
# LOGGING: seguridad y auth a consola
# --------------------------------------------------------------------------------------
LOG_LEVEL = env.str("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        "django.security": {"handlers": ["console"], "level": LOG_LEVEL},
        "django.request":  {"handlers": ["console"], "level": "WARNING"},
        "axes":            {"handlers": ["console"], "level": "INFO"},
    },
}
