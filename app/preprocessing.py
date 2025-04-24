import logging
import chromadb

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from . import config
import os # Import os for path manipulation
from pathlib import Path # Import Path for easier path handling
from typing import Set, List # Import Set and List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_global_settings():
    """Sets up global LlamaIndex settings for LLM and Embeddings."""
    # Note: LLM is not strictly needed for indexing, only embeddings.
    # But setting it globally can be convenient if other parts use it.
    # We primarily need the embedding model here.
    Settings.embed_model = OpenAIEmbedding(
        model=config.EMBEDDING_MODEL,
        api_key=config.OPENAI_API_KEY
    )
    # Optional: Configure LLM globally if needed elsewhere or for consistency
    # from llama_index.llms.openai import OpenAI
    # Settings.llm = OpenAI(model=config.LLM_MODEL, api_key=config.OPENAI_API_KEY)
    logger.info(f"Global Settings configured with Embedding Model: {config.EMBEDDING_MODEL}")



def get_processed_filenames(db_client: chromadb.PersistentClient, collection_name: str) -> Set[str]:
    """
    Helper function to get unique filenames already processed in a collection.
    Uses db.list_collections() to check for existence first.
    """
    processed_files: Set[str] = set()
    collection_exists = False
    try:
        # Get list of all collection objects
        collections = db_client.list_collections()
        # Check if our collection name is in the list of names
        collection_names = {col.name for col in collections}
        if collection_name in collection_names:
            collection_exists = True
            logger.info(f"Collection '{collection_name}' found.")
        else:
            logger.info(f"Collection '{collection_name}' not found in the database.")

    except Exception as e:
        logger.error(f"Error listing collections from ChromaDB: {e}", exc_info=True)
        # If we can't even list collections, assume we can't get processed files
        return processed_files # Return empty set

    # If the collection exists, proceed to get metadata
    if collection_exists:
        try:
            collection = db_client.get_collection(name=collection_name)
            # Fetch only metadata, potentially optimize if collection is huge
            results = collection.get(include=['metadatas'])
            if results and results.get('metadatas'):
                for metadata in results['metadatas']:
                    if metadata and 'file_name' in metadata:
                        processed_files.add(metadata['file_name'])
            logger.info(f"Found {len(processed_files)} unique filenames already in collection '{collection_name}'.")
        except Exception as e:
            # Catch potential errors during .get() even if collection exists
            logger.error(f"Error retrieving metadata from existing collection '{collection_name}': {e}", exc_info=True)
            # Return empty set as we couldn't reliably get the data
            return set()
    # If collection didn't exist, processed_files is still the initial empty set
    return processed_files

# --- process_and_store_documents function remains the same ---
# It now uses the updated get_processed_filenames helper.

# Make sure the rest of process_and_store_documents is unchanged from the previous version
# (setup_global_settings, finding files, filtering new files, loading, storing)
def process_and_store_documents(data_folder: str, collection_name: str, persist_dir: str) -> int:
    setup_global_settings() # Ensure embedding model is set

    logger.info(f"Starting INCREMENTAL document processing from folder: {data_folder}")
    logger.info(f"Using ChromaDB collection: {collection_name} in {persist_dir}")

    # Initialize ChromaDB client
    db = chromadb.PersistentClient(path=persist_dir)

    # --- Get list of already processed files using the updated helper ---
    processed_filenames = get_processed_filenames(db, collection_name)
    # ---

    # --- Find files in the data directory ---
    input_dir = Path(data_folder)
    all_files_in_folder: List[Path] = []
    required_exts = [".pdf", ".xlsx"] # Keep required extensions

    for ext in required_exts:
        # Use rglob for recursive search
        all_files_in_folder.extend(list(input_dir.rglob(f'*{ext}')))
        all_files_in_folder.extend(list(input_dir.rglob(f'*{ext.upper()}'))) # Include uppercase extensions

    if not all_files_in_folder:
        logger.warning(f"No files with extensions {required_exts} found in {data_folder} (recursive).")
        return 0

    # --- Filter for NEW files only ---
    new_files_to_process: List[str] = []
    for file_path in all_files_in_folder:
        if file_path.name not in processed_filenames:
            new_files_to_process.append(str(file_path))

    if not new_files_to_process:
        logger.info(f"No new documents found in {data_folder} to process. Collection '{collection_name}' is up-to-date.")
        return 0

    logger.info(f"Found {len(new_files_to_process)} new file(s) to process: {new_files_to_process}")
    # ---

    # --- Load ONLY the new documents ---
    reader = SimpleDirectoryReader(
        input_files=new_files_to_process,
    )

    try:
        documents = reader.load_data()
        if not documents:
            logger.warning(f"Loaded 0 document chunks from the new files list. Check reader compatibility.")
            return 0
        logger.info(f"Loaded {len(documents)} document chunks from {len(new_files_to_process)} new file(s).")
    except Exception as e:
        logger.error(f"Error loading new documents: {e}", exc_info=True)
        raise

    # --- Index and Store the new documents ---
    logger.info(f"Accessing ChromaDB collection: {collection_name} to add new documents.")
    chroma_collection = db.get_or_create_collection(collection_name) # get_or_create is safe
    logger.info(f"Collection '{collection_name}' accessed/created successfully.")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    logger.info("Adding new documents to the vector store index...")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True
    )
    logger.info(f"Successfully added {len(documents)} chunks from new documents to collection '{collection_name}'.")

    return len(documents)