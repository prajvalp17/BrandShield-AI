import unicodedata
import re

def normalize_package_id(value: object) -> str | None:
    """Trim and standardize a package ID while preserving dots and hyphens."""
    if value is None:
        return None

    package_id = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    return package_id or None


def normalize_contact_number(value: object) -> str | None:
    """Remove formatting from a phone number, keeping its digits."""
    if value is None:
        return None

    text = unicodedata.normalize("NFKC", str(value))
    digits = re.sub(r"\D", "", text)
    return digits or None


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
