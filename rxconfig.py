import reflex as rx
import sys
import os

import subprocess

# Add project root to sys.path so 'backend' is importable
# Now that rxconfig.py is in the root, project_root is the current directory
project_root = os.path.dirname(os.path.abspath(__file__))
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
        "outputs",
        "data",
    ]),
)



# Set api_url to localhost for local Windows dev so frontend can load backend images
# without Chrome rejecting the 0.0.0.0 binding. On Cloud, this is safely ignored.
config_kwargs = {
    "app_name": "texas_equity_ai",
    "disable_plugins": ["reflex.plugins.sitemap.SitemapPlugin"],
}

if sys.platform == "win32" and not os.environ.get("REFLEX_ENV_MODE"):
    config_kwargs["api_url"] = "http://127.0.0.1:8000"

config = rx.Config(**config_kwargs)

