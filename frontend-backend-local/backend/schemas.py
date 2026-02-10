from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str
    is_verified: bool
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'

class TokenPayload(BaseModel):
    sub: str
    exp: int
    role: Optional[str]

class ScholarshipCreate(BaseModel):
    title: str
    provider: str
    type: str
    link: Optional[str] = None
    amount: Optional[str] = None
    deadline: Optional[str] = None
    description: Optional[str] = None

class ScholarshipOut(ScholarshipCreate):
    id: int
    created_by: Optional[int]
    created_at: Optional[datetime]
    class Config:
        from_attributes = True
