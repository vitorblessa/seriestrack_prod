"""Pydantic request schemas — kept tiny and grouped here for visibility."""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class LibraryUpsertIn(BaseModel):
    tmdb_id: int
    status: str = Field(pattern="^(watching|paused|finished|want)$")
    name: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    overview: Optional[str] = None


class ProgressIn(BaseModel):
    tmdb_id: int
    season: int
    episode: int
    watched: bool = True


class ProgressBulkIn(BaseModel):
    tmdb_id: int
    season: int
    watched: bool = True


class GoogleCallbackIn(BaseModel):
    credential: str  # Google ID token (JWT) from Google Identity Services


class ReviewIn(BaseModel):
    tmdb_id: int
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class PushKeysIn(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: PushKeysIn


class CheckoutIn(BaseModel):
    plan: str
    origin_url: str
