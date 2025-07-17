import logging
import chromadb
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
    PromptTemplate # Import PromptTemplate
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from . import config
# Import the custom node postprocessor
from .node_processing import MetadataCitationPostprocessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Custom Prompt Templates ---

# Template for combining context and answering the question
# Instructs the LLM to cite sources using the format provided by the postprocessor
QA_TEMPLATE_STR = (
    "You are an assistant helping answer questions based ONLY on the provided context.\n"
    "The context below contains information extracted from various documents.\n"
    "Each piece of context is preceded by its source information (e.g., [Source: filename, Page: page_number]).\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given this context, please answer the following question:\n"
    "Question: {query_str}\n\n"
    "**Instructions:**\n"
    "1. Base your answer strictly on the information present in the context above.\n"
    "2. Do not use any prior knowledge or information outside the provided context.\n"
    "3. When you use information from a specific source, cite it clearly in your answer. For example: 'According to [Source: filename, Page: page_number], the value is X.' or 'The process involves Y [Source: filename, Page: page_number].'\n"
    "4. If the context does not contain information to answer the question, state that clearly.\n"
    "Answer: "
)
QA_TEMPLATE = PromptTemplate(QA_TEMPLATE_STR)

# Template for refining an existing answer with more context
# Also instructs the LLM to maintain citations
REFINE_TEMPLATE_STR = (
    "You are an assistant refining an existing answer based on new context.\n"
    "The original query was: {query_str}\n"
    "The existing answer is: {existing_answer}\n"
    "We have provided new context below, potentially relevant to improving the answer.\n"
    "Each piece of new context is preceded by its source information (e.g., [Source: filename, Page: page_number]).\n"
    "---------------------\n"
    "{context_msg}\n"
    "---------------------\n"
    "Given the new context, refine the original answer.\n"
    "**Instructions:**\n"
    "1. Improve the answer using ONLY the new context AND the original answer.\n"
    "2. Maintain or add citations for all information, using the format [Source: filename, Page: page_number].\n"
    "3. If the new context isn't helpful, return the original answer.\n"
    "Refined Answer: "
)
REFINE_TEMPLATE = PromptTemplate(REFINE_TEMPLATE_STR)

# --- End Custom Prompt Templates ---


def get_query_engine(collection_name: str, persist_dir: str):
    """
    Loads an existing index from ChromaDB and returns a query engine
    configured with citation handling.
    """
    logger.info(f"Setting up query engine for collection: {collection_name} from {persist_dir}")

    # Configure LlamaIndex Settings (Embeddings and LLM)
    Settings.embed_model = OpenAIEmbedding(
        model=config.EMBEDDING_MODEL,
        api_key=config.OPENAI_API_KEY
    )
    Settings.llm = OpenAI(
        model=config.LLM_MODEL,
        api_key=config.OPENAI_API_KEY,
        temperature=0.1 # Keep temperature low for factual answers
    )
    logger.info(f"Query Engine Settings: LLM={config.LLM_MODEL}, Embed={config.EMBEDDING_MODEL}")

    # Initialize ChromaDB client
    db = chromadb.PersistentClient(path=persist_dir)

    # Get the existing Chroma collection
    try:
        logger.info(f"Attempting to access existing ChromaDB collection: {collection_name}")
        chroma_collection = db.get_collection(collection_name)
        logger.info(f"Successfully accessed collection '{collection_name}'.")
    except Exception as e:
        logger.error(f"Failed to get ChromaDB collection '{collection_name}'. Has it been created via /preprocess? Error: {e}", exc_info=True)
        raise ValueError(f"Collection '{collection_name}' not found in {persist_dir}. Please run preprocessing first.") from e

    # Create LlamaIndex vector store wrapper
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # Load the index from the vector store
    logger.info("Loading index from vector store...")
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        # Settings are used implicitly here
    )
    logger.info("Index loaded successfully.")

    # Create the query engine WITH the custom prompts and node postprocessor
    query_engine = index.as_query_engine(
        response_mode="compact", # 'compact' or 'refine' often work well with citations
        # Use the custom prompt templates
        text_qa_template=QA_TEMPLATE,
        refine_template=REFINE_TEMPLATE,
        # Add the node postprocessor to format context before it hits the prompt
        node_postprocessors=[MetadataCitationPostprocessor()],
        similarity_top_k=3 # Adjust how many nodes to retrieve
    )
    logger.info("Query engine created with custom citation prompts and node postprocessor.")

    return query_engine

# --- answer_query function remains the same ---
# It will now use the query_engine configured above

def answer_query(query_text: str, collection_name: str, persist_dir: str) -> dict:
    """
    Answers a query using the RAG system, now configured for citations.
    """
    try:
        query_engine = get_query_engine(collection_name, persist_dir)
        logger.info(f"Querying index with: '{query_text}'")
        # The response object contains the final answer and source nodes
        response = query_engine.query(query_text)
        logger.info("Query processed successfully.")

        # The answer string should now contain citations based on the prompt
        answer = str(response)
        source_nodes_count = len(response.source_nodes)

        # Extract source information including URLs
        from .models import SourceInfo
        sources = []
        for node in response.source_nodes:
            metadata = node.node.metadata
            source_info = SourceInfo(
                file_name=metadata.get('file_name', 'Unknown'),
                page_label=metadata.get('page_label', 'Unknown'),
                document_url=metadata.get('document_url', 'https://www.construction-institute.org/'),
                product_name=metadata.get('product_name', None)
            )
            sources.append(source_info)

        return {
            "query": query_text,
            "answer": answer, # This answer string should have inline citations
            "source_nodes_count": source_nodes_count,
            "sources": sources
        }
    except ValueError as ve:
        logger.error(f"Query failed: {ve}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during query processing: {e}", exc_info=True)
        raise RuntimeError("Failed to process the query due to an internal error.") from e