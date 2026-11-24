import os
import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db import get_db, User

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "raj-police-cyber-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours for prototype demo

security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    token = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except Exception:
        raise HTTPException(status_code=401, detail="Expired or invalid token")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*allowed_roles: str):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for role '{current_user.role}'. Required: {list(allowed_roles)}"
            )
        return current_user
    return role_checker


def seed_default_users(db: Session):
    default_users = [
        {
            "username": "admin",
            "password": "Admin@RajPolice2026",
            "role": "admin",
            "full_name": "ACP Ramesh Meena",
            "badge_number": "RAJ-POL-ADM-01"
        },
        {
            "username": "io_sharma",
            "password": "IO@RajPolice2026",
            "role": "investigating_officer",
            "full_name": "Inspector Ajay Sharma",
            "badge_number": "RAJ-POL-IO-42"
        },
        {
            "username": "sp_verma",
            "password": "SP@RajPolice2026",
            "role": "senior_officer",
            "full_name": "SP Sangeeta Verma",
            "badge_number": "RAJ-POL-SP-09"
        }
    ]

    for u in default_users:
        existing = db.query(User).filter(User.username == u["username"]).first()
        if not existing:
            user = User(
                username=u["username"],
                password_hash=hash_password(u["password"]),
                role=u["role"],
                full_name=u["full_name"],
                badge_number=u["badge_number"]
            )
            db.add(user)
    db.commit()
