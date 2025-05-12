from typing import Dict, Any, List
from sqlalchemy.orm import Session

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
from refiner.utils.encrypt import hash_id, scrub_text


class TelegramChatTransformer(DataTransformer):
    """
    Transforms ONE Telegram chat dump into the refined DB schema.
    Always produces *pseudonymised / refined* output
    """

    def __init__(self, db_path: str):
        super().__init__(db_path)

    # ------------- public API ------------------------------------------------

    def transform(self, data: Dict[str, Any]) -> List[Base]:
        """
        Args:
            data: raw JSON of ONE Telegram chat (dict)
        Returns:
            list of SQLAlchemy model instances ready to add()
        """
        raw_chat: RawChat = RawChat.model_validate(data)

        session: Session = self.Session()        # temp session for de-dup
        models: List[Base] = []

        # --- 1. Chat ---------------------------------------------------------
        chat_row = Chat(
            tg_chat_id      = raw_chat.id,
            name            = raw_chat.name,
            character_slug  = raw_chat.character_slug,
            character_level = raw_chat.character_level,
            uploader_id     = hash_id(raw_chat.uploader_tg_id, settings.HASH_SALT),
            # created_at auto-fills
        )
        models.append(chat_row)
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

            # Scrub message text
            if isinstance(m.text, str):
                text_out = scrub_text(m.text)
            else:
                text_out = scrub_text(" ".join(t.text for t in m.text))

            # Keep “junk drawer” JSON for media etc.
            content = {
                k: v for k, v in m.model_dump().items()
                if k not in {
                    "id", "type", "date", "date_unixtime", "from_id", "from",
                    "text", "text_entities", "reactions", "reply_to_message_id",
                    "media_type", "mime_type", "duration_seconds"
                } and v is not None
            }

            msg_row = Message(
                chat_id        = chat_row.chat_id,
                message_id     = m.id or 0,
                type           = m.type,
                date_iso       = _iso(m.date),
                date_unixtime  = _to_int(m.date_unixtime),
                reply_to_id    = m.reply_to_message_id,
                media_type     = m.media_type,
                mime_type      = m.mime_type,
                duration_s     = m.duration_seconds,
                from_pseudo_id = from_hash,
                text_raw       = text_out,
                content_json   = content or None,
            )
            models.append(msg_row)
            session.add(msg_row)
            session.flush()      # need message_rowid for children

            # ---- text entities ---------------------------------------------
            for te in m.text_entities or []:
                ent = MessageEntity(
                    message_id  = msg_row.message_rowid,
                    entity_type = te.type,
                    entity_text = scrub_text(te.text),
                )
                models.append(ent)
                session.add(ent)

            # ---- reactions (ignore recent list for privacy) ----------------
            for rx in m.reactions or []:
                react = Reaction(
                    message_id = msg_row.message_rowid,
                    emoji      = rx.emoji,
                    count      = rx.count,
                )
                models.append(react)
                session.add(react)

        # Flush but don’t commit; caller’s process() will handle commit/rollback
        session.flush()
        session.close()
        return models
