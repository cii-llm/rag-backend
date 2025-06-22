import uvicorn
import os

if __name__ == "__main__":
    # Get host and port from environment variables or use defaults
    host = os.getenv("HOST", "127.0.0.1") # This should be 0.0.0.0 for production
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() == "true" # Enable reload for development

    print(f"Starting Uvicorn server on {host}:{port} with reload={'enabled' if reload else 'disabled'}")
    uvicorn.run(
        "app.main:app", # Points to the FastAPI app instance in app/main.py
        host=host,
        port=port,
        reload=reload, # Automatically reload server on code changes (good for development)
        log_level="info"
    )