from rapidfuzz import fuzz

from normalization import normalize_identifier, normalize_text


SCAM_PHRASES = (
    "contact support",
    "claim your reward",
    "verify your account",
    "send otp",
    "dm us",
    "limited offer",
)


def analyze_social_profile(candidate: dict, brand: dict) -> dict:
    """Return social-profile signals and evidence; do not assign a risk score."""

    brand_name = brand.get("brand_name", "")
    profile_name = candidate.get("profile_name", "")
    handle = candidate.get("handle", "")
    bio = candidate.get("bio", "")
    account_age_days = candidate.get("account_age_days")

    normalized_brand = normalize_text(brand_name)
    normalized_profile = normalize_text(profile_name)
    normalized_bio = normalize_text(bio)

    name_similarity = (
        float(fuzz.ratio(normalized_brand, normalized_profile))
        if normalized_brand and normalized_profile
        else 0.0
    )

    handle_similarity = (
        float(fuzz.ratio(
            normalize_identifier(brand_name),
            normalize_identifier(handle),
        ))
        if brand_name and handle
        else 0.0
    )

    official_handles = brand.get("official_social_handles", [])
    if isinstance(official_handles, str):
        official_handles = [official_handles]

    candidate_handle = normalize_identifier(handle)
    is_official = bool(candidate_handle) and any(
        candidate_handle == normalize_identifier(official_handle)
        for official_handle in official_handles
    )

    scam_matches = [
        phrase for phrase in SCAM_PHRASES
        if normalize_text(phrase) in normalized_bio
    ]
    has_scam_phrase = bool(scam_matches)

    reasons = []
    if name_similarity >= 80:
        reasons.append("Profile name closely resembles the brand name.")
    if handle_similarity >= 80:
        reasons.append("Handle closely resembles the brand name.")
    if has_scam_phrase:
        reasons.append("Bio contains a potentially suspicious phrase.")
    if is_official:
        reasons.append("Handle matches a registered official social profile.")

    return {
        "asset_type": "social",
        "signals": {
            "name_similarity": name_similarity,
            "handle_similarity": handle_similarity,
            "has_scam_phrase": has_scam_phrase,
            "account_age_days": account_age_days,
            "is_official": is_official,
        },
        "reasons": reasons,
        "evidence": {
            "platform": candidate.get("platform"),
            "profile_name": profile_name,
            "handle": handle,
            "scam_phrase_matches": scam_matches,
        },
    }