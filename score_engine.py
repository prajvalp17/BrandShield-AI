
from typing import Any

WEIGHTS = {
    "identity": 0.45,
    "content": 0.35,
    "metadata": 0.20,
}

ACTIVE_THRESHOLD = 0.60
FLAG_THRESHOLD = 0.70
REQUIRED_INPUT_FIELDS = (
    "entity_id",
    "target_type",
    "platform",
    "identifier",
    "is_official",
    "exclusion_reason",
    "signals",
    "evidence_source",
    "evidence_timestamp",
)

VALID_TARGET_TYPES = {"social_profile", "app_listing"}


def _coerce_signal_value(name: str, value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} value must be a number between 0 and 1 or null")
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} value must be between 0 and 1")
    return value


def _base_result(engine_output: dict[str, Any], *, is_official: bool = False) -> dict[str, Any]:
    return {
        "entity_id": engine_output.get("entity_id", ""),
        "target_type": engine_output.get("target_type", ""),
        "platform": engine_output.get("platform", ""),
        "identifier": engine_output.get("identifier", ""),
        "risk_score": 0.0,
        "status": "CLEARED" if is_official else "NOT_FLAGGED",
        "is_official": is_official,
        "signals": {},
        "reasons": [],
        "exclusion_reason": engine_output.get("exclusion_reason") if is_official else None,
        "review_required": False,
        "evidence_source": engine_output.get("evidence_source", "simulated"),
        "evidence_timestamp": engine_output.get("evidence_timestamp"),
        "ring_id": None,
    }


def combine(engine_output: dict) -> dict:
    """Combine engine output signals into a frozen scoring result."""
    if not isinstance(engine_output, dict):
        raise TypeError("engine_output must be a dict")

    missing_fields = [field for field in REQUIRED_INPUT_FIELDS if field not in engine_output]
    if missing_fields:
        raise ValueError(f"engine_output is missing required fields: {', '.join(missing_fields)}")

    # Section 3 of CONTRACT.md: validate target_type explicitly.
    target_type = engine_output["target_type"]

    if not isinstance(target_type, str) or target_type not in VALID_TARGET_TYPES:
        raise ValueError(
            "target_type must be exactly 'social_profile' or 'app_listing'; "
            f"got {target_type!r}"
        )

    is_official = bool(engine_output.get("is_official", False))
    if is_official:
        result = _base_result(engine_output, is_official=True)
        result["exclusion_reason"] = engine_output.get("exclusion_reason") or "official_asset"
        result["reasons"] = ["Matched a registered official asset"]
        result["status"] = "CLEARED"
        result["risk_score"] = 0.0
        return result

    signals = engine_output["signals"]
    if not isinstance(signals, dict):
        raise TypeError("signals must be a mapping of signal names to {value, category, reason}")

    category_values: dict[str, list[float]] = {"identity": [], "content": [], "metadata": []}
    scored_signals: dict[str, float] = {}

    for signal_name, signal_record in signals.items():
        if signal_name in {"contact_number", "redirect_url"}:
            continue
        if signal_record is None:
            continue
        if not isinstance(signal_record, dict):
            raise TypeError(f"{signal_name} signal definition must be a dict")
        category = signal_record.get("category")
        if not isinstance(category, str) or category not in WEIGHTS:
            raise ValueError(f"{signal_name} signal category must be identity, content, or metadata")
        value = _coerce_signal_value(signal_name, signal_record.get("value"))
        if value is None:
            continue
        category_values[category].append(value)
        scored_signals[signal_name] = value

    if not scored_signals:
        result = _base_result(engine_output)
        result["signals"] = {}
        result["reasons"] = ["Insufficient evidence to calculate risk"]
        result["status"] = "NOT_FLAGGED"
        result["risk_score"] = 0.0
        result["review_required"] = False
        return result

    category_scores = {
        category: max(values) if values else None
        for category, values in category_values.items()
    }
    available_categories = {
        category: value
        for category, value in category_scores.items()
        if value is not None
    }

    total_weight = sum(WEIGHTS[category] for category in available_categories)
    risk_score = sum(
        WEIGHTS[category] * value
        for category, value in available_categories.items()
    ) / total_weight
    risk_score = round(float(risk_score), 6)

    active_categories = {
        category for category, value in available_categories.items()
        if value >= ACTIVE_THRESHOLD
    }

    flagged = risk_score >= FLAG_THRESHOLD and len(active_categories) >= 2
    if flagged:
        status = "FLAGGED"
        review_required = False
    elif risk_score >= FLAG_THRESHOLD and len(active_categories) < 2:
        status = "NOT_FLAGGED"
        review_required = True
    elif 0.50 <= risk_score < FLAG_THRESHOLD:
        status = "NOT_FLAGGED"
        review_required = True
    else:
        status = "NOT_FLAGGED"
        review_required = False

    reason_items: list[str] = []
    if active_categories:
        for category in sorted(active_categories):
            reason_items.append(f"{category} category active ({available_categories[category]:.2f})")
    else:
        reason_items = ["No active risk categories"]
    if not flagged and risk_score >= FLAG_THRESHOLD and len(active_categories) < 2:
        reason_items.append("High risk score without two independent active categories")
    elif not flagged and 0.50 <= risk_score < FLAG_THRESHOLD:
        reason_items.append("Borderline risk score requires review")

    result = _base_result(engine_output)
    result["risk_score"] = round(float(risk_score), 3)
    result["status"] = status
    result["signals"] = {name: round(float(value), 3) for name, value in scored_signals.items()}
    result["reasons"] = reason_items
    result["exclusion_reason"] = engine_output.get("exclusion_reason")
    result["review_required"] = review_required
    result["evidence_source"] = engine_output.get("evidence_source", "simulated")
    result["evidence_timestamp"] = engine_output.get("evidence_timestamp")
    result["ring_id"] = None
    return result
