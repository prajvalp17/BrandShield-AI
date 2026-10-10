"""Social-profile signals for BrandShield AI.

This module returns evidence signals only. It does not calculate risk scores
or decide FLAGGED / NOT_FLAGGED status.
"""
from rapidfuzz.fuzz import ratio
from normalization import (
    normalize_contact_number,
    normalize_identifier,
    normalize_redirect_url,
    normalize_text,
)


SCAM_PHRASES = (
    "verify your account",
    "dm us",
    "claim your prize",
    "account suspended",
    "click the link",
    "send your password",
    "verify your identity",
    "confirm your account",
    "account verification",
    "reset your password",
    "send us your password",
    "claim your reward",
    "you have won",
    "free giveaway",
    "urgent action required",
    "dm to claim",
    "send payment",
    "make a payment",
    "payment required",
    "send your otp",
    "share your otp",
    "send the verification code",
    "share the verification code",
    "pay a processing fee",
    "processing fee",
    "pay a release fee",
)


def _signal(value, category, reason):
    """Create one signal record in the contract format."""
    return {
        "value": value,
        "category": category,
        "reason": reason,
    }


def _similarity(first, second):
    """Return text similarity from 0.0 to 1.0, or None if unavailable."""
    first_text = normalize_text(first)
    second_text = normalize_text(second)

    if first_text is None or second_text is None:
        return None

    return round(ratio(first_text, second_text) / 100.0, 3)


def evaluate(brand: dict, candidate: dict) -> dict:
    """Return social-profile signals and evidence for one candidate."""
    entity_id = candidate["entity_id"]
    platform = candidate["platform"]
    username = candidate["username"]
    display_name = candidate.get("display_name")
    bio = candidate.get("bio")

    # Check whether the username exactly matches an official handle
    # registered for this platform.
    official_handles = brand.get("official_handles", {}).get(platform, [])
    normalized_username = normalize_identifier(username)
    is_official = normalized_username is not None and any(
        normalized_username == normalize_identifier(handle)
        for handle in official_handles
    )

    if is_official:
        exclusion_reason = "Username exactly matches a registered official handle."
        signals = {}
    else:
        exclusion_reason = None

        # Compare the username against this brand's official handles.
        handle_scores = [
            _similarity(username, handle)
            for handle in official_handles
        ]
        handle_scores = [score for score in handle_scores if score is not None]
        handle_similarity = max(handle_scores) if handle_scores else None

        # Compare the candidate's display name against the registered brand name.
        name_similarity = _similarity(display_name, brand.get("name"))

        # Scam phrase signal: 1.0 if a phrase is present, otherwise 0.0.
        normalized_bio = normalize_text(bio)
        matched_phrases = [
            phrase for phrase in SCAM_PHRASES
            if normalized_bio is not None and phrase in normalized_bio
        ]
        if normalized_bio is None:
            scam_phrase = None
            scam_reason = "Bio is unknown."
        elif matched_phrases:
            scam_phrase = 1.0
            scam_reason = "Matched phrases: " + ", ".join(matched_phrases)
        else:
            scam_phrase = 0.0
            scam_reason = "No listed scam phrase found."

        # Young accounts receive higher age signals; missing age stays unknown.
        age = candidate.get("account_age_days")
        if age is None:
            account_age = None
            age_reason = "Account age is unknown."
        elif age <= 14:
            account_age = 0.9
            age_reason = "Account is 14 days old or newer."
        elif age <= 90:
            account_age = 0.5
            age_reason = "Account is between 15 and 90 days old."
        else:
            account_age = 0.0
            age_reason = "Account is older than 90 days."

        signals = {
            "handle_similarity": _signal(
                handle_similarity,
                "identity",
                "Similarity to a registered official handle."
                if handle_similarity is not None else "No official handle to compare.",
            ),
            "name_similarity": _signal(
                name_similarity,
                "identity",
                "Similarity between the display name and brand name."
                if name_similarity is not None else "Display name or brand name is unavailable.",
            ),
            "scam_phrase": _signal(
                scam_phrase,
                "content",
                "Matched phrases: " + ", ".join(matched_phrases)
                if matched_phrases else "No listed scam phrase found.",
            ),
            "account_age": _signal(account_age, "metadata", age_reason),
        }

    return {
        "entity_id": entity_id,
        "target_type": candidate["target_type"],
        "platform": platform,
        "identifier": username,
        "is_official": is_official,
        "exclusion_reason": exclusion_reason,
        "signals": signals,
        "evidence_source": candidate["evidence_source"],
        "evidence_timestamp": candidate.get("evidence_timestamp"),
        "indicators": {
           "contact_number": normalize_contact_number(candidate.get("contact_number")),
"redirect_url": normalize_redirect_url(candidate.get("redirect_url")),
        },
        "evidence": {
            "display_name": display_name,
            "username": username,
            "matched_scam_phrases": matched_phrases if not is_official else [],
        },
    }