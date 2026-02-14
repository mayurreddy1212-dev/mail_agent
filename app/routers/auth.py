from datetime import datetime, timedelta, timezone
from typing import Annotated
import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Admin

import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(tags=["Authentication"])

bcrypt_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

class CreateAdminRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        password = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return bcrypt_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if len(plain_password.encode("utf-8")) > 72:
        plain_password = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return bcrypt_context.verify(plain_password, hashed_password)


def authenticate_admin(name: str, password: str, db: Session):
    user = db.query(Admin).filter(Admin.name == name).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    encode = {
        "sub": username,
        "id": user_id,
        "exp": datetime.now(timezone.utc) + expires_delta
    }
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

allow=True
if allow == True:
    @router.post("/auth", status_code=status.HTTP_201_CREATED)
    async def create_admin(create_admin_request: CreateAdminRequest, db: db_dependency):

        existing_admin = db.query(Admin).first()

        if existing_admin:
            raise HTTPException(
                status_code=400,
                detail="Admin already exists"
            )

        hashed_password = hash_password(create_admin_request.password)

        new_admin = Admin(
            name=create_admin_request.name,
            email=create_admin_request.email,
            hashed_password=hashed_password
        )

        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)

        return {"message": "Admin created successfully"}


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: db_dependency
):
    user = authenticate_admin(form_data.username, form_data.password, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    token = create_access_token(
        user.name,
        user.id,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


async def get_current_user(
    token: Annotated[str, Depends(oauth2_bearer)],
    db: db_dependency
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")

        if username is None or user_id is None:
            raise HTTPException(status_code=401, detail="Could not validate user")

    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate user")

    user = db.query(Admin).filter(Admin.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user

