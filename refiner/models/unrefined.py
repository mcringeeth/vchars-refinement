from typing import Optional, Union, List, Any
from pydantic import BaseModel, Field


class TextEntity(BaseModel):
    type: str
    text: str


class ReactionRecent(BaseModel):
    from_: str = Field(..., alias="from")
    from_id: str
    date: str


class Reaction(BaseModel):
    type: str
    count: int
    emoji: str
    recent: List[ReactionRecent]


class Message(BaseModel):
    id: Optional[int] = None
    type: str
    date: str
    date_unixtime: Optional[str] = None
    from_: str = Field(..., alias="from")
    from_id: Optional[str] = None
    text: Union[str, List[TextEntity]]
    text_entities: Optional[List[TextEntity]] = None
    edited: Optional[str] = None
    edited_unixtime: Optional[str] = None
    reply_to_message_id: Optional[int] = None
    forwarded_from: Optional[str] = None
    photo: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file: Optional[str] = None
    file_name: Optional[str] = None
    thumbnail: Optional[str] = None
    media_type: Optional[str] = None
    mime_type: Optional[str] = None
    duration_seconds: Optional[int] = None
    reactions: Optional[List[Reaction]] = None


class Chat(BaseModel):
    name: Optional[str] = None
    type: str
    id: Optional[int] = None
    character_slug: Optional[str] = None
    character_level: Optional[int] = None
    uploader_tg_id: Optional[int] = None
    messages: List[Message]