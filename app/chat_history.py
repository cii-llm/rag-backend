from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from . import database
from datetime import datetime

class ChatHistoryService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(self, user_id: int, title: Optional[str] = None) -> database.ChatSession:
        """Create a new chat session"""
        session = database.ChatSession(
            user_id=user_id,
            title=title or "New Chat"
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def get_user_sessions(self, user_id: int, include_archived: bool = False) -> List[database.ChatSession]:
        """Get all chat sessions for a user"""
        query = self.db.query(database.ChatSession).filter(
            database.ChatSession.user_id == user_id
        )
        
        if not include_archived:
            query = query.filter(database.ChatSession.is_archived == False)
        
        return query.order_by(database.ChatSession.updated_at.desc()).all()
    
    def get_session(self, session_id: UUID, user_id: int) -> Optional[database.ChatSession]:
        """Get a specific chat session"""
        return self.db.query(database.ChatSession).filter(
            database.ChatSession.id == session_id,
            database.ChatSession.user_id == user_id
        ).first()
    
    def save_message(
        self, 
        session_id: UUID, 
        message_type: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> database.ChatMessage:
        """Save a message to a chat session"""
        message = database.ChatMessage(
            session_id=session_id,
            message_type=message_type,
            content=content,
            message_metadata=metadata
        )
        self.db.add(message)
        
        # Update session timestamp
        session = self.db.query(database.ChatSession).filter(
            database.ChatSession.id == session_id
        ).first()
        if session:
            session.updated_at = datetime.utcnow()
            # Auto-generate title from first user message if not set
            if not session.title or session.title == "New Chat":
                if message_type == "user":
                    session.title = content[:50] + "..." if len(content) > 50 else content
        
        self.db.commit()
        self.db.refresh(message)
        return message
    
    def get_session_messages(self, session_id: UUID, user_id: int) -> List[database.ChatMessage]:
        """Get all messages for a chat session"""
        # Verify user owns the session
        session = self.get_session(session_id, user_id)
        if not session:
            return []
        
        return self.db.query(database.ChatMessage).filter(
            database.ChatMessage.session_id == session_id
        ).order_by(database.ChatMessage.created_at.asc()).all()
    
    def get_session_message_count(self, session_id: UUID, user_id: int) -> int:
        """Get message count for a chat session"""
        # Verify user owns the session
        session = self.get_session(session_id, user_id)
        if not session:
            return 0
        
        return self.db.query(database.ChatMessage).filter(
            database.ChatMessage.session_id == session_id
        ).count()
    
    def update_session_title(self, session_id: UUID, user_id: int, title: str) -> bool:
        """Update session title"""
        session = self.get_session(session_id, user_id)
        if session:
            session.title = title
            session.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    def archive_session(self, session_id: UUID, user_id: int) -> bool:
        """Archive a chat session"""
        session = self.get_session(session_id, user_id)
        if session:
            session.is_archived = True
            session.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    def unarchive_session(self, session_id: UUID, user_id: int) -> bool:
        """Unarchive a chat session"""
        session = self.get_session(session_id, user_id)
        if session:
            session.is_archived = False
            session.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    def delete_session(self, session_id: UUID, user_id: int) -> bool:
        """Delete a chat session"""
        session = self.get_session(session_id, user_id)
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False
    
    def delete_message(self, message_id: int, user_id: int) -> bool:
        """Delete a specific message"""
        message = self.db.query(database.ChatMessage).join(
            database.ChatSession
        ).filter(
            database.ChatMessage.id == message_id,
            database.ChatSession.user_id == user_id
        ).first()
        
        if message:
            self.db.delete(message)
            self.db.commit()
            return True
        return False
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics"""
        total_sessions = self.db.query(database.ChatSession).filter(
            database.ChatSession.user_id == user_id
        ).count()
        
        active_sessions = self.db.query(database.ChatSession).filter(
            database.ChatSession.user_id == user_id,
            database.ChatSession.is_archived == False
        ).count()
        
        archived_sessions = total_sessions - active_sessions
        
        total_messages = self.db.query(database.ChatMessage).join(
            database.ChatSession
        ).filter(
            database.ChatSession.user_id == user_id
        ).count()
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "archived_sessions": archived_sessions,
            "total_messages": total_messages
        }