import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import dj_database_url

from .runtime import ensure_data_dir, get_bundle_dir, is_desktop_mode, is_frozen, load_env_files


load_env_files()


BASE_DIR = get_bundle_dir()
DATA_DIR = ensure_data_dir()
DESKTOP_MODE = is_desktop_mode()
FROZEN_APP = is_frozen()

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG or DESKTOP_MODE or FROZEN_APP:
        SECRET_KEY = "django-insecure-pos-system-universidad"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=False")


def _split_env_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver", "caff-pos-production.up.railway.app"]
ALLOWED_HOSTS += _split_env_list(os.environ.get("DJANGO_ALLOWED_HOSTS", ""))

railway_public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_public_domain:
    ALLOWED_HOSTS.append(railway_public_domain)

ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))

CSRF_TRUSTED_ORIGINS = _split_env_list(os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", ""))
if railway_public_domain:
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_public_domain}")

CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "cafeteria",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if not DEBUG or DESKTOP_MODE or FROZEN_APP:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "pos_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            template_dir
            for template_dir in (BASE_DIR / "cafeteria" / "templates",)
            if Path(template_dir).exists()
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pos_system.wsgi.application"
ASGI_APPLICATION = "pos_system.asgi.application"

DATABASE_PATH = DATA_DIR / "db.sqlite3"
DEFAULT_DATABASE_URL = f"sqlite:///{DATABASE_PATH.resolve().as_posix()}"

if DESKTOP_MODE or FROZEN_APP:
    os.environ["DATABASE_URL"] = DEFAULT_DATABASE_URL

DATABASES = {
    "default": dj_database_url.config(
        default=DEFAULT_DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}


def _mysql_settings_from_url() -> dict[str, str | int] | None:
    for env_name in ("MYSQL_PUBLIC_URL", "MYSQL_URL"):
        raw_url = os.environ.get(env_name, "").strip()
        if not raw_url:
            continue

        parsed_url = urlparse(raw_url)
        if parsed_url.scheme != "mysql":
            raise RuntimeError(f"{env_name} must use the mysql:// scheme")

        database_name = parsed_url.path.lstrip("/")
        if not parsed_url.hostname or not parsed_url.username or not database_name:
            raise RuntimeError(f"{env_name} is missing required MySQL connection data")

        return {
            "host": parsed_url.hostname,
            "port": int(parsed_url.port or 3306),
            "user": unquote(parsed_url.username),
            "password": unquote(parsed_url.password or ""),
            "database": unquote(database_name),
        }

    return None


def _missing_mysql_config_message() -> str:
    app_env_path = DATA_DIR / ".env"
    return (
        "Missing MySQL configuration. Define MYSQL_PUBLIC_URL or MYSQL_URL, or set MYSQL_HOST, "
        "MYSQL_USER and MYSQL_DATABASE (optionally MYSQL_PORT and MYSQL_PASSWORD). "
        f"For the desktop .exe, place a .env file at {app_env_path} or configure Windows environment variables."
    )


def _mysql_settings_from_env() -> dict[str, str | int]:
    mysql_url_settings = _mysql_settings_from_url()
    if mysql_url_settings:
        return mysql_url_settings

    host = os.environ.get("MYSQL_HOST", "").strip()
    port = os.environ.get("MYSQL_PORT", "3306").strip() or "3306"
    user = os.environ.get("MYSQL_USER", "").strip()
    password = os.environ.get("MYSQL_PASSWORD", "")
    database = os.environ.get("MYSQL_DATABASE", "").strip()

    if not any((host, user, password, database, os.environ.get("MYSQL_PORT", "").strip())):
        raise RuntimeError(_missing_mysql_config_message())

    missing_fields = []
    if not host:
        missing_fields.append("MYSQL_HOST")
    if not user:
        missing_fields.append("MYSQL_USER")
    if not database:
        missing_fields.append("MYSQL_DATABASE")

    if missing_fields:
        missing_fields_text = ", ".join(missing_fields)
        raise RuntimeError(f"Missing required MySQL settings: {missing_fields_text}. {_missing_mysql_config_message()}")

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
    }


mysql_settings = _mysql_settings_from_env()

MYSQL_HOST = str(mysql_settings["host"])
MYSQL_PORT = int(mysql_settings["port"])
MYSQL_USER = str(mysql_settings["user"])
MYSQL_PASSWORD = str(mysql_settings["password"])
MYSQL_DATABASE = str(mysql_settings["database"])
MYSQL_CONNECT_TIMEOUT = int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "5"))
MYSQL_READ_TIMEOUT = int(os.environ.get("MYSQL_READ_TIMEOUT", "15"))
MYSQL_WRITE_TIMEOUT = int(os.environ.get("MYSQL_WRITE_TIMEOUT", "15"))

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if not DEBUG or DESKTOP_MODE or FROZEN_APP:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

if not DEBUG and not DESKTOP_MODE and not FROZEN_APP:
    SECURE_HSTS_SECONDS = 3600
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

if not DESKTOP_MODE and not FROZEN_APP:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
