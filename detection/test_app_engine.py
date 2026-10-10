
import sys
from pathlib import Path

# Add the repository root to Python's import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_engine import evaluate



brand = {
    "brand_id": "brand_01",
    "name": "AcmePay",
    "official_apps": [
        {
            "platform": "Android",
            "package_id": "com.acme.pay",
            "publisher": "Acme Technologies",
        }
    ],
    "official_descriptions": [
        "Official mobile payment application for AcmePay customers"
    ],
}


def make_candidate(**overrides):
    candidate = {
        "entity_id": "app_test",
        "target_type": "app_listing",
        "brand_id": "brand_01",
        "platform": "Android",
        "app_name": "Garden Planner",
        "package_id": "com.green.garden",
        "publisher": "Green Apps",
        "description": "Plan and organize your garden",
        "evidence_source": "simulated",
        "contact_number": None,
        "redirect_url": None,
    }
    candidate.update(overrides)
    return candidate


def test_evaluate_returns_contract_fields():
    result = evaluate(brand, make_candidate())

    required = {
        "entity_id",
        "target_type",
        "platform",
        "identifier",
        "is_official",
        "exclusion_reason",
        "signals",
        "evidence_source",
        "evidence_timestamp",
        "indicators",
        "evidence",
    }

    assert required.issubset(result.keys())
    assert result["entity_id"] == "app_test"
    assert result["target_type"] == "app_listing"
    assert "risk_score" not in result
    assert "status" not in result


def test_exact_official_package_is_official():
    candidate = make_candidate(
        entity_id="app_official",
        app_name="AcmePay",
        package_id="com.acme.pay",
        publisher="Acme Technologies",
    )

    result = evaluate(brand, candidate)

    assert result["is_official"] is True
    assert result["exclusion_reason"] is not None


def test_lookalike_app_returns_normalized_signals():
    candidate = make_candidate(
        entity_id="app_lookalike",
        app_name="AcmePay Support",
        package_id="com.unknown.acmepay",
        publisher="Unknown Publisher",
        description=(
            "Official mobile payment application for AcmePay customers"
        ),
    )

    result = evaluate(brand, candidate)

    expected_signals = {
        "app_name_similarity",
        "package_similarity",
        "description_similarity",
        "credential_bait",
        "publisher_mismatch",
    }

    assert expected_signals == set(result["signals"])

    for signal in result["signals"].values():
        value = signal["value"]
        assert value is None or 0.0 <= value <= 1.0
        assert signal["category"] in {"identity", "content", "metadata"}
        assert isinstance(signal["reason"], str)


def test_missing_description_and_publisher_are_unknown():
    candidate = make_candidate(
        entity_id="app_missing",
        description=None,
        publisher=None,
    )

    result = evaluate(brand, candidate)

    assert result["signals"]["description_similarity"]["value"] is None
    assert result["signals"]["publisher_mismatch"]["value"] is None
    assert result["signals"]["credential_bait"]["value"] is None


def test_contact_and_full_url_are_indicators_not_signals():
    candidate = make_candidate(
        contact_number="+1 (800) 555-0100",
        redirect_url="https://Example.com/login?next=account",
    )

    result = evaluate(brand, candidate)

    assert result["indicators"]["contact_number"] == "8005550100"
    assert result["indicators"]["redirect_url"] == (
        "https://example.com/login?next=account"
    )

    assert "contact_number" not in result["signals"]
    assert "redirect_url" not in result["signals"]


def test_official_package_matching_respects_platform():
    candidate = make_candidate(
        platform="iOS",
        package_id="com.acme.pay",
    )

    result = evaluate(brand, candidate)

    assert result["is_official"] is False
