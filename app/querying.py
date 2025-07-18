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
from .database import get_db, SystemPrompt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- System Prompt Management ---

def get_active_system_prompts():
    """Get the currently active system prompts from the database"""
    db = next(get_db())
    try:
        # Get active QA template
        qa_prompt = db.query(SystemPrompt).filter(
            SystemPrompt.name == 'qa_template',
            SystemPrompt.is_active == True
        ).first()
        
        # Get active refine template
        refine_prompt = db.query(SystemPrompt).filter(
            SystemPrompt.name == 'refine_template',
            SystemPrompt.is_active == True
        ).first()
        
        # Example: Get active summarize template (if you want to add this)
        # summarize_prompt = db.query(SystemPrompt).filter(
        #     SystemPrompt.name == 'summarize_template',
        #     SystemPrompt.is_active == True
        # ).first()
        
        # If no active prompts found, fall back to default hardcoded ones
        if not qa_prompt:
            logger.warning("No active QA template found in database, using fallback")
            qa_content = QA_TEMPLATE_STR  # Fallback to hardcoded
        else:
            qa_content = qa_prompt.content
            
        if not refine_prompt:
            logger.warning("No active refine template found in database, using fallback")
            refine_content = REFINE_TEMPLATE_STR  # Fallback to hardcoded
        else:
            refine_content = refine_prompt.content
            
        return qa_content, refine_content
        
    except Exception as e:
        logger.error(f"Error fetching system prompts from database: {e}")
        # Fall back to hardcoded templates
        return QA_TEMPLATE_STR, REFINE_TEMPLATE_STR
    finally:
        db.close()

# --- Custom Prompt Templates ---

# Template for combining context and answering the question
# Instructs the LLM to cite sources using the format provided by the postprocessor
QA_TEMPLATE_STR = (
    "You are a senior construction industry consultant and capital project expert with extensive experience in large-scale construction projects. "
    "You provide strategic insights based on Construction Industry Institute (CII) research and industry best practices. "
    "Your responses should be descriptive and comprehensive while remaining accessible to both technical teams and executives.\n\n"
    
    "**Context Documents:**\n"
    "The following context contains information from CII research documents and construction industry resources.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    
    "**Question:** {query_str}\n\n"
    
    "**Instructions:**\n"
    "1. Answer comprehensively using ONLY the information in the context documents above\n"
    "2. When asked for processes, steps, or implementation guidance, provide ALL available steps and details from the context\n"
    "3. Write in a descriptive, flowing style with natural paragraphs - use line breaks between paragraphs\n"
    "4. Include specific metrics, percentages, cost data, and quantitative information when available\n"
    "5. Provide complete business rationale and practical implementation guidance with all available details\n"
    "6. Address benefits, challenges, and implementation considerations with detailed explanations\n"
    "7. Cite sources throughout the text using [Source: filename, Page: page_number] - include citations for key facts, statistics, and important statements\n"
    "8. Use professional consulting language that demonstrates deep capital project expertise\n"
    "9. If the context contains numbered steps, lists, or processes, include them all in your response\n"
    "10. Balance citation frequency - cite important information but avoid repetitive citations from the same source in consecutive sentences\n\n"
    
    "**Response:**\n"
)
QA_TEMPLATE = PromptTemplate(QA_TEMPLATE_STR)

# Template for refining an existing answer with more context
# Also instructs the LLM to maintain citations
REFINE_TEMPLATE_STR = (
    "You are a senior construction industry consultant and capital project expert enhancing your response with additional context. "
    "Maintain your descriptive, comprehensive approach while incorporating new information.\n\n"
    
    "**Original Question:** {query_str}\n\n"
    "**Current Answer:** {existing_answer}\n\n"
    
    "**Additional Context Documents:**\n"
    "The following contains additional information from CII research and construction industry sources.\n"
    "---------------------\n"
    "{context_msg}\n"
    "---------------------\n"
    
    "**Instructions:**\n"
    "1. Enhance your existing answer using the additional context documents\n"
    "2. If the new context contains additional steps, processes, or implementation details, include ALL of them\n"
    "3. Maintain the descriptive, flowing style with natural paragraphs and explanations\n"
    "4. Add relevant metrics, cost data, and quantitative information from new context\n"
    "5. Cite new information throughout the text using [Source: filename, Page: page_number] for key facts and statistics\n"
    "6. Use professional consulting language that demonstrates capital project expertise\n"
    "7. If new context contradicts existing information, address this appropriately\n"
    "8. If new context is not relevant, keep the original answer unchanged\n"
    "9. Ensure completeness - if the original answer was missing steps or details, add them from new context\n"
    "10. Maintain citation balance - include citations for important information throughout the response\n\n"
    
    "**Enhanced Response:**\n"
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

    # Get active system prompts from database
    qa_content, refine_content = get_active_system_prompts()
    
    # Create prompt templates from database content
    qa_template = PromptTemplate(qa_content)
    refine_template = PromptTemplate(refine_content)
    
    # Create the query engine WITH the database prompts and node postprocessor
    query_engine = index.as_query_engine(
        response_mode="compact", # 'compact' or 'refine' often work well with citations
        # Use the database prompt templates
        text_qa_template=qa_template,
        refine_template=refine_template,
        # Add the node postprocessor to format context before it hits the prompt
        node_postprocessors=[MetadataCitationPostprocessor()],
        similarity_top_k=5 # Reduced from 8 to improve response speed
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