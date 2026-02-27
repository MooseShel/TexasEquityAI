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

# Set the Railway domain so rxconfig.py can bake the correct api_url into the frontend
ENV RAILWAY_PUBLIC_DOMAIN=texasequityai.up.railway.app

# Initialize Reflex and export static frontend
RUN reflex init
RUN reflex export --no-zip

# Copy Caddyfile (already in project root)
# Uses {$PORT} syntax for Caddy env var expansion

# Create startup script
RUN printf '#!/bin/bash\nset -e\necho "Starting Reflex backend on port 8001..."\nreflex run --env prod --backend-only --loglevel info --backend-host 0.0.0.0 --backend-port 8001 &\necho "Waiting for backend..."\nsleep 3\necho "Starting Caddy on port $PORT..."\ncaddy run --config /app/Caddyfile --adapter caddyfile\n' > /app/start.sh && chmod +x /app/start.sh

ENV PORT=8080

CMD ["/app/start.sh"]
