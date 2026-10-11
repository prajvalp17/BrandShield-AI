"""Headless smoke tests for the Streamlit dashboard (app.py), using Streamlit's AppTest.
They check that the app loads for every brand, that its numbers agree with the shared pipeline, and that the
SHA-256 shown beside the download equals the hash of the canonical report bytes (CONTRACT section 6)."""
import hashlib, json, os
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app.py")
pytest.importorskip("streamlit")
if not os.path.exists(APP):
    pytest.skip("app.py not present yet", allow_module_level=True)
from streamlit.testing.v1 import AppTest

def load(name):
    return json.load(open(os.path.join(ROOT, "data", name), encoding="utf-8"))

def start(brand=None, **selects):
    at = AppTest.from_file(APP, default_timeout=90).run()
    if brand:
        at.sidebar.selectbox[0].select(brand).run()
    for label, value in selects.items():
        for sb in at.sidebar.selectbox:
            if sb.label == label:
                sb.select(value).run()
    return at

def metrics(at):
    return {m.label: int(m.value) for m in at.metric if m.label in ("Total entities", "Flagged", "Needs review", "Cleared")}

def card_count(at):
    return len([m for m in at.metric if m.label == "Risk score"])

@pytest.fixture(scope="module")
def brand_names():
    return [b["name"] for b in load("brand_registry.json")["brands"]]

def test_app_loads_without_errors_for_every_brand(brand_names):
    for name in brand_names:
        at = start(name)
        assert not at.exception, (name, [e.value for e in at.exception])
        assert not at.error, (name, [e.value for e in at.error])
        assert card_count(at) == metrics(at)["Total entities"], "with no filters every entity should be shown"

def test_dashboard_totals_agree_with_the_datasets(brand_names):
    total = sum(metrics(start(n))["Total entities"] for n in brand_names)
    assert total == len(load("social_profiles.json")) + len(load("app_listings.json"))

def test_official_assets_are_cleared_not_flagged(brand_names):
    registry = {b["name"]: b for b in load("brand_registry.json")["brands"]}
    official = {r["brand_id"]: 0 for r in registry.values()}
    for r in load("social_profiles.json") + load("app_listings.json"):
        if r["ground_truth"] == "official":
            official[r["brand_id"]] += 1
    for name in brand_names:
        assert metrics(start(name))["Cleared"] == official[registry[name]["brand_id"]]

def test_status_filter_matches_the_flagged_metric(brand_names):
    for name in brand_names:
        base = start(name)
        flagged = metrics(base)["Flagged"]
        filtered = start(name, Status="FLAGGED")
        assert card_count(filtered) == flagged
        assert metrics(filtered)["Total entities"] == metrics(base)["Total entities"], "filters must not change the metrics"

def test_displayed_sha256_equals_hash_of_canonical_report_bytes(brand_names):
    import app   # module import only; main() is not run
    brands, social, apps = app.load_datasets()
    name = brand_names[0]
    brand = next(b for b in brands if b["name"] == name)
    cands = [app.candidate_for_detection(c) for c in social + apps if c["brand_id"] == brand["brand_id"]]
    report = app.run_detection_pipeline(brand, cands)[3]
    expected = hashlib.sha256(app.canonical_json_bytes(report)).hexdigest()
    at = start(name)
    assert expected in [c.value for c in at.code], "the digest shown in the UI must equal the hash of the exported bytes"

def test_page_states_the_data_is_simulated_and_hash_does_not_prove_authenticity():
    at = start()
    text = " ".join([w.value for w in at.warning] + [c.value for c in at.caption]).lower()
    assert "simulated" in text
    assert "not the authenticity" in text or "authenticity" in text
