#!/bin/bash

# Start the Backend (FastAPI) in the background
# We bind to 0.0.0.0 so it's accessible locally within the container
echo "Starting Backend API..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# Wait a few seconds for the backend to spin up
sleep 5

# Start the Frontend (Streamlit)
# Streamlit runs on port 7860 (Hugging Face's expected public port)
echo "Starting Frontend Dashboard..."
streamlit run frontend/app.py --server.port 7860 --server.address 0.0.0.0
