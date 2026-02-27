import os
import sys
from pathlib import Path

from config.env import load_dotenv_if_exists

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "apps"))


from django.core.asgi import get_asgi_application

load_dotenv_if_exists(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()
