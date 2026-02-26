import reflex as rx
import sys
import os

# Add project root to sys.path so 'backend' is importable
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables from the project root .env
from dotenv import load_dotenv
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path, override=False)

# Exclude data/outputs dirs from hot-reload to prevent worker restarts
# when files are written during protest generation
os.environ.setdefault(
    "REFLEX_HOT_RELOAD_EXCLUDE_PATHS",
    ":".join([
        "outputs",
        "data",
    ]),
)

# Determine the correct api_url for the deployment environment
api_url = None
if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    # Railway deployment: use the public domain Railway assigns
    api_url = f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
elif sys.platform == "win32":
    # Local Windows dev: Chrome rejects 0.0.0.0, use localhost
    api_url = "http://127.0.0.1:8000"

config_kwargs = {
    "app_name": "texas_equity_ai",
    "disable_plugins": ["reflex.plugins.sitemap.SitemapPlugin"],
}
if api_url:
    config_kwargs["api_url"] = api_url

config = rx.Config(**config_kwargs)
