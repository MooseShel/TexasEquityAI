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

def install_playwright_browsers():
    """Installs Playwright browsers automatically on the server."""
    print("Installing Playwright browsers...")
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("Playwright browsers installed successfully.")
    except Exception as e:
        print(f"Failed to install Playwright browsers: {e}")

# Install browsers at startup (on cloud only)
if os.environ.get("REFLEX_ENV_MODE") or not os.path.exists(os.path.join(project_root, ".env")):
    install_playwright_browsers()

config = rx.Config(
    app_name="texas_equity_ai",
)

