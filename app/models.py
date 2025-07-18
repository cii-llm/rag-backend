from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

class PreprocessRequest(BaseModel):
    # Optional: Allow specifying folder/collection via API, otherwise use .env defaults
    data_folder: Optional[str] = Field(None, description="Path to the folder containing documents relative to the project root. Overrides .env setting.")
    collection_name: Optional[str] = Field(None, description="Name for the ChromaDB collection. Overrides .env setting.")

class PreprocessResponse(BaseModel):
    message: str
    collection_name: str
    documents_processed: int
    persist_directory: str

class SourceInfo(BaseModel):
    file_name: str
    page_label: str
    document_url: str
    product_name: Optional[str] = None

class QueryRequest(BaseModel):
    query: str = Field(..., description="The question to ask the RAG system.")
    collection_name: Optional[str] = Field(None, description="Name of the ChromaDB collection to query. Overrides .env setting.")

class QueryResponse(BaseModel):
    query: str
    answer: str
    source_nodes_count: int # Example metadata, LlamaIndex response has more
    sources: Optional[List[SourceInfo]] = None

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

# Authentication Models
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Chat History Models
class ChatSessionCreate(BaseModel):
    title: Optional[str] = None

class ChatSessionResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    is_archived: bool
    message_count: Optional[int] = None

class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None

class ChatMessageCreate(BaseModel):
    session_id: UUID
    message_type: str  # 'user' or 'assistant'
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ChatMessageResponse(BaseModel):
    id: int
    session_id: UUID
    message_type: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    reaction: Optional[str] = None  # 'thumbs_up', 'thumbs_down', or None
    created_at: datetime

class ChatSessionWithMessages(BaseModel):
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]

# Enhanced Query Request to include session management
class QueryWithSessionRequest(BaseModel):
    query: str = Field(..., description="The question to ask the RAG system.")
    collection_name: Optional[str] = Field(None, description="Name of the ChromaDB collection to query. Overrides .env setting.")
    session_id: Optional[UUID] = Field(None, description="Chat session ID. If None, creates new session.")

class QueryWithSessionResponse(BaseModel):
    query: str
    answer: str
    source_nodes_count: int
    session_id: UUID
    sources: Optional[List[SourceInfo]] = None
    user_message_id: Optional[int] = None  # Database ID of the user message
    assistant_message_id: Optional[int] = None  # Database ID of the assistant message

# User Statistics
class UserStatsResponse(BaseModel):
    total_sessions: int
    active_sessions: int
    archived_sessions: int
    total_messages: int

# Message Reaction Models
class MessageReactionRequest(BaseModel):
    reaction: Optional[str] = Field(None, description="Reaction type: 'thumbs_up', 'thumbs_down', or null to remove")
    
    class Config:
        schema_extra = {
            "example": {
                "reaction": "thumbs_up"
            }
        }

class MessageReactionResponse(BaseModel):
    message_id: int
    reaction: Optional[str]
    message: str