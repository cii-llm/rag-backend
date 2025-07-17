import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from . import database
from .database import get_db
from dotenv import load_dotenv

load_dotenv()

# Configuration
MOCK_AUTH_MODE = os.getenv("MOCK_AUTH_MODE", "true").lower() == "true"
KENTICO_SSO_SECRET = os.getenv("KENTICO_SSO_SECRET", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-secret-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

USE_MOCK_AUTH = MOCK_AUTH_MODE or not KENTICO_SSO_SECRET

# Mock user data
MOCK_USER_DATA = {
    "id": 1,
    "username": "demo_user",
    "email": "demo@cii.utexas.edu",
    "first_name": "Demo",
    "last_name": "User"
}

security = HTTPBearer(auto_error=False)

class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

def validate_kentico_jwt(token: str) -> Dict[str, Any]:
    """Validate JWT token from Kentico"""
    try:
        payload = jwt.decode(
            token, 
            KENTICO_SSO_SECRET, 
            algorithms=["HS256"]
        )
        
        # Check expiration
        if "Expires" in payload:
            expires = datetime.fromisoformat(payload["Expires"])
            if datetime.utcnow() > expires:
                raise AuthenticationError("Token expired")
        
        return payload
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")

def get_current_user_mock() -> Dict[str, Any]:
    """Return mock user for development"""
    return MOCK_USER_DATA

def get_current_user_jwt(credentials: HTTPAuthorizationCredentials, db: Session) -> Dict[str, Any]:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = validate_kentico_jwt(token)
    
    # Extract user info from JWT
    user_data = {
        "username": payload.get("username"),
        "email": payload.get("email"), 
        "first_name": payload.get("firstname"),
        "last_name": payload.get("lastname")
    }
    
    # Create or update user in database
    user = get_or_create_user(db, user_data)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name
    }

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user - mock or real based on configuration"""
    if USE_MOCK_AUTH:
        return get_current_user_mock()
    else:
        if not credentials:
            raise AuthenticationError("Missing authentication token")
        return get_current_user_jwt(credentials, db)

def get_or_create_user(db: Session, user_data: Dict[str, Any]) -> database.User:
    """Get existing user or create new one"""
    user = db.query(database.User).filter(
        database.User.username == user_data["username"]
    ).first()
    
    if not user:
        user = database.User(
            username=user_data["username"],
            email=user_data["email"],
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
    
    return user

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")

# Optional: For routes that don't require authentication
def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, otherwise return None"""
    try:
        return get_current_user(credentials, db)
    except AuthenticationError:
        return None