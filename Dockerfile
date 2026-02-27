FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Install Node.js, unzip (for bun), and Caddy (reverse proxy)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs unzip debian-keyring debian-archive-keyring apt-transport-https curl && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list && \
    apt-get update && apt-get install -y caddy && \
    npm install -g npm@latest

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium
RUN playwright install chromium && playwright install-deps chromium

# Copy the application
COPY . .

# Initialize Reflex and export static frontend
RUN reflex init
RUN reflex export --no-zip

# Create Caddyfile that serves frontend static files + proxies backend
RUN echo ':${PORT}\n\
    \n\
    # API and WebSocket routes -> Reflex backend\n\
    handle /ping {\n\
    reverse_proxy localhost:8001\n\
    }\n\
    handle /_event {\n\
    reverse_proxy localhost:8001\n\
    }\n\
    handle /_upload {\n\
    reverse_proxy localhost:8001\n\
    }\n\
    handle /_upload/* {\n\
    reverse_proxy localhost:8001\n\
    }\n\
    handle /api/* {\n\
    reverse_proxy localhost:8001\n\
    }\n\
    \n\
    # Everything else -> static frontend\n\
    handle {\n\
    root * /app/.web/_static\n\
    try_files {path} {path}.html /index.html\n\
    file_server\n\
    }\n\
    ' > /app/Caddyfile

# Create startup script
RUN echo '#!/bin/bash\n\
    set -e\n\
    \n\
    echo "Starting Reflex backend on port 8001..."\n\
    reflex run --env prod --backend-only --loglevel info --backend-host 0.0.0.0 --backend-port 8001 &\n\
    \n\
    echo "Waiting for backend..."\n\
    sleep 3\n\
    \n\
    echo "Starting Caddy reverse proxy on port $PORT..."\n\
    caddy run --config /app/Caddyfile --adapter caddyfile\n\
    ' > /app/start.sh && chmod +x /app/start.sh

ENV PORT=8080

CMD ["/app/start.sh"]
