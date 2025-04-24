import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file located in the parent directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# --- Required Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

# --- Application Settings ---
# Use absolute paths for robustness
BASE_DIR = Path(__file__).parent.parent.resolve()
DATA_FOLDER = BASE_DIR / os.getenv("DATA_FOLDER", "data")
PERSIST_DIR = BASE_DIR / os.getenv("PERSIST_DIR", "vector_store")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "doc_store_v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

# Ensure data and persist directories exist
DATA_FOLDER.mkdir(parents=True, exist_ok=True)
PERSIST_DIR.mkdir(parents=True, exist_ok=True)

print(f"--- Configuration ---")
print(f"Data Folder: {DATA_FOLDER}")
print(f"Persist Directory: {PERSIST_DIR}")
print(f"Collection Name: {COLLECTION_NAME}")
print(f"LLM Model: {LLM_MODEL}")
print(f"Embedding Model: {EMBEDDING_MODEL}")
print(f"---------------------")