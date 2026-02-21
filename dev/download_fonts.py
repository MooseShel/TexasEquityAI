import os
import urllib.request
import zipfile
import io
import logging
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FONT_SOURCES = {
    "Roboto": "https://github.com/googlefonts/roboto/releases/download/v2.138/roboto-unhinted.zip",
    "Montserrat": "https://github.com/JulietaUla/Montserrat/archive/refs/heads/master.zip"
}

def download_fonts():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    fonts_dir = os.path.join(backend_dir, "fonts")
    
    os.makedirs(fonts_dir, exist_ok=True)
    logger.info(f"Target fonts directory: {fonts_dir}")

    for family, url in FONT_SOURCES.items():
        logger.info(f"Downloading {family} from {url}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with zipfile.ZipFile(io.BytesIO(response.read())) as z:
                    for filename in z.namelist():
                        if filename.endswith(".ttf") and not filename.startswith("__MACOSX"):
                            target_filename = os.path.basename(filename)
                            # Only extract standard widths/weights to save space
                            if "Italic" in target_filename or "Regular" in target_filename or "Bold" in target_filename:
                                target_filepath = os.path.join(fonts_dir, target_filename)
                                logger.info(f"Extracting {target_filename}...")
                                with open(target_filepath, 'wb') as f_out:
                                    f_out.write(z.read(filename))
            logger.info(f"Successfully downloaded {family}")
        except Exception as e:
            logger.error(f"Failed to download {family}: {e}")

if __name__ == "__main__":
    download_fonts()
