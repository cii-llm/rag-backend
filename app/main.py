import logging
from fastapi import FastAPI, HTTPException, Body, Depends
from . import config, preprocessing, querying, models # Relative imports

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG API with LlamaIndex, ChromaDB, and GPT-4",
    description="API for preprocessing documents and querying them using a RAG pipeline.",
    version="1.0.0",
)

# --- Dependency for Configuration ---
# This allows overriding config via request body if needed, otherwise uses .env defaults
# You could simplify this if overrides aren't needed.
class CommonParams:
    def __init__(
        self,
        collection_name: str | None = None,
        data_folder: str | None = None,
        persist_dir: str | None = None,
    ):
        self.collection_name = collection_name or config.COLLECTION_NAME
        # Resolve relative paths from request body against project root if provided
        self.data_folder = str(config.BASE_DIR / data_folder) if data_folder else str(config.DATA_FOLDER)
        self.persist_dir = str(config.BASE_DIR / persist_dir) if persist_dir else str(config.PERSIST_DIR)

# --- API Endpoints ---

@app.post("/preprocess",
          response_model=models.PreprocessResponse,
          summary="Preprocess Documents",
          description="Loads PDF and XLSX files from a specified folder, processes them, and stores embeddings in ChromaDB.")
async def preprocess_endpoint(request: models.PreprocessRequest = Body(None)):
    """
    Initiates the document preprocessing pipeline.
    Uses configuration from .env file, which can be optionally overridden in the request body.
    """
    # Use request values if provided, otherwise fallback to config defaults
    data_folder_to_use = str(config.BASE_DIR / request.data_folder) if request and request.data_folder else str(config.DATA_FOLDER)
    collection_name_to_use = request.collection_name if request and request.collection_name else config.COLLECTION_NAME
    persist_dir_to_use = str(config.PERSIST_DIR) # Persist dir usually fixed

    logger.info(f"Received preprocessing request for folder: {data_folder_to_use}, collection: {collection_name_to_use}")

    try:
        # Run the potentially long-running preprocessing task
        # In a production scenario, consider background tasks (e.g., Celery)
        num_processed = preprocessing.process_and_store_documents(
            data_folder=data_folder_to_use,
            collection_name=collection_name_to_use,
            persist_dir=persist_dir_to_use
        )
        message = f"Successfully processed documents and updated collection '{collection_name_to_use}'."
        if num_processed == 0:
             message = f"No new documents found or processed in '{data_folder_to_use}'. Collection '{collection_name_to_use}' remains unchanged or empty."

        return models.PreprocessResponse(
            message=message,
            collection_name=collection_name_to_use,
            documents_processed=num_processed,
            persist_directory=persist_dir_to_use
        )
    except FileNotFoundError as e:
        logger.error(f"Preprocessing error: Data folder not found at {data_folder_to_use}")
        raise HTTPException(status_code=404, detail=f"Data folder not found: {data_folder_to_use}. Error: {e}")
    except Exception as e:
        logger.exception(f"Failed to preprocess documents for collection '{collection_name_to_use}'. Error: {e}") # Log full traceback
        raise HTTPException(status_code=500, detail=f"An internal server error occurred during preprocessing. Check logs. Error: {str(e)}")


@app.post("/query",
          response_model=models.QueryResponse,
          summary="Query Documents",
          description="Sends a query to the RAG system, retrieves relevant context from ChromaDB, and generates an answer using GPT-4.")
async def query_endpoint(request: models.QueryRequest):
    """
    Queries the indexed documents.
    Uses configuration from .env file, collection name can be overridden.
    """
    collection_name_to_use = request.collection_name or config.COLLECTION_NAME
    persist_dir_to_use = str(config.PERSIST_DIR) # Persist dir usually fixed

    logger.info(f"Received query for collection '{collection_name_to_use}': '{request.query}'")

    if not request.query:
         raise HTTPException(status_code=400, detail="Query text cannot be empty.")

    try:
        result = querying.answer_query(
            query_text=request.query,
            collection_name=collection_name_to_use,
            persist_dir=persist_dir_to_use
        )
        return models.QueryResponse(**result)
    except ValueError as e: # Catch collection not found error
         logger.warning(f"Query failed: {e}")
         raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to answer query for collection '{collection_name_to_use}'. Error: {e}") # Log full traceback
        raise HTTPException(status_code=500, detail=f"An internal server error occurred during query processing. Check logs. Error: {str(e)}")

@app.get("/", summary="Health Check", description="Basic health check endpoint.")
async def root():
    return {"status": "ok", "message": "RAG API is running"}