import unicodedata
import re

def normalize_text(value: object) -> str | None:
    """Normalize text for case-insensitive comparisons."""
    if value is None:
        return None

    text = unicodedata.normalize("NFKC", str(value))
    text = " ".join(text.casefold().split())
    return text or None


def normalize_identifier(value: object) -> str | None:
    """Normalize a handle or other identifier for exact comparisons."""
    text = normalize_text(value)
    if text is None:
        return None

    # Handles may be stored with or without one leading @.
    if text.startswith("@"):
        text = text[1:].strip()

    return text or None

def normalize_package_id(value: object) -> str | None:
    """Trim and standardize a package ID while preserving dots and hyphens."""
    if value is None:
        return None

    package_id = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    return package_id or None



def normalize_contact_number(value: object) -> str | None:
    if value is None:
        return None

    text = unicodedata.normalize("NFKC", str(value))
    digits = re.sub(r"\D", "", text)

    if len(digits) < 10:
        return None

    return digits[-10:]




    if len(digits) < 10:
        return None

    return digits[-10:]

def normalize_redirect_url(value: object) -> str | None:
    """Lowercase the URL's scheme and host while preserving its full path."""
    from urllib.parse import urlsplit, urlunsplit

    if value is None:
        return None

    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text:
        return None

    has_scheme = "://" in text
    parts = urlsplit(text if has_scheme else f"//{text}")

    if not parts.netloc:
        return None

    normalized_netloc = parts.netloc.casefold()

    if has_scheme:
        return urlunsplit((
            parts.scheme.casefold(),
            normalized_netloc,
            parts.path,
            parts.query,
            parts.fragment,
        ))

    return urlunsplit((
        "",
        normalized_netloc,
        parts.path,
        parts.query,
        parts.fragment,
    )).lstrip("/")