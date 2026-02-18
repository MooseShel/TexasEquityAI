FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install specific Playwright browsers (already in base image, but ensuring deps)
RUN playwright install chromium
RUN playwright install-deps

# Copy the rest of the application
COPY . .

# Expose the ports
# 7860 is the default port for Hugging Face Spaces
EXPOSE 7860
EXPOSE 8000

# Grant execution permission to the entrypoint script
RUN chmod +x run_app.sh

# Run the startup script
CMD ["./run_app.sh"]
