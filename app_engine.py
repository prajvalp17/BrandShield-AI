
"""
BrandShield AI - App Detection Engine
Member 3: App Detection

Contract interface:
    evaluate(brand: dict, candidate: dict) -> dict

This module generates explainable app-risk signals.
Final scoring and status assignment belong to score_engine.combine().
"""

import unicodedata

from rapidfuzz import fuzz

from normalization import (
    normalize_package_id,
    normalize_contact_number,
    normalize_redirect_url,
)


# --------------------------------------------------
# TEXT NORMALIZATION AND SIMILARITY
# --------------------------------------------------

def normalize_text(value):
    """Normalize text for comparison. Missing values become empty strings."""
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    return " ".join(text.casefold().split())


def similarity(value_a, value_b):
    """
    Return similarity between 0.0 and 1.0.
    Return None when either value is missing.
    """
    a = normalize_text(value_a)
    b = normalize_text(value_b)

    if not a or not b:
        return None

    return round(fuzz.ratio(a, b) / 100.0, 4)


def best_similarity(value, official_values):
    """Return the highest similarity to available official values."""
    if not isinstance(official_values, (list, tuple)):
        return None

    scores = [
        similarity(value, official_value)
        for official_value in official_values
    ]

    scores = [score for score in scores if score is not None]
    return max(scores) if scores else None


def make_signal(value, category, reason):
    """Create a signal record following the contract."""
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

    if not isinstance(official_apps, list):
        return []

    return [
        app
        for app in official_apps
        if isinstance(app, dict)
        and app.get("platform") == platform
    ]


def is_registered_official_package(package_id, official_apps):
    """
    Check for an exact normalized package ID match.
    Platform filtering is performed before this function is called.
    """
    normalized_package = normalize_package_id(package_id)

    if normalized_package is None:
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
# APP DETECTION ENGINE
# --------------------------------------------------

def evaluate(brand: dict, candidate: dict) -> dict:
    """
    Evaluate an app listing against a brand registry entry.

    Required output:
        entity_id, target_type, platform, identifier,
        is_official, exclusion_reason, signals,
        evidence_source, evidence_timestamp, indicators, evidence.

    This function does not calculate the final risk score or status.
    """

    entity_id = candidate.get("entity_id")
    platform = candidate.get("platform")
    package_id = candidate.get("package_id")
    app_name = candidate.get("app_name")
    publisher = candidate.get("publisher")
    description = candidate.get("description")

    official_apps = find_official_apps(brand, platform)

    # Official packages are identified before scoring.
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
    # IDENTITY SIGNALS
    # --------------------------------------------------

    app_name_similarity = similarity(
        app_name,
        brand.get("name"),
    )

    official_package_ids = [
        app.get("package_id")
        for app in official_apps
        if app.get("package_id")
    ]

    package_similarity = best_similarity(
        package_id,
        official_package_ids,
    )

    # --------------------------------------------------
    # CONTENT SIGNALS
    # --------------------------------------------------

    # Optional registry field introduced in contract v0.8.
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
                "Description contains configured credential-related "
                "phrases: " + ", ".join(found_phrases)
            )
        else:
            credential_bait_reason = (
                "No configured credential-bait phrase detected."
            )

    # --------------------------------------------------
    # PUBLISHER METADATA SIGNAL — CONTRACT v0.8
    # --------------------------------------------------

    # Optional registry field. Do not infer authorization from
    # official_apps when authorized_publishers is unavailable.
    authorized_publishers = brand.get("authorized_publishers") or []

    if not isinstance(authorized_publishers, (list, tuple)):
        authorized_publishers = []

    registered_publishers = {
        normalize_text(item)
        for item in authorized_publishers
        if item and normalize_text(item)
    }

    normalized_publisher = normalize_text(publisher)

    if not normalized_publisher or not registered_publishers:
        publisher_mismatch = None
        publisher_reason = (
            "Publisher or authorized publisher information is unavailable."
        )
    elif normalized_publisher in registered_publishers:
        publisher_mismatch = 0.0
        publisher_reason = (
            "Publisher matches a registered authorized publisher."
        )
    else:
        publisher_mismatch = 1.0
        publisher_reason = (
            "Publisher does not match a registered authorized publisher."
        )

    # --------------------------------------------------
    # SIGNALS
    # Names and categories must match the contract.
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
