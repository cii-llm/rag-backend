      
import chromadb
import logging
import os
import shutil
from pathlib import Path
from typing import List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import FastAPI, HTTPException, Body, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from . import config, preprocessing, querying, models # Relative imports
from .auth import get_current_user, get_current_user_optional
from .chat_history import ChatHistoryService
from .database import get_db, init_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG API with LlamaIndex, ChromaDB, and GPT-4",
    description="API for preprocessing documents and querying them using a RAG pipeline.",
    version="1.0.0",
)

# Initialize database
init_db()

# --- CORS Configuration ---
# Define the list of origins allowed to connect (your Vue frontend)
# IMPORTANT: Use the specific origin in production, '*' is less secure
origins = [
    "http://localhost:5173", # Your Vue frontend origin
    "http://127.0.0.1:5173", # Sometimes needed depending on browser/OS
    # Add your deployed frontend URL here later if applicable
    # e.g., "https://your-frontend-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # List of allowed origins
    allow_credentials=True, # Allow cookies/auth headers
    allow_methods=["*"],    # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],    # Allow all headers
)
# --- End CORS Configuration ---


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
async def preprocess_endpoint(request: models.PreprocessRequest = Body(None), current_user: dict = Depends(get_current_user)):
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
async def query_endpoint(request: models.QueryRequest, current_user: dict = Depends(get_current_user)):
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
    return {"status": "ok", "message": "RAG API is running", "auth_mode": "mock" if os.getenv("MOCK_AUTH_MODE", "").lower() == "true" else "production"}


@app.get("/processed_documents",
         response_model=models.ProcessedDocumentsResponse,
         summary="List Processed Documents",
         description="Retrieves a list of unique source filenames stored in the specified ChromaDB collection.")
async def get_processed_documents(collection_name: str | None = None, current_user: dict = Depends(get_current_user)):
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


@app.post("/upload_file",
          response_model=models.FileUploadResponse,
          summary="Upload File",
          description="Uploads a file to the data folder and optionally processes it into the vector store.")
