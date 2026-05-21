import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR / "salary_management"

sys.path.insert(0, str(PROJECT_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")

app = get_wsgi_application()
