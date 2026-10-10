
import re
import unicodedata
from rapidfuzz import fuzz


# --------------------------------------------------
# TEXT NORMALIZATION
# Replace this with Member 2's shared utility
# when it becomes available.
# --------------------------------------------------

def normalize_text(value):
    """Normalize text for consistent comparisons."""
    if value is None:
        return ""

    value = unicodedata.normalize("NFKC", str(value))
    value = value.casefold()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_identifier(value):
    """Normalize package IDs and other identifiers."""
    return normalize_text(value)


# --------------------------------------------------
# SIMILARITY
# --------------------------------------------------

def similarity(text_a, text_b):
    """Return similarity from 0 to 100, or None if missing."""
    a = normalize_text(text_a)
    b = normalize_text(text_b)

    if not a or not b:
        return None

    return round(fuzz.ratio(a, b), 2)


def best_description_similarity(description, official_descriptions):
    """Find the closest available official description."""
    scores = [
        similarity(description, official)
        for official in official_descriptions
    ]

    scores = [score for score in scores if score is not None]

    return max(scores) if scores else None


# --------------------------------------------------
# APP DETECTION ENGINE
# --------------------------------------------------

def detect_app(app, brand):
    """
    Analyze a candidate app against a registered brand.

    Candidate app fields:
        app_id, name, publisher, description, package_id

    Brand fields:
        name, official_package_ids, official_publishers,
        official_descriptions

    Risk scores are heuristic indicators, not probabilities
    or proof that an app is malicious.
    """

    package_id = normalize_identifier(app.get("package_id"))

    official_package_ids = {
        normalize_identifier(item)
        for item in brand.get("official_package_ids", [])
        if item
    }

    # 1. Protect exact registered official package IDs.
    if package_id and package_id in official_package_ids:
        return {
            "app_id": app.get("app_id"),
            "risk_score": 0,
            "risk_level": "low",
            "classification": "official",
            "signals": {
                "official_package_match": True,
                "name_similarity": None,
                "publisher_mismatch": None,
                "description_similarity": None,
            },
            "reasons": [
                "Exact registered official package ID match"
            ],
        }

    # 2. Extract candidate and brand details.
    app_name = app.get("name", "")
    brand_name = brand.get("name", "")
    publisher = normalize_text(app.get("publisher", ""))
    description = app.get("description", "")

    official_publishers = {
        normalize_text(item)
        for item in brand.get("official_publishers", [])
        if item
    }

    official_descriptions = brand.get(
        "official_descriptions", []
    )

    # 3. Calculate detection signals.
    name_score = similarity(app_name, brand_name)

    description_score = best_description_similarity(
        description,
        official_descriptions,
    )

    publisher_known = (
        publisher in official_publishers
        if publisher and official_publishers
        else None
    )

    publisher_mismatch = (
        not publisher_known
        if publisher_known is not None
        else None
    )

    # 4. Explainable risk scoring.
    # Publisher mismatch alone never adds risk points.
    score = 0
    reasons = []

    if name_score is not None:
        if name_score >= 90:
            score += 50
            reasons.append(
                "App name is highly similar to the registered brand"
            )
        elif name_score >= 75:
            score += 35
            reasons.append(
                "App name closely resembles the registered brand"
            )
        elif name_score >= 60:
            score += 15
            reasons.append(
                "App name has some similarity to the registered brand"
            )

    if publisher_mismatch is True:
        reasons.append(
            "Publisher is not in the authorized publisher list"
        )
    elif publisher_known is True:
        reasons.append(
            "Publisher matches an authorized publisher"
        )
    else:
        reasons.append(
            "Publisher could not be verified"
        )

    if description_score is not None:
        if description_score >= 80:
            score += 25
            reasons.append(
                "Description closely resembles an official description"
            )
        elif description_score >= 60:
            score += 15
            reasons.append(
                "Description has notable similarity to an official description"
            )

    score = min(int(score), 100)

    # 5. Determine triage classification.
    if score >= 60:
        risk_level = "high"
        classification = "suspicious"
    elif score >= 30:
        risk_level = "medium"
        classification = "review"
    else:
        risk_level = "low"
        classification = "low_risk"

    if not reasons:
        reasons.append("Insufficient matching evidence")

    return {
        "app_id": app.get("app_id"),
        "risk_score": score,
        "risk_level": risk_level,
        "classification": classification,
        "signals": {
            "name_similarity": name_score,
            "publisher_mismatch": publisher_mismatch,
            "description_similarity": description_score,
            "official_package_match": False,
        },
        "reasons": reasons,
    }


# --------------------------------------------------
# BATCH DETECTION
# --------------------------------------------------

def detect_apps(apps, brand):
    """Analyze multiple candidate apps."""
    return [
        detect_app(app, brand)
        for app in apps
    ]
