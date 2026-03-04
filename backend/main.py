# Re-export app from app.main for convenient uvicorn command
from app.main import app

# This allows running: uvicorn main:app --reload
# from the backend directory
