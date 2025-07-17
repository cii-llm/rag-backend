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


## Build Virtualenv
```
virtualenv env
source ./env/bin/activate
pip3 install -r requirements.txt
```

## Running RAG LLM

```
      
screen -S rag_backend

source env/bin/activate
python run.py >> backend.log 2>&1
```

Detach from the screen Session:
    Press Ctrl+A, then release the keys, and then press d (for detach).
    You will see [detached from ... .rag_backend] and be returned to your normal shell prompt. The run.py process continues running inside the detached screen session. You can now safely disconnect your SSH session.

How to Manage the Session and Logs:

List Running screen Sessions:

`screen -ls`

You should see your session listed, e.g., ... .rag_backend (Detached).

Reattach to the Session:

`screen -r rag_backend`

(If you only have one detached session, screen -r might be enough). You'll be back inside the screen where the process is running.

Stop the Backend Process:

Reattach to the session: `screen -r rag_backend`

Press Ctrl+C to send an interrupt signal to the running Python process (Uvicorn should catch this and shut down gracefully).

Once the process stops, you can type exit and press Enter to terminate the screen session itself.

Kill the Session (if reattaching and Ctrl+C doesn't work):
      
`screen -X -S rag_backend quit`

    
### API
Preprocess
`curl -X POST -H "Content-Type: application/json" -d "{}" http://localhost:8000/preprocess`

Query
`curl -X POST -H "Content-Type: application/json" -d '{"query": "What is CII?"}' http://localhost:8000/query`

## Git Configuration

This repository is configured to push to both GitHub and UT Austin remotes simultaneously.

### Current Remote Setup
- **UT Austin**: `git@github.austin.utexas.edu:kk33964/cii-llm-backend.git`
- **GitHub**: `git@github.com:yourusername/cii-llm-backend.git` (update with actual URL)

### Push to Both Remotes
When you run `git push`, it will push to both remotes automatically:
```bash
git push
```

### Individual Remote Operations
If you need to push to a specific remote:
```bash
git push github main    # Push to GitHub only
git push ut main        # Push to UT Austin only (if configured as separate remote)
```

### Verify Remote Configuration
```bash
git remote -v
```

### Update GitHub URL
Replace the placeholder GitHub URL with your actual repository:
```bash
git remote set-url github git@github.com:yourusername/cii-llm-backend.git
```