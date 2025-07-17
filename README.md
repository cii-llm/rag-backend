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

## Batch Processing Documents with Product Names

This system supports batch processing of documents with product names and URLs from a CSV file. This is useful for processing large numbers of documents with proper metadata.

### 📁 File Structure

```
rag-backend/
├── batch_process_csv.py           # Main batch processing script
├── update_document_metadata.py    # Update existing documents script
├── cii-urls.csv                   # CSV file with product data
└── cii-pdfs/                      # Folder with PDF files
    ├── 272_11.pdf
    └── 272_12.pdf
```

### 📋 CSV File Format

Create a `cii-urls.csv` file with the following structure:

```csv
Product Name,eCopyfile,CII Website URL
Advanced Work Packaging Implementation Guide,272_12.pdf,https://www.construction-institute.org/resources/knowledgebase/best-practices/advanced-work-packaging-implementation-guide
Project Definition Rating Index,272_11.pdf,https://www.construction-institute.org/resources/knowledgebase/best-practices/project-definition-rating-index
```

### 🚀 Batch Processing Scripts

#### 1. Process New Documents from CSV

```bash
cd /Users/krishna/dev/cii/rag-backend
source env/bin/activate

# Process first 2 rows from CSV (for testing)
python batch_process_csv.py --limit 2

# Process all rows
python batch_process_csv.py

# Use custom CSV file
python batch_process_csv.py --csv-file custom-urls.csv
```

#### 2. Update Existing Documents with Product Names

```bash
cd /Users/krishna/dev/cii/rag-backend
source env/bin/activate

# Update metadata for first 2 documents
python update_document_metadata.py --limit 2

# Update all documents
python update_document_metadata.py

# Use custom CSV file
python update_document_metadata.py --csv-file custom-urls.csv
```

### 🔧 Script Options

#### batch_process_csv.py Options:
- `--limit N` - Process only first N rows from CSV
- `--csv-file path` - Use different CSV file (default: cii-urls.csv)
- `--collection name` - Use different ChromaDB collection

#### update_document_metadata.py Options:
- `--limit N` - Process only first N rows from CSV
- `--csv-file path` - Use different CSV file (default: cii-urls.csv)
- `--collection name` - Use different ChromaDB collection

### 📝 Usage Workflow

1. **Prepare your files:**
   - Add PDF files to the `cii-pdfs/` folder
   - Create/update `cii-urls.csv` with product information

2. **For new documents:**
   ```bash
   python batch_process_csv.py --limit 2  # Test with first 2 rows
   ```

3. **For existing documents (add product names):**
   ```bash
   python update_document_metadata.py --limit 2  # Test with first 2 rows
   ```

4. **Process all documents:**
   ```bash
   python batch_process_csv.py           # Process all new documents
   python update_document_metadata.py    # Update all existing documents
   ```

### 📊 Expected Output

The scripts will show progress like this:

```
2025-07-16 22:29:11,025 - INFO - Starting CSV batch processing
2025-07-16 22:29:11,025 - INFO - CSV file: cii-urls.csv
2025-07-16 22:29:11,025 - INFO - Collection: doc_store_v1
2025-07-16 22:29:11,025 - INFO - Limit: 2
2025-07-16 22:29:11,025 - INFO - Read 2 records from CSV file
2025-07-16 22:29:11,222 - INFO - ✅ Successfully processed: 272_12.pdf (Advanced Work Packaging Implementation Guide)
2025-07-16 22:29:11,222 - INFO - ✅ Successfully processed: 272_11.pdf (Project Definition Rating Index)
2025-07-16 22:29:11,321 - INFO - Batch processing complete!
2025-07-16 22:29:11,321 - INFO - ✅ Processed: 2
2025-07-16 22:29:11,321 - INFO - ⏭️  Skipped: 0
2025-07-16 22:29:11,321 - INFO - ❌ Failed: 0
```

### 🎯 Result

After processing, query responses will show:

```
Sources:
📄 Advanced Work Packaging Implementation Guide (Page iii)     [← clickable link]
📄 Project Definition Rating Index (Page 43)                  [← clickable link]
📄 Advanced Work Packaging Implementation Guide (Page 105)    [← clickable link]
```

Each source will be a clickable link that opens the document URL in a new tab, with the product name prominently displayed instead of just the filename.