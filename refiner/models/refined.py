from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, JSON, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ---------- 1. Pseudonymised users ----------
class UserPseudo(Base):
    __tablename__ = "users"

    pseudo_id = Column(String(64), primary_key=True)  # salted SHA-256 hash

    messages = relationship(
        "Message",
        foreign_keys="[Message.from_pseudo_id]",
        back_populates="author"
    )
    forwarded_messages = relationship(
        "Message",
        foreign_keys="[Message.forwarded_from_pseudo_id]",
        back_populates="forwarded_from_author"
    )

# ---------- 2. Chats ----------
class Chat(Base):
    __tablename__ = "chats"

    chat_id         = Column(Integer, primary_key=True, autoincrement=True)
    tg_chat_id      = Column(Integer, nullable=False, index=True) 
    name            = Column(Text, nullable=True)
    character_slug  = Column(String, nullable=True)
    character_level = Column(Integer, nullable=True)
    uploader_id     = Column(String(64), nullable=True)  # hashed uploader ID
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    messages = relationship("Message", back_populates="chat")

# ---------- 3. Messages ----------
class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("chat_id", "message_id", name="uq_chat_message"),
    )

    message_rowid   = Column(Integer, primary_key=True, autoincrement=True)
    chat_id         = Column(Integer, ForeignKey("chats.chat_id"), nullable=False)
    message_id      = Column(Integer, nullable=False)  # original TG message ID
    type            = Column(String, nullable=False)
    date_iso        = Column(String, nullable=False)   # ISO 8601 timestamp
    date_unixtime   = Column(Integer, nullable=True)
    edited_at_iso   = Column(String, nullable=True)    # ISO 8601 timestamp
    reply_to_id     = Column(Integer, nullable=True)
    media_type      = Column(String, nullable=True)
    mime_type       = Column(String, nullable=True)
    duration_s      = Column(Integer, nullable=True)

    from_pseudo_id  = Column(String(64), ForeignKey("users.pseudo_id"), nullable=True)
    forwarded_from_pseudo_id = Column(String(64), ForeignKey("users.pseudo_id"), nullable=True)

    text_raw        = Column(Text, nullable=True)      # PII-scrubbed text
    content_json    = Column(JSON, nullable=True)      # media & weird edge fields

    chat    = relationship("Chat", back_populates="messages")
    author  = relationship(
        "UserPseudo",
        foreign_keys=[from_pseudo_id],
        back_populates="messages"
    )
    forwarded_from_author = relationship(
        "UserPseudo",
        foreign_keys=[forwarded_from_pseudo_id],
        back_populates="forwarded_messages"
    )
    entities = relationship("MessageEntity", back_populates="message",
                            cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="message",
                             cascade="all, delete-orphan")

# ---------- 4. Message entities ----------
class MessageEntity(Base):
    __tablename__ = "message_entities"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    message_id   = Column(Integer, ForeignKey("messages.message_rowid"), nullable=False)
    entity_type  = Column(String, nullable=False)
    entity_text  = Column(Text, nullable=False)

    message = relationship("Message", back_populates="entities")

# ---------- 5. Reactions ----------
class Reaction(Base):
    __tablename__ = "reactions"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    message_id  = Column(Integer, ForeignKey("messages.message_rowid"), nullable=False)
    emoji       = Column(String, nullable=False)
    count       = Column(Integer, nullable=False)

    message = relationship("Message", back_populates="reactions")
