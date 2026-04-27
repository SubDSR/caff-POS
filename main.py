from __future__ import annotations

import os
import logging
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

from pos_system.runtime import ensure_data_dir


APP_TITLE = "Caff POS"
HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 30


def _configure_logging() -> None:
    log_dir = ensure_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "desktop.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
        force=True,
    )


def _show_error(message: str) -> None:
    logging.exception(message)

    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
        return

    print(message, file=sys.stderr)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _resolve_port() -> int:
    configured_port = os.environ.get("POS_SERVER_PORT", "").strip()
    if configured_port:
        return int(configured_port)
    return _find_free_port()


def _prepare_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_system.settings")
    os.environ.setdefault("POS_DESKTOP_MODE", "True")
    os.environ.setdefault("DJANGO_DEBUG", "False")

    import django
    from django.core.management import call_command

    logging.info("Inicializando Django en modo escritorio")
    django_setup_started_at = time.perf_counter()
    django.setup()
    logging.info("Django configurado en %.2fs", time.perf_counter() - django_setup_started_at)

    migrate_started_at = time.perf_counter()
    call_command("migrate", interactive=False, run_syncdb=True, verbosity=0)
    logging.info("Migraciones verificadas en %.2fs", time.perf_counter() - migrate_started_at)


def _run_server(port: int) -> None:
    from waitress import serve

    logging.info("Iniciando Waitress en %s:%s", HOST, port)

    from pos_system.wsgi import application

    serve(application, host=HOST, port=port, threads=8)


def _wait_for_server(url: str) -> None:
    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(0.25)

    raise RuntimeError(f"No se pudo iniciar el servidor embebido en {url}: {last_error}")


def main() -> None:
    try:
        startup_started_at = time.perf_counter()
        _configure_logging()
        _prepare_django()

        port = _resolve_port()
        url = f"http://{HOST}:{port}/"
        healthcheck_url = f"http://{HOST}:{port}/health/"

        server_thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
        server_thread.start()
        _wait_for_server(healthcheck_url)
        logging.info(
            "Servidor listo en %.2fs, abriendo ventana en %s",
            time.perf_counter() - startup_started_at,
            url,
        )

        import webview

        webview.create_window(APP_TITLE, url, width=1440, height=900, min_size=(1024, 720))
        webview.start()
    except Exception as exc:  # pragma: no cover - startup dialog for packaged app
        _show_error(str(exc))
        raise


if __name__ == "__main__":
    main()
