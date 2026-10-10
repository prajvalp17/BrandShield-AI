import pytest

from score_engine import combine


def build_output(**overrides):
    output = {
        "entity_id": "soc_01",
        "target_type": "social_profile",
        "platform": "Instagram",
        "identifier": "@brand_support",
        "is_official": False,
        "exclusion_reason": None,
        "signals": {},
        "evidence_source": "simulated",
        "evidence_timestamp": None,
        "indicators": {
            "contact_number": "9000011111",
            "redirect_url": "https://example.com/login",
        },
        "evidence": {},
    }
    output.update(overrides)
    return output


def test_official_candidate_is_cleared():
    result = combine(build_output(
        is_official=True,
        exclusion_reason="official_asset",
    ))
    assert result["status"] == "CLEARED"
    assert result["risk_score"] == 0.0
    assert result["is_official"] is True
    assert result["exclusion_reason"] == "official_asset"
    assert result["review_required"] is False
    assert result["ring_id"] is None


def test_null_signal_values_are_ignored():
    result = combine(build_output(signals={
        "handle_similarity": {"value": None, "category": "identity", "reason": "unknown"},
        "scam_phrase": {"value": None, "category": "content", "reason": "unknown"},
        "account_age": {"value": None, "category": "metadata", "reason": "unknown"},
    }))
    assert result["status"] == "NOT_FLAGGED"
    assert result["risk_score"] == 0.0
    assert result["review_required"] is False


@pytest.mark.parametrize("field", [
    "entity_id",
    "target_type",
    "platform",
    "identifier",
    "is_official",
    "exclusion_reason",
    "signals",
    "evidence_source",
    "evidence_timestamp",
])
def test_missing_required_input_field_raises(field):
    engine_output = build_output()
    del engine_output[field]

    with pytest.raises(ValueError, match="required"):
        combine(engine_output)


def test_unknown_signal_category_raises():
    with pytest.raises(ValueError, match="category"):
        combine(build_output(signals={
            "handle_similarity": {"value": 0.8, "category": "reputation", "reason": "unknown category"},
        }))


def test_two_active_categories_flag_at_threshold():
    result = combine(build_output(signals={
        "handle_similarity": {"value": 0.90, "category": "identity", "reason": "very similar"},
        "name_similarity": {"value": 0.90, "category": "identity", "reason": "very similar"},
        "scam_phrase": {"value": 0.90, "category": "content", "reason": "bad phrase"},
        "account_age": {"value": 0.10, "category": "metadata", "reason": "older account"},
    }))
    assert result["status"] == "FLAGGED"
    assert result["risk_score"] >= 0.70
    assert result["review_required"] is False
    assert set(result["signals"]) >= {"handle_similarity", "scam_phrase"}


def test_exact_weighted_threshold_flags_with_two_active_categories():
    result = combine(build_output(signals={
        "scam_phrase": {"value": 0.70, "category": "content", "reason": "suspicious phrase"},
        "account_age": {"value": 0.70, "category": "metadata", "reason": "new account"},
    }))

    assert result["status"] == "FLAGGED"


def test_weighted_score_below_threshold_is_not_flagged():
    result = combine(build_output(signals={
        "scam_phrase": {"value": 0.6999, "category": "content", "reason": "suspicious phrase"},
        "account_age": {"value": 0.6999, "category": "metadata", "reason": "new account"},
    }))

    assert result["status"] == "NOT_FLAGGED"


def test_one_active_category_triggers_review_without_flagging():
    result = combine(build_output(signals={
        "handle_similarity": {"value": 0.90, "category": "identity", "reason": "similar handle"},
        "name_similarity": {"value": 0.10, "category": "identity", "reason": "not similar"},
        "scam_phrase": {"value": None, "category": "content", "reason": "unknown"},
        "account_age": {"value": None, "category": "metadata", "reason": "unknown"},
    }))
    assert result["status"] == "NOT_FLAGGED"
    assert result["review_required"] is True
    assert result["risk_score"] >= 0.70


def test_borderline_score_requires_review_but_not_flagging():
    result = combine(build_output(signals={
        "handle_similarity": {"value": 0.80, "category": "identity", "reason": "somewhat similar"},
        "scam_phrase": {"value": 0.50, "category": "content", "reason": "not strongly suspicious"},
        "account_age": {"value": None, "category": "metadata", "reason": "unknown"},
    }))
    assert result["status"] == "NOT_FLAGGED"
    assert 0.50 <= result["risk_score"] < 0.70
    assert result["review_required"] is True


def test_same_category_counts_once_for_active_category_total():
    result = combine(build_output(signals={
        "handle_similarity": {"value": 0.90, "category": "identity", "reason": "very similar"},
        "name_similarity": {"value": 0.90, "category": "identity", "reason": "very similar"},
        "description_similarity": {"value": 0.90, "category": "content", "reason": "looks like phishing"},
        "account_age": {"value": 0.10, "category": "metadata", "reason": "older account"},
    }))
    assert result["status"] == "FLAGGED"
    assert result["risk_score"] >= 0.70
    assert result["review_required"] is False


def test_invalid_non_numeric_signal_value_raises():
    with pytest.raises(ValueError):
        combine(build_output(signals={
            "handle_similarity": {"value": "high", "category": "identity", "reason": "bad"},
        }))


def test_invalid_out_of_range_signal_value_raises():
    with pytest.raises(ValueError):
        combine(build_output(signals={
            "handle_similarity": {"value": 1.5, "category": "identity", "reason": "bad"},
        }))


def test_contact_and_redirect_are_not_scored():
    result = combine(build_output(signals={
        "handle_similarity": {"value": 0.20, "category": "identity", "reason": "low"},
        "scam_phrase": {"value": 0.20, "category": "content", "reason": "low"},
        "account_age": {"value": 0.20, "category": "metadata", "reason": "low"},
    }))
    assert result["status"] == "NOT_FLAGGED"
    assert "contact_number" not in result["signals"]
    assert "redirect_url" not in result["signals"]
    assert result["ring_id"] is None
