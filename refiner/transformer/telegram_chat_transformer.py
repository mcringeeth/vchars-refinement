from typing import Dict, Any, List
from sqlalchemy.orm import Session
import logging

from refiner.transformer.base_transformer import DataTransformer
from refiner.config import settings
from refiner.models.refined import (
    Base,
    Chat,
    Message,
    MessageEntity,
    Reaction,
    UserPseudo,
)
from refiner.models.unrefined import Chat as RawChat    
from refiner.utils.date import _iso
from refiner.utils.other import _to_int
from refiner.utils.encrypt import hash_id
from refiner.utils.pii import scrub_text_advanced
from pydantic import ValidationError


class TelegramChatTransformer(DataTransformer):
    """
    Transforms ONE Telegram chat dump into the refined DB schema.
    Always produces *pseudonymised / refined* output
    """

    def __init__(self, db_path: str):
        super().__init__(db_path)

    # ------------- public API ------------------------------------------------

    def transform(self, data: Dict[str, Any], session: Session) -> None:
        """
        Args:
            data: raw JSON of ONE Telegram chat (dict)
        Returns:
            list of SQLAlchemy model instances ready to add()
        """
        # --- Parse and Validate ---
        try:
            raw_chat: RawChat = RawChat.parse_obj(data)
        except ValidationError as e:
            logging.error(f"Failed to parse chat data: {e}")
            raise

        # --- 1. Chat ---------------------------------------------------------
        chat_row = Chat(
            tg_chat_id      = raw_chat.id,
            name            = hash_id(raw_chat.name, settings.HASH_SALT),
            character_slug  = raw_chat.character_slug,
            character_level = raw_chat.character_level,
            uploader_id     = hash_id(raw_chat.uploader_tg_id, settings.HASH_SALT),
            # created_at auto-fills
        )
        session.add(chat_row)
        session.flush()          # get chat_row.chat_id

        # --- 2. Users cache (to avoid dup inserts) ---------------------------
        user_cache: set[str] = set()

        # --- 3. Loop messages ------------------------------------------------
        for m in raw_chat.messages:
            # Author hash
            from_hash = hash_id(m.from_id, settings.HASH_SALT)
            if from_hash and from_hash not in user_cache:
                session.merge(UserPseudo(pseudo_id=from_hash))
                user_cache.add(from_hash)

            # Forwarded-from hash
            forwarded_from_hash = None
            if m.forwarded_from:
                forwarded_from_hash = hash_id(m.forwarded_from, settings.HASH_SALT)
                if forwarded_from_hash and forwarded_from_hash not in user_cache:
                    session.merge(UserPseudo(pseudo_id=forwarded_from_hash))
                    user_cache.add(forwarded_from_hash)

            # Scrub message text
            if isinstance(m.text, str):
                text_out = scrub_text_advanced(m.text)
            else:
                text_parts = []
                if m.text:
                    for t in m.text:
                        if isinstance(t, str):
                            text_parts.append(t)
                        elif hasattr(t, 'text'):
                            text_parts.append(t.text)
                text_out = scrub_text_advanced("".join(text_parts))

            # Keep "junk drawer" JSON for media etc.
            content = {
                k: v for k, v in m.dict().items()
                if k not in ["text", "text_entities", "id"]
            }
            # Remove file name from content if it exists
            content.pop("file_name", None)

            msg_row = Message(
                chat_id        = chat_row.chat_id,
                message_id     = m.id or 0,
                type           = m.type,
                date_iso       = _iso(m.date),
                date_unixtime  = _to_int(m.date_unixtime),
                edited_at_iso  = _iso(m.edited),
                reply_to_id    = m.reply_to_message_id,
                media_type     = m.media_type,
                mime_type      = m.mime_type,
                duration_s     = m.duration_seconds,
                from_pseudo_id = from_hash,
                forwarded_from_pseudo_id = forwarded_from_hash,
                text_raw       = text_out,
                content_json   = content or None,
            )
            session.add(msg_row)
            session.flush()      # need message_rowid for children

            # ---- text entities ---------------------------------------------
            for te in m.text_entities or []:
                ent = MessageEntity(
                    message_id  = msg_row.message_rowid,
                    entity_type = te.type,
                    entity_text = scrub_text_advanced(te.text),
                )
                session.add(ent)

            # ---- reactions (ignore recent list for privacy) ----------------
            for rx in m.reactions or []:
                react = Reaction(
                    message_id = msg_row.message_rowid,
                    emoji      = rx.emoji,
                    count      = rx.count,
                )
                session.add(react)

        # Flush but don't commit; caller's process() will handle commit/rollback
        session.flush()
