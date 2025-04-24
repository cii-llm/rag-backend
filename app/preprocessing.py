import logging
import chromadb
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding # Use specific embedding class
from . import config # Use relative import within the package

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


def process_and_store_documents(data_folder: str, collection_name: str, persist_dir: str) -> int:
    """
    Loads documents from a folder, processes them, and stores them in ChromaDB.

    Args:
        data_folder: The path to the folder containing documents.
        collection_name: The name of the ChromaDB collection.
        persist_dir: The directory to persist ChromaDB data.

    Returns:
        The number of documents processed.
    """
    setup_global_settings() # Ensure embedding model is set

    logger.info(f"Starting document processing from folder: {data_folder}")
    logger.info(f"Using ChromaDB collection: {collection_name} in {persist_dir}")

    # Supported file types by SimpleDirectoryReader with necessary extras installed
    required_exts = [".pdf", ".xlsx"]
    reader = SimpleDirectoryReader(
        input_dir=data_folder,
        required_exts=required_exts,
        recursive=True, # Process subdirectories as well
    )

    try:
        documents = reader.load_data()
        if not documents:
            logger.warning(f"No documents found in {data_folder} with extensions {required_exts}")
            return 0
        logger.info(f"Loaded {len(documents)} document chunks.") # Note: LlamaIndex splits docs into chunks
    except Exception as e:
        logger.error(f"Error loading documents from {data_folder}: {e}", exc_info=True)
        raise

    # Initialize ChromaDB client
    db = chromadb.PersistentClient(path=persist_dir)

    # Get or create the Chroma collection
    logger.info(f"Accessing ChromaDB collection: {collection_name}")
    chroma_collection = db.get_or_create_collection(collection_name)
    logger.info(f"Collection '{collection_name}' accessed/created successfully.")

    # Create a LlamaIndex vector store wrapper around the Chroma collection
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # Create a storage context using the vector store
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Create the index - this processes documents and stores embeddings in ChromaDB
    # Uses the globally set embedding model via Settings
    logger.info("Creating/updating vector store index...")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True # Show progress bar in console
    )
    logger.info(f"Successfully created/updated index for collection '{collection_name}'.")

    # Persistence is handled by ChromaDB PersistentClient, no extra index.persist needed here

    return len(documents) # Return the number of loaded document chunks