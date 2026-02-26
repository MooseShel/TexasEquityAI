FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Install Node.js (required by Reflex for frontend compilation)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npm@latest

# Copy and install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium && playwright install-deps chromium

# Copy the entire application
COPY . .

# Initialize Reflex and compile production frontend
RUN reflex init
RUN reflex export --no-zip

# Railway sets $PORT dynamically (usually 443 behind their proxy)
ENV PORT=8000

# Single command: run Reflex in production mode
CMD reflex run --env prod --backend-host 0.0.0.0 --backend-port $PORT
