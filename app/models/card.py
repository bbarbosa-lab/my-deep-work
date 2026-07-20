from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, ForeignKey, Boolean, Float, Text, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


card_labels = Table(
    "card_labels",
    Base.metadata,
    Column("card_id", Integer, ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", Integer, ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("lists.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[float] = mapped_column(Float, default=0.0)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    list = relationship("BoardList", back_populates="cards")
    labels = relationship("Label", secondary=card_labels, lazy="joined")
    members = relationship(
        "CardMember",
        back_populates="card",
        cascade="all, delete-orphan",
    )
    checklists = relationship(
        "Checklist",
        back_populates="card",
        cascade="all, delete-orphan",
    )
    comments = relationship(
        "Comment",
        back_populates="card",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )


class CardMember(Base):
    __tablename__ = "card_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    card = relationship("Card", back_populates="members")


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), default="Checklist")
    position: Mapped[float] = mapped_column(Float, default=0.0)

    card = relationship("Card", back_populates="checklists")
    items = relationship(
        "ChecklistItem",
        back_populates="checklist",
        cascade="all, delete-orphan",
        order_by="ChecklistItem.position",
    )


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[float] = mapped_column(Float, default=0.0)

    checklist = relationship("Checklist", back_populates="items")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    card = relationship("Card", back_populates="comments")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
