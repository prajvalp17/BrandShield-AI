
"""
BrandShield AI - App Detection Engine
Member 3: App Detection & Clustering

Implements the CONTRACT.md engine interface:
    evaluate(brand: dict, candidate: dict) -> dict

This engine produces explainable signals. It does not calculate the
final risk score or status; score_engine.combine() owns those decisions.

Normalization helpers in this file are temporary until Member 2's
shared normalization module is available and its interfaces are confirmed.
"""

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from rapidfuzz import fuzz


# --------------------------------------------------
# TEMPORARY NORMALIZATION HELPERS
# Replace with Member 2's shared helpers when available.
# --------------------------------------------------

def normalize_text(value):
    """Normalize text for comparisons. Missing values become empty strings."""
    if value is None:
        return ""

    value = unicodedata.normalize("NFKC", str(value))
    value = value.casefold()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_identifier(value):
    """Provisional normalization for package identifiers."""
    return normalize_text(value)


def normalize_contact_number(value):
    """
    Provisional contact normalization.

    Removes formatting characters but does not guess country codes or
    discard digits. Replace with the agreed shared helper from Member 2.
    """
    if value is None or not str(value).strip():
        return None

    digits = re.sub(r"\D", "", str(value))
    return digits or None


def normalize_redirect_url(value):
    """
    Normalize URL scheme and hostname while preserving the full path,
    query, and fragment. Domain-only matching is not performed.

    Replace with Member 2's shared URL normalizer once available.
    """
    if value is None or not str(value).strip():
        return None

    raw = str(value).strip()

    # Allow URLs supplied without an explicit scheme.
    if "://" not in raw:
        raw = "https://" + raw

    try:
        parsed = urlsplit(raw)

        if not parsed.hostname:
            return None

        scheme = parsed.scheme.casefold()
        hostname = parsed.hostname.casefold()

        try:
            port = parsed.port
        except ValueError:
            return None

        if port is not None:
            is_default_port = (
                (scheme == "https" and port == 443)
                or (scheme == "http" and port == 80)
            )
            if not is_default_port:
                hostname = f"{hostname}:{port}"

        # Preserve path, query, and fragment.
        return urlunsplit(
            (
                scheme,
                hostname,
                parsed.path or "/",
                parsed.query,
                parsed.fragment,
            )
        )

    except (ValueError, TypeError):
        return None


# --------------------------------------------------
# SIMILARITY HELPERS
# --------------------------------------------------

def similarity(value_a, value_b):
    """
    Return normalized similarity from 0.0 to 1.0.

    Return None if either input is missing. Similarity is a heuristic,
    not a probability that an app is malicious.
    """
    a = normalize_text(value_a)
    b = normalize_text(value_b)

    if not a or not b:
        return None

    return round(fuzz.ratio(a, b) / 100.0, 4)


def best_similarity(value, official_values):
    """Return the highest similarity to available official values."""
    scores = [
        similarity(value, official)
        for official in official_values
    ]

    scores = [score for score in scores if score is not None]
    return max(scores) if scores else None


def make_signal(value, category, reason):
    """Create a signal record matching CONTRACT.md."""
    return {
        "value": value,
        "category": category,
        "reason": reason,
    }


# --------------------------------------------------
# OFFICIAL APP MATCHING
# --------------------------------------------------

def find_official_apps(brand, platform):
    """
    Return registered official app records for the candidate platform.

    Contract registry format:
        official_apps: [
            {
                "platform": "Android",
                "package_id": "com.example.app",
                "publisher": "Example Ltd"
            }
        ]
    """
    official_apps = brand.get("official_apps") or []

    return [
        item
        for item in official_apps
        if isinstance(item, dict)
        and item.get("platform") == platform
    ]


def is_registered_official_package(package_id, official_apps):
    """Check for an exact normalized registered package ID."""
    normalized_package = normalize_identifier(package_id)

    if not normalized_package:
        return False

    for official_app in official_apps:
        registered_package = official_app.get("package_id")

        if not registered_package:
            continue

        if normalized_package == normalize_identifier(registered_package):
            return True

    return False


# --------------------------------------------------
# CONTRACT ENGINE INTERFACE
# --------------------------------------------------

