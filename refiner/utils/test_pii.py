import unittest
import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import re

from refiner.utils.pii import scrub_text_advanced
from refiner.transformer.telegram_chat_transformer import TelegramChatTransformer
from refiner.config import settings
from refiner.models import refined


class TestPIIScrubbing(unittest.TestCase):

    def test_scrubbing_all_pii_types(self):
        """
        Tests that the advanced scrubber correctly redacts names, emails,
        phone numbers, locations, and URLs.
        """
        input_text = "Hello, my name is John Doe. You can email me at john.doe@example.com or call (123) 456-7890. I live in New York. You can see my project at https://example.com."
        expected_text = "Hello, my name is [PERSON] [PERSON]. You can email me at [EMAIL] or call [PHONE]. I live in [LOCATION] [LOCATION]. You can see my project at [URL]."
        
        scrubbed_text = scrub_text_advanced(input_text)
        self.assertEqual(scrubbed_text, expected_text)

    def test_scrubbing_with_no_pii(self):
        """
        Tests that text with no PII remains unchanged.
        """
        # Arrange
        sample_text = "This is a perfectly safe sentence with no sensitive information."
        
        # Act
        scrubbed_text = scrub_text_advanced(sample_text)

        # Assert
        self.assertEqual(scrubbed_text, sample_text)

    def test_scrubbing_complex_cyrillic_names(self):
        """
        Tests scrubbing on a real, complex example with cyrillic names and
        English job titles.
        """
        input_text = "Лайнап:\n• Альшун Джеферов – Blockchain Engineer at Ethereum\n• Дмитрий Климов – Core Developer at Blockscout\n• Антон Василенко – UX Designer & Researcher"
        
        # The logic now uses a direct regex replacement for cyrillic text.
        expected_text = "Лайнап:\n• [PERSON] [PERSON] – Blockchain Engineer at Ethereum\n• [PERSON] [PERSON] – Core Developer at Blockscout\n• [PERSON] [PERSON] – UX Designer & Researcher"
        
        scrubbed_text = scrub_text_advanced(input_text)
        self.assertEqual(scrubbed_text, expected_text)


@unittest.skipIf(os.environ.get("CI"), "Skipping full pipeline test in CI")
class TestFullPipelinePrivacy(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """
        Processes the input JSON file once for all tests in this class.
        Uses an in-memory SQLite DB for testing purposes.
        """
        # --- Setup in-memory DB and session ---
        cls.engine = create_engine('sqlite:///:memory:')
        refined.Base.metadata.create_all(cls.engine)
        Session = sessionmaker(bind=cls.engine)
        cls.session = Session()

        # --- Load input data ---
        # Construct path relative to this test file's location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
        input_path = os.path.join(project_root, 'input', 'result.json')
        with open(input_path, 'r') as f:
            cls.input_data = json.load(f)

        # --- Run the transformer ---
        # The transformer needs a db_path, but it's not used here
        # because we provide our own session.
        transformer = TelegramChatTransformer(db_path=":memory:")
        transformer.process(cls.input_data, session=cls.session)
        
        # --- Fetch the results for tests to use ---
        cls.chat_result = cls.session.query(refined.Chat).first()
        cls.messages_result = cls.session.query(refined.Message).all()

        # --- Save artifact for inspection ---
        output_dict = {
            "chat": {
                "tg_chat_id": cls.chat_result.tg_chat_id,
                "name_hash": cls.chat_result.name,
                "character_slug": cls.chat_result.character_slug
            },
            "messages": []
        }
        for msg in cls.messages_result:
            msg_dict = {
                "message_id": msg.message_id,
                "type": msg.type,
                "date_iso": msg.date_iso,
                "edited_at_iso": msg.edited_at_iso,
                "from_pseudo_id": msg.from_pseudo_id,
                "forwarded_from_pseudo_id": msg.forwarded_from_pseudo_id,
                "text_raw": msg.text_raw,
                "content_json": msg.content_json,
                "entities": [{"type": ent.entity_type, "text": ent.entity_text} for ent in msg.entities],
                "reactions": [{"emoji": rx.emoji, "count": rx.count} for rx in msg.reactions]
            }
            output_dict["messages"].append(msg_dict)
        
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'output')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_path = os.path.join(output_dir, 'test_refined_output.json')

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False)
        
        print(f"\n[INFO] Test artifact saved to {output_path}")

    def test_chat_name_is_hashed(self):
        """
        Verifies that the chat name is not stored in plaintext.
        """
        raw_chat_name = self.input_data.get('name')
        processed_chat_name = self.chat_result.name
        
        self.assertIsNotNone(processed_chat_name)
        self.assertNotEqual(raw_chat_name, processed_chat_name)
        # A SHA-256 hash is 64 hex characters
        self.assertEqual(len(processed_chat_name), 64)

    def test_message_text_is_scrubbed(self):
        """
        Verifies that PII is scrubbed from message text.
        Specifically checks that '@' symbols only appear as part of a
        [TG_USERNAME] tag, not in a raw email or username.
        """
        for message in self.messages_result:
            if message.text_raw and '@' in message.text_raw:
                # Find all occurrences of the '@' symbol
                for match in re.finditer(r'@', message.text_raw):
                    # Check the surrounding text to ensure it's part of our tag
                    start, end = match.start(), match.end()
                    # A bit of a fudge factor for where the @ is in the tag,
                    # but this should be robust enough.
                    context = message.text_raw[max(0, start-1):end+12]
                    self.assertIn('[TG_USERNAME]', context,
                                  f"Found a raw '@' that wasn't scrubbed in message: {message.text_raw}")

    def test_filename_is_removed(self):
        """
        Verifies that 'file_name' is not in the content_json blob.
        """
        for message in self.messages_result:
            if message.content_json and isinstance(message.content_json, dict):
                self.assertNotIn('file_name', message.content_json.keys())

    @classmethod
    def tearDownClass(cls):
        """Closes the session."""
        cls.session.close()


if __name__ == '__main__':
    # Before running, ensure you have installed the required dependencies:
    # .venv/bin/pip install -r requirements.txt
    # .venv/bin/python -m spacy download en_core_web_sm
    unittest.main() 