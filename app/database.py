import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON as PG_JSON
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy import Text as SQLText
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Try PostgreSQL first, fallback to SQLite if it fails
try:
    engine = create_engine(DATABASE_URL)
    # Test connection
    with engine.connect() as conn:
        pass
    print("PostgreSQL connection successful")
except Exception as e:
    print(f"PostgreSQL connection failed: {e}")
    print("Falling back to SQLite database")
    # Use SQLite as fallback
    DATABASE_URL = "sqlite:///./chat_history.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Cross-database UUID type
class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value

# Cross-database JSON type  
class JSON(TypeDecorator):
    """Platform-independent JSON type."""
    impl = SQLText
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_JSON())
        else:
            return dialect.type_descriptor(SQLText())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            import json
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            import json
            return json.loads(value)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    first_name = Column(String(255))
    last_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(GUID(), ForeignKey("chat_sessions.id"), nullable=False)
    message_type = Column(String(10), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON)  # Additional data like tokens, model info, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")

class UserDocumentAccess(Base):
    __tablename__ = "user_document_access"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    document_name = Column(String(255), primary_key=True)
    granted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

def get_db():
    """Database dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

def init_db():
    """Initialize database with tables and mock data"""
    create_tables()
    
    # Create mock user if in mock mode
    if os.getenv("MOCK_AUTH_MODE", "").lower() == "true":
        db = SessionLocal()
        try:
            # Check if mock user already exists
            existing_user = db.query(User).filter(User.username == "demo_user").first()
            if not existing_user:
                mock_user = User(
                    id=1,
                    username="demo_user",
                    email="demo@cii.utexas.edu",
                    first_name="Demo",
                    last_name="User"
                )
                db.add(mock_user)
                db.commit()
                print("Mock user created successfully")
            else:
                print("Mock user already exists")
        except Exception as e:
            print(f"Error creating mock user: {e}")
            db.rollback()
        finally:
            db.close()