def evaluate(brand: dict, candidate: dict) -> dict:
    """
    Evaluate an app listing against a brand registry entry.

    Required output fields:
        entity_id, target_type, platform, identifier,
        is_official, exclusion_reason, signals, evidence_source,
        evidence_timestamp, indicators, evidence

    The final risk score and status are calculated by Member 4.
    """

    entity_id = candidate.get("entity_id")
    platform = candidate.get("platform")
    package_id = candidate.get("package_id")
    app_name = candidate.get("app_name")
    publisher = candidate.get("publisher")
    description = candidate.get("description")

    official_apps = find_official_apps(brand, platform)

    # Official matching happens before scoring.
    is_official = is_registered_official_package(
        package_id,
        official_apps,
    )

    exclusion_reason = (
        "Exact registered official package ID match"
        if is_official
        else None
    )

    # --------------------------------------------------
    # Identity signals
    # --------------------------------------------------

    app_name_similarity = similarity(
        app_name,
        brand.get("name"),
    )

    official_package_ids = [
        item.get("package_id")
        for item in official_apps
        if item.get("package_id")
    ]

    package_similarity = best_similarity(
        package_id,
        official_package_ids,
    )

    # --------------------------------------------------
    # Content signals
    # --------------------------------------------------

    official_descriptions = brand.get("official_descriptions") or []

    description_similarity = best_similarity(
        description,
        official_descriptions,
    )

    credential_bait_phrases = (
        "verify your account",
        "enter your password",
        "enter otp",
        "one time password",
        "account suspended",
        "claim your reward",
        "confirm your credentials",
        "login to verify",
    )

    normalized_description = normalize_text(description)

    if not normalized_description:
        credential_bait = None
        credential_bait_reason = "Description is missing."
    else:
        found_phrases = [
            phrase
            for phrase in credential_bait_phrases
            if phrase in normalized_description
        ]

        credential_bait = 1.0 if found_phrases else 0.0

        credential_bait_reason = (
            "Description contains configured credential-related phrases: "
            + ", ".join(found_phrases)
            if found_phrases
            else "No configured credential-bait phrase detected."
        )

    # --------------------------------------------------
    # Publisher metadata signal
    # --------------------------------------------------

    registered_publishers = {
        normalize_text(item.get("publisher"))
        for item in official_apps
        if item.get("publisher")
    }

    normalized_publisher = normalize_text(publisher)

    if not normalized_publisher or not registered_publishers:
        publisher_mismatch = None
        publisher_reason = (
            "Publisher or registered publisher information is unavailable."
        )
    elif normalized_publisher in registered_publishers:
        publisher_mismatch = 0.0
        publisher_reason = "Publisher matches a registered official publisher."
    else:
        publisher_mismatch = 1.0
        publisher_reason = (
            "Publisher does not match a registered official publisher."
        )

    # --------------------------------------------------
    # Signals: names and categories must match CONTRACT.md
    # --------------------------------------------------

    signals = {
        "app_name_similarity": make_signal(
            app_name_similarity,
            "identity",
            (
                "Similarity between app name and registered brand name."
                if app_name_similarity is not None
                else "App name or brand name is missing."
            ),
        ),
        "package_similarity": make_signal(
            package_similarity,
            "identity",
            (
                "Similarity to a registered official package ID."
                if package_similarity is not None
                else "Package ID or official package IDs are unavailable."
            ),
        ),
        "description_similarity": make_signal(
            description_similarity,
            "content",
            (
                "Similarity to an official app description."
                if description_similarity is not None
                else "Description or official descriptions are unavailable."
            ),
        ),
        "credential_bait": make_signal(
            credential_bait,
            "content",
            credential_bait_reason,
        ),
        "publisher_mismatch": make_signal(
            publisher_mismatch,
            "metadata",
            publisher_reason,
        ),
    }

    # Evidence is for downstream reporting, not a final risk score.
    evidence = {
        "app_name": app_name,
        "package_id": package_id,
        "publisher": publisher,
        "description": description,
        "official_package_match": is_official,
    }

    return {
        "entity_id": entity_id,
        "target_type": "app_listing",
        "platform": platform,
        "identifier": package_id,
        "is_official": is_official,
        "exclusion_reason": exclusion_reason,
        "signals": signals,
        "evidence_source": candidate.get("evidence_source"),
        "evidence_timestamp": candidate.get("evidence_timestamp"),
        "indicators": {
            "contact_number": normalize_contact_number(
                candidate.get("contact_number")
            ),
            "redirect_url": normalize_redirect_url(
                candidate.get("redirect_url")
            ),
        },
        "evidence": evidence,
    }


# --------------------------------------------------
# LEGACY COMPATIBILITY
# --------------------------------------------------

def detect_app(app, brand):
    """
    Legacy interface retained temporarily for older tests or callers.

    New contract integrations must use evaluate(brand, candidate).
    This wrapper is not the team's final scoring implementation.
    """
    candidate = dict(app)

    # Translate the old field names into contract field names.
    if "entity_id" not in candidate:
        candidate["entity_id"] = candidate.get("app_id")

    if "app_name" not in candidate:
        candidate["app_name"] = candidate.get("name")

    if "target_type" not in candidate:
        candidate["target_type"] = "app_listing"

    if "evidence_source" not in candidate:
        candidate["evidence_source"] = "simulated"

    engine_output = evaluate(brand, candidate)

    # Compatibility summary only. Do not use this for the new evaluator.
    legacy_signals = {
        name: record["value"]
        for name, record in engine_output["signals"].items()
    }

    return {
        "app_id": candidate.get("app_id", candidate.get("entity_id")),
        "risk_score": None,
        "risk_level": "unscored",
        "classification": (
            "official" if engine_output["is_official"] else "unscored"
        ),
        "signals": legacy_signals,
        "reasons": [
            record["reason"]
            for record in engine_output["signals"].values()
            if record["reason"]
        ],
        "engine_output": engine_output,
    }


def detect_apps(apps, brand):
    """Legacy batch wrapper; new integrations should call evaluate()."""
    return [detect_app(app, brand) for app in apps]
