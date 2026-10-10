
"""
BrandShield AI - App Detection Engine
Member 3: App Detection & Clustering

Contract interface:
    evaluate(brand: dict, candidate: dict) -> dict

This engine produces explainable signals.
Final risk scoring and status are handled by score_engine.combine().
"""

import unicodedata

from rapidfuzz import fuzz

from normalization import (
    normalize_package_id,
    normalize_contact_number,
    normalize_redirect_url,
)


# --------------------------------------------------
# TEXT NORMALIZATION
# --------------------------------------------------

def normalize_text(value):
    """Normalize text for comparisons. Missing values become empty strings."""
    if value is None:
        return ""

    value = unicodedata.normalize("NFKC", str(value))
    value = value.casefold()
    return " ".join(value.split())


# --------------------------------------------------
# SIMILARITY HELPERS
# --------------------------------------------------

def similarity(value_a, value_b):
    """Return normalized similarity from 0.0 to 1.0, or None if missing."""
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
    """Return registered official apps for the candidate platform."""
    official_apps = brand.get("official_apps") or []

    return [
        item
        for item in official_apps
        if isinstance(item, dict)
        and item.get("platform") == platform
    ]


def is_registered_official_package(package_id, official_apps):
    """Check for an exact normalized registered package ID."""
    normalized_package = normalize_package_id(package_id)

    if not normalized_package:
        return False

    for official_app in official_apps:
        registered_package = normalize_package_id(
            official_app.get("package_id")
        )

        if (
            registered_package is not None
            and normalized_package == registered_package
        ):
            return True

    return False


# --------------------------------------------------
# CONTRACT ENGINE INTERFACE
# --------------------------------------------------

def evaluate(brand: dict, candidate: dict) -> dict:
    """
    Evaluate an app listing against a brand registry entry.

    Returns explainable signals, evidence and normalized clustering
    indicators. Does not calculate the final risk score or status.
    """

    entity_id = candidate.get("entity_id")
    platform = candidate.get("platform")
    package_id = candidate.get("package_id")
    app_name = candidate.get("app_name")
    publisher = candidate.get("publisher")
    description = candidate.get("description")

    official_apps = find_official_apps(brand, platform)

    # Official matching takes priority over risk scoring.
    is_official = is_registered_official_package(
        package_id,
        official_apps,
    )

    exclusion_reason = (
        "Exact registered official package ID match"
        if is_official
        else None
    )

    # Identity signals
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

    # Content signals
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

        if found_phrases:
            credential_bait_reason = (
                "Description contains configured credential-related phrases: "
                + ", ".join(found_phrases)
            )
        else:
            credential_bait_reason = (
                "No configured credential-bait phrase detected."
            )

    # Publisher metadata signal
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
        publisher_reason = (
            "Publisher matches a registered official publisher."
        )
    else:
        publisher_mismatch = 1.0
        publisher_reason = (
            "Publisher does not match a registered official publisher."
        )

    # Contract-defined signals
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

    # Evidence for downstream reporting
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
    """Compatibility wrapper for older callers."""
    candidate = dict(app)

    if "entity_id" not in candidate:
        candidate["entity_id"] = candidate.get("app_id")

    if "app_name" not in candidate:
        candidate["app_name"] = candidate.get("name")

    candidate.setdefault("target_type", "app_listing")
    candidate.setdefault("evidence_source", "simulated")

    engine_output = evaluate(brand, candidate)

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
