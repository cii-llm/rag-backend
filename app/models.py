from pydantic import BaseModel, Field
from typing import Optional, List

class PreprocessRequest(BaseModel):
    # Optional: Allow specifying folder/collection via API, otherwise use .env defaults
    data_folder: Optional[str] = Field(None, description="Path to the folder containing documents relative to the project root. Overrides .env setting.")
    collection_name: Optional[str] = Field(None, description="Name for the ChromaDB collection. Overrides .env setting.")

class PreprocessResponse(BaseModel):
    message: str
    collection_name: str
    documents_processed: int
    persist_directory: str

class QueryRequest(BaseModel):
    query: str = Field(..., description="The question to ask the RAG system.")
    collection_name: Optional[str] = Field(None, description="Name of the ChromaDB collection to query. Overrides .env setting.")

class QueryResponse(BaseModel):
    query: str
    answer: str
    source_nodes_count: int # Example metadata, LlamaIndex response has more

class ProcessedDocumentsResponse(BaseModel):
    collection_name: str
    processed_filenames: List[str]
    count: int

class FileUploadResponse(BaseModel):
    message: str
    filename: str
    processed: bool

class FileDeleteRequest(BaseModel):
    filename: str = Field(..., description="Name of the file to delete from the vector store")
    collection_name: Optional[str] = Field(None, description="Name of the ChromaDB collection. Overrides .env setting.")

class FileDeleteResponse(BaseModel):
    message: str
    filename: str
    deleted: bool