# RAG LLM for CII


> .env file
```
# --- OpenAI Configuration ---
OPENAI_API_KEY="your_api_key" # Replace with your actual key

# --- Application Configuration ---
# Directory containing the source documents (PDF, XLSX)
DATA_FOLDER="./data"
# Directory where ChromaDB will store its persistent data
PERSIST_DIR="./vector_store"
# Name for the ChromaDB collection
COLLECTION_NAME="doc_store_v1"
# OpenAI Model for Generation
LLM_MODEL="gpt-3.5-turbo" # or "gpt-4" if you have access
# OpenAI Embedding Model (or choose another like "text-embedding-3-small", etc.)
EMBEDDING_MODEL="text-embedding-ada-002"
```