import re
import spacy
from functools import lru_cache
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# Ensure consistent detection results for testing
DetectorFactory.seed = 0

# --- Pre-load NLP models ---
# Use a cache to avoid reloading models constantly
@lru_cache(maxsize=None)
def _get_nlp(model_name: str):
    try:
        return spacy.load(model_name)
    except OSError:
        print(f"Downloading '{model_name}'...")
        from spacy.cli import download
        download(model_name)
        return spacy.load(model_name)

# --- Regex for common PII ---
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d{1,3})?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,9}")
URL_RE = re.compile(r"https?://\S*[a-zA-Z0-9/]")
TELEGRAM_USERNAME_RE = re.compile(r'(?<!\w)@(\w{5,32})(?!\w)')

# This regex looks for two capitalized Cyrillic words in a row.
CYRILLIC_NAME_RE = re.compile(r'\b([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\b')

# --- Scrubbing Functions ---
def scrub_emails(text: str) -> str:
    """Scrubs emails from text."""
    return EMAIL_RE.sub("[EMAIL]", text) if text else text

def scrub_phones(text: str) -> str:
    """Scrubs phone numbers from text."""
    return PHONE_RE.sub("[PHONE]", text) if text else text

def scrub_urls(text: str) -> str:
    """Scrubs URLs from text."""
    return URL_RE.sub("[URL]", text) if text else text

def scrub_telegram_username(text: str) -> str:
    """Scrubs telegram usernames from text."""
    return TELEGRAM_USERNAME_RE.sub("[TG_USERNAME]", text) if text else text

def scrub_text_advanced(text: str) -> str:
    """
    Scrubs PII from text. It uses a targeted regex for cyrillic names first,
    then falls back to spaCy for other languages.
    """
    if not text or not isinstance(text, str):
        return text

    # First, always scrub common patterns
    text = scrub_emails(text)
    text = scrub_phones(text)
    text = scrub_urls(text)
    text = scrub_telegram_username(text)

    # The most reliable method is to check for the specific cyrillic name
    # pattern first, as langdetect can be fooled by mixed-language text.
    if CYRILLIC_NAME_RE.search(text):
        return CYRILLIC_NAME_RE.sub("[PERSON] [PERSON]", text)

    # If no cyrillic names are found, proceed with the standard NLP approach
    try:
        lang = detect(text)
    except LangDetectException:
        lang = "en"

    nlp = _get_nlp("en_core_web_sm") if lang == "en" else _get_nlp("xx_ent_wiki_sm")
    
    doc = nlp(text)
    
    tokens_to_redact = []
    for ent in doc.ents:
        if ent.label_ in ["PERSON", "PER", "GPE", "LOC"]:
            tokens_to_redact.extend(ent)
            
    for token in sorted(tokens_to_redact, key=lambda t: t.idx, reverse=True):
        label = "PERSON" if token.ent_type_ in ["PERSON", "PER"] else "LOCATION"
        text = text[:token.idx] + f"[{label}]" + text[token.idx + len(token.text):]
            
    return text

def mask_email(email: str) -> str:
    """
    Creates a masked, non-identifiable version of an email address.
    Example: "test.email@example.com" -> "t***l@e***e.com"
    """
    if not email or "@" not in email:
        return ""
        
    local, domain = email.split('@', 1)
    
    masked_local = f"{local[0]}***{local[-1]}" if len(local) > 2 else f"{local[0]}***"
    
    domain_parts = domain.split('.')
    if len(domain_parts) > 1:
        main_domain, tld = domain_parts[0], '.'.join(domain_parts[1:])
        masked_domain = f"{main_domain[0]}***{main_domain[-1]}" if len(main_domain) > 2 else f"{main_domain[0]}***"
        masked_full_domain = f"{masked_domain}.{tld}"
    else:
        masked_full_domain = f"{domain[0]}***"

    return f"{masked_local}@{masked_full_domain}" 