async def upload_file(
    file: UploadFile = File(...),
    process_immediately: bool = True,
    collection_name: str | None = None,
    document_url: str | None = None,
    product_name: str | None = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Uploads a file to the data folder and optionally processes it into ChromaDB.
    """
    collection_to_use = collection_name or config.COLLECTION_NAME
    data_folder_to_use = str(config.DATA_FOLDER)
    
    logger.info(f"Received file upload: {file.filename}")
    
    # Validate file type
    allowed_extensions = {'.pdf', '.docx'}
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File type {file_extension} not supported. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Ensure data folder exists
        os.makedirs(data_folder_to_use, exist_ok=True)
        
        # Save uploaded file
        file_path = Path(data_folder_to_use) / file.filename
        
        # Check if file already exists
        if file_path.exists():
            raise HTTPException(status_code=409, detail=f"File {file.filename} already exists")
        
        # Write file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        processed = False
        message = f"File {file.filename} uploaded successfully"
        
        # Process immediately if requested
        if process_immediately:
            try:
                # Use provided URL or default
                url_to_use = document_url or "https://www.construction-institute.org/"
                num_processed = preprocessing.process_and_store_documents(
                    data_folder=data_folder_to_use,
                    collection_name=collection_to_use,
                    persist_dir=str(config.PERSIST_DIR),
                    document_url=url_to_use,
                    product_name=product_name
                )
                processed = True
                message = f"File {file.filename} uploaded and processed successfully"
            except Exception as e:
                logger.error(f"Failed to process uploaded file {file.filename}: {e}")
                message = f"File {file.filename} uploaded but processing failed: {str(e)}"
        
        return models.FileUploadResponse(
            message=message,
            filename=file.filename,
            processed=processed
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to upload file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


@app.delete("/delete_file",
           response_model=models.FileDeleteResponse,
           summary="Delete File",
           description="Removes a file from both the file system and the vector store.")
async def delete_file(request: models.FileDeleteRequest, current_user: dict = Depends(get_current_user)):
    """
    Deletes a file from the data folder and removes its embeddings from ChromaDB.
    """
    collection_to_use = request.collection_name or config.COLLECTION_NAME
    data_folder_to_use = str(config.DATA_FOLDER)
    persist_dir_to_use = str(config.PERSIST_DIR)
    
    logger.info(f"Received delete request for file: {request.filename}")
    
    try:
        deleted = False
        
        # Remove from file system
        file_path = Path(data_folder_to_use) / request.filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file from filesystem: {request.filename}")
        
        # Remove from vector store
        try:
            db = chromadb.PersistentClient(path=persist_dir_to_use)
            collections = db.list_collections()
            collection_names = {col.name for col in collections}
            
            if collection_to_use in collection_names:
                collection = db.get_collection(name=collection_to_use)
                
                # Get all documents with this filename
                results = collection.get(
                    where={"file_name": request.filename}
                )
                
                if results and results['ids']:
                    # Delete all chunks for this file
                    collection.delete(ids=results['ids'])
                    deleted = True
                    logger.info(f"Deleted {len(results['ids'])} chunks for file {request.filename} from vector store")
                else:
                    logger.info(f"No chunks found for file {request.filename} in vector store")
            
        except Exception as e:
            logger.error(f"Error removing {request.filename} from vector store: {e}")
        
        return models.FileDeleteResponse(
            message=f"File {request.filename} deleted successfully" if deleted else f"File {request.filename} not found in vector store",
            filename=request.filename,
            deleted=deleted
        )
        
    except Exception as e:
        logger.exception(f"Failed to delete file {request.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"File deletion failed: {str(e)}")


@app.post("/update_document_urls",
          summary="Update Document URLs",
          description="Updates existing documents in the vector store with default URL metadata.")
async def update_document_urls(
    collection_name: str | None = None,
    default_url: str = "https://www.construction-institute.org/",
    current_user: dict = Depends(get_current_user)
):
    """
    Updates existing documents in ChromaDB with default URL metadata.
    """
    collection_to_use = collection_name or config.COLLECTION_NAME
    persist_dir_to_use = str(config.PERSIST_DIR)
    
    logger.info(f"Received request to update document URLs in collection: {collection_to_use}")
    
    try:
        updated_count = preprocessing.update_existing_documents_with_urls(
            collection_name=collection_to_use,
            persist_dir=persist_dir_to_use,
            default_url=default_url
        )
        
        return {
            "message": f"Successfully updated {updated_count} documents with URL metadata",
            "collection_name": collection_to_use,
            "default_url": default_url,
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.exception(f"Failed to update document URLs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update document URLs: {str(e)}")


# --- Authentication and Chat History Endpoints ---

@app.get("/me", 
         response_model=models.UserResponse,
         summary="Get Current User",
         description="Get information about the currently authenticated user.")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return models.UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        first_name=current_user.get("first_name"),
        last_name=current_user.get("last_name"),
        created_at=current_user.get("created_at", datetime.utcnow()),
        last_login=current_user.get("last_login")
    )


# Chat Session Endpoints
@app.post("/chat/sessions", 
          response_model=models.ChatSessionResponse,
          summary="Create Chat Session",
          description="Create a new chat session for the current user.")
async def create_chat_session(
    session_data: models.ChatSessionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session"""
    chat_service = ChatHistoryService(db)
    session = chat_service.create_session(
        user_id=current_user["id"],
        title=session_data.title
    )
    return models.ChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        is_archived=session.is_archived,
        message_count=0
    )


@app.get("/chat/sessions", 
         response_model=List[models.ChatSessionResponse],
         summary="List Chat Sessions",
         description="Get all chat sessions for the current user.")
async def get_chat_sessions(
    include_archived: bool = False,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all chat sessions for the current user"""
    chat_service = ChatHistoryService(db)
    sessions = chat_service.get_user_sessions(current_user["id"], include_archived)
    
    # Add message count to each session
    result = []
    for session in sessions:
        message_count = chat_service.get_session_message_count(session.id, current_user["id"])
        result.append(models.ChatSessionResponse(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            is_archived=session.is_archived,
            message_count=message_count
        ))
    
    return result


@app.get("/chat/sessions/{session_id}", 
         response_model=models.ChatSessionWithMessages,
         summary="Get Chat Session",
         description="Get a specific chat session with all its messages.")
async def get_chat_session(
    session_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific chat session with messages"""
    chat_service = ChatHistoryService(db)
    
    # Get session
    session = chat_service.get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get messages
    messages = chat_service.get_session_messages(session_id, current_user["id"])
    
    return models.ChatSessionWithMessages(
        session=models.ChatSessionResponse(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            is_archived=session.is_archived,
            message_count=len(messages)
        ),
        messages=[
            models.ChatMessageResponse(
                id=msg.id,
                session_id=msg.session_id,
                message_type=msg.message_type,
                content=msg.content,
                metadata=msg.message_metadata,
                created_at=msg.created_at
            )
            for msg in messages
        ]
    )


@app.get("/chat/sessions/{session_id}/messages", 
         response_model=List[models.ChatMessageResponse],
         summary="Get Session Messages",
         description="Get all messages for a specific chat session.")
async def get_session_messages(
    session_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages for a specific chat session"""
    chat_service = ChatHistoryService(db)
    messages = chat_service.get_session_messages(session_id, current_user["id"])
    
    return [
        models.ChatMessageResponse(
            id=msg.id,
            session_id=msg.session_id,
            message_type=msg.message_type,
            content=msg.content,
            metadata=msg.message_metadata,
            created_at=msg.created_at
        )
        for msg in messages
    ]


@app.put("/chat/sessions/{session_id}", 
         response_model=models.ChatSessionResponse,
         summary="Update Chat Session",
         description="Update a chat session's title or archive status.")
async def update_chat_session(
    session_id: UUID,
    session_update: models.ChatSessionUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a chat session"""
    chat_service = ChatHistoryService(db)
    
    # Get session to ensure it exists and user owns it
    session = chat_service.get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update title if provided
    if session_update.title is not None:
        chat_service.update_session_title(session_id, current_user["id"], session_update.title)
    
    # Update archive status if provided
    if session_update.is_archived is not None:
        if session_update.is_archived:
            chat_service.archive_session(session_id, current_user["id"])
        else:
            chat_service.unarchive_session(session_id, current_user["id"])
    
    # Get updated session
    updated_session = chat_service.get_session(session_id, current_user["id"])
    message_count = chat_service.get_session_message_count(session_id, current_user["id"])
    
    return models.ChatSessionResponse(
        id=updated_session.id,
        title=updated_session.title,
        created_at=updated_session.created_at,
        updated_at=updated_session.updated_at,
        is_archived=updated_session.is_archived,
        message_count=message_count
    )


@app.post("/chat/sessions/{session_id}/archive",
          summary="Archive Chat Session",
          description="Archive a chat session.")
async def archive_chat_session(
    session_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Archive a chat session"""
    chat_service = ChatHistoryService(db)
    success = chat_service.archive_session(session_id, current_user["id"])
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"message": "Session archived successfully"}


@app.delete("/chat/sessions/{session_id}",
            summary="Delete Chat Session",
            description="Delete a chat session and all its messages.")
async def delete_chat_session(
    session_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat session"""
    chat_service = ChatHistoryService(db)
    success = chat_service.delete_session(session_id, current_user["id"])
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"message": "Session deleted successfully"}


# Enhanced Query Endpoint with Chat History
@app.post("/query_with_session", 
          response_model=models.QueryWithSessionResponse,
          summary="Query with Session",
          description="Query documents and save the conversation to chat history.")
async def query_with_session(
    request: models.QueryWithSessionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Query documents and save to chat history"""
    chat_service = ChatHistoryService(db)
    
    # Create new session if none provided
    if not request.session_id:
        session = chat_service.create_session(current_user["id"])
        session_id = session.id
    else:
        session_id = request.session_id
        # Verify user owns this session
        if not chat_service.get_session(session_id, current_user["id"]):
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Save user message
    chat_service.save_message(
        session_id=session_id,
        message_type="user",
        content=request.query
    )
    
    try:
        # Perform the actual query (existing logic)
        collection_name = request.collection_name or config.COLLECTION_NAME
        result = querying.answer_query(
            query_text=request.query,
            collection_name=collection_name,
            persist_dir=str(config.PERSIST_DIR)
        )
        
        # Convert SourceInfo objects to dictionaries for JSON serialization
        sources_dict = []
        if result.get("sources"):
            for source in result["sources"]:
                if hasattr(source, 'dict'):
                    sources_dict.append(source.dict())
                else:
                    sources_dict.append(source)
        
        # Save assistant response
        chat_service.save_message(
            session_id=session_id,
            message_type="assistant",
            content=result["answer"],
            metadata={
                "sources": sources_dict,
                "collection_name": collection_name,
                "source_nodes_count": result.get("source_nodes_count", 0)
            }
        )
        
        # Return response with session ID
        return models.QueryWithSessionResponse(
            query=request.query,
            answer=result["answer"],
            source_nodes_count=result.get("source_nodes_count", 0),
            session_id=session_id,
            sources=result.get("sources", [])
        )
        
    except Exception as e:
        logger.exception(f"Failed to query documents: {e}")
        # Save error message
        chat_service.save_message(
            session_id=session_id,
            message_type="assistant",
            content=f"Sorry, I encountered an error: {str(e)}",
            metadata={"error": True, "error_message": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/chat/stats",
         response_model=models.UserStatsResponse,
         summary="Get Chat Statistics",
         description="Get chat statistics for the current user.")
async def get_chat_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user chat statistics"""
    chat_service = ChatHistoryService(db)
    stats = chat_service.get_user_stats(current_user["id"])
    
    return models.UserStatsResponse(**stats)