from datetime import datetime, date
from typing import Any, Optional

from sqlalchemy import String, Integer, Float, Date, Text, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (UniqueConstraint("external_id", name="uq_properties_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    long_description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    price: Mapped[Optional[float]] = mapped_column(Float)
    listing_date: Mapped[Optional[date]] = mapped_column(Date)
    floorplan_image: Mapped[Optional[str]] = mapped_column(String(1024))
    seller_type: Mapped[Optional[str]] = mapped_column(String(64))
    seller_contact: Mapped[Optional[str]] = mapped_column(String(255))
    metadata_tags: Mapped[Optional[dict]] = mapped_column(JSONB)
    cert_links: Mapped[Optional[dict]] = mapped_column(JSONB)
    parsed_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer, index=True)
    role: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserMemory(Base):
    __tablename__ = "user_memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    data: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Shortlist(Base):
    __tablename__ = "shortlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    properties: Mapped[dict] = mapped_column(JSONB)  # {"ids": ["PROP-..."]}
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
