      
import chromadb
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


@app.get("/processed_documents",
         response_model=models.ProcessedDocumentsResponse,
         summary="List Processed Documents",
         description="Retrieves a list of unique source filenames stored in the specified ChromaDB collection.")
async def get_processed_documents(collection_name: str | None = None):
    """
    Queries ChromaDB to find unique source filenames that have been processed.
    Uses db.list_collections() to check for existence first.
    """
    collection_to_check = collection_name or config.COLLECTION_NAME
    persist_dir_to_use = str(config.PERSIST_DIR)
    logger.info(f"Request received to list processed documents in collection: '{collection_to_check}'")

    processed_files: Set[str] = set()
    collection_exists = False

    try:
        # Initialize ChromaDB client
        db = chromadb.PersistentClient(path=persist_dir_to_use)

        # Check if collection exists by listing all collections
        try:
            logger.debug(f"Listing collections to check for '{collection_to_check}'.")
            collections = db.list_collections()
            collection_names = {col.name for col in collections}
            if collection_to_check in collection_names:
                collection_exists = True
                logger.debug(f"Collection '{collection_to_check}' confirmed to exist.")
            else:
                 logger.info(f"Collection '{collection_to_check}' does not exist.")
                 # If collection doesn't exist, return empty list immediately
                 return models.ProcessedDocumentsResponse(
                     collection_name=collection_to_check,
                     processed_filenames=[],
                     count=0
                 )
        except Exception as e:
            logger.error(f"Error listing collections from ChromaDB: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to query vector store collections.")

        # If collection exists, get its metadata
        if collection_exists:
            try:
                logger.debug(f"Fetching metadata from existing collection '{collection_to_check}'.")
                collection = db.get_collection(name=collection_to_check)
                results = collection.get(include=['metadatas']) # Only fetch metadata
                logger.info(f"Retrieved metadata for {len(results.get('ids', []))} chunks from '{collection_to_check}'.")

                if results and results.get('metadatas'):
                    for metadata in results['metadatas']:
                        if metadata and 'file_name' in metadata:
                            processed_files.add(metadata['file_name'])

            except Exception as e:
                # Catch errors during the .get() call itself
                logger.error(f"Error retrieving metadata from collection '{collection_to_check}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to retrieve metadata from collection '{collection_to_check}'.")

        # Convert set to sorted list for consistent output
        sorted_filenames = sorted(list(processed_files))

        return models.ProcessedDocumentsResponse(
            collection_name=collection_to_check,
            processed_filenames=sorted_filenames,
            count=len(sorted_filenames)
        )

    except Exception as e:
        # Catch broader errors like DB connection issues
        logger.exception(f"An unexpected error occurred while listing processed documents for collection '{collection_to_check}': {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred. Check logs. Error: {str(e)}")