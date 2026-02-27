FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Install Node.js and system utils required by Reflex (bun needs unzip)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs unzip && \
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

ENV PORT=8000

# Reflex prod mode serves both compiled frontend + API on the backend port
CMD reflex run --env prod --loglevel debug --backend-host 0.0.0.0 --backend-port $PORT
