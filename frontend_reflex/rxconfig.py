import reflex as rx
import sys
import os

# Add project root to sys.path so 'backend' is importable
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables from the project root .env
from dotenv import load_dotenv
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path, override=False)

# Exclude data/outputs dirs from hot-reload to prevent worker restarts
# when files are written during protest generation
# Use relative paths and colon separator because Reflex splits on ':' exactly
os.environ.setdefault(
    "REFLEX_HOT_RELOAD_EXCLUDE_PATHS",
    ":".join([
        "../outputs",
        "data",
        "outputs",
    ]),
)

config = rx.Config(
    app_name="texas_equity_ai",
    frontend_port=3000,
    backend_port=8001,
)
