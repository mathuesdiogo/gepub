import os
import sys
import atexit
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from config.env import load_dotenv_if_exists

BASE_DIR = Path(__file__).resolve().parent
_NEXT_PROCESS = None
_NEXT_LOG_FILE = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on"}


def _is_tcp_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _cleanup_next_process() -> None:
    global _NEXT_PROCESS, _NEXT_LOG_FILE
    proc = _NEXT_PROCESS
    _NEXT_PROCESS = None
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    if _NEXT_LOG_FILE is not None:
        try:
            _NEXT_LOG_FILE.close()
        except Exception:
            pass
        _NEXT_LOG_FILE = None


def _autostart_next_for_runserver() -> None:
    global _NEXT_PROCESS, _NEXT_LOG_FILE

    if len(sys.argv) < 2 or sys.argv[1] != "runserver":
        return

    if os.getenv("RUN_MAIN") == "true":
        return

    if not _env_bool("DJANGO_DEBUG", default=False):
        return

    if not _env_bool("GEPUB_INSTITUCIONAL_NEXT_ENABLED", default=True):
        return

    if not _env_bool("GEPUB_AUTOSTART_NEXT_ON_RUNSERVER", default=True):
        return

    next_url = (os.getenv("GEPUB_INSTITUCIONAL_NEXT_URL", "") or "").strip()
    if not next_url and _env_bool("DJANGO_DEBUG", default=False):
        next_url = "http://127.0.0.1:3000"
    if not next_url:
        return

    parsed = urlparse(next_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 3000

    if host not in {"127.0.0.1", "localhost", "::1"}:
        return

    if _is_tcp_open(host, port):
        print(f"[institucional] Next.js já ativo em {host}:{port}.")
        return

    if shutil.which("npm") is None:
        print("[institucional] npm não encontrado no PATH; autostart do Next.js desativado.")
        return

    web_dir = BASE_DIR / "web"
    if not web_dir.exists():
        print(f"[institucional] pasta do Next não encontrada em {web_dir}.")
        return

    log_path = Path("/tmp/gepub-next-autostart.log")
    _NEXT_LOG_FILE = open(log_path, "ab")

    print(f"[institucional] iniciando Next.js automático em {host}:{port}...")
    _NEXT_PROCESS = subprocess.Popen(
        ["npm", "run", "dev", "--", "-p", str(port), "-H", host],
        cwd=str(web_dir),
        stdout=_NEXT_LOG_FILE,
        stderr=subprocess.STDOUT,
    )
    atexit.register(_cleanup_next_process)

    deadline = time.time() + 25
    while time.time() < deadline:
        if _NEXT_PROCESS.poll() is not None:
            print(f"[institucional] Next.js encerrou ao iniciar. Veja: {log_path}")
            _cleanup_next_process()
            return
        if _is_tcp_open(host, port):
            print(f"[institucional] Next.js pronto em {host}:{port}.")
            return
        time.sleep(0.35)

    print(f"[institucional] Next.js ainda não respondeu. Verifique: {log_path}")

def main():
    load_dotenv_if_exists(BASE_DIR)
    _autostart_next_for_runserver()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
