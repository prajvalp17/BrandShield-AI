"""Contract conformance tests for CONTRACT.md v0.5 (owner: Member 1).
Run from the repo root:  pytest tests/test_contract.py -v
Tests for a module are SKIPPED until that module exists, so this file is safe to commit today.
These check the interface and rules, NOT detection accuracy (evaluation.py does that)."""
import copy, itertools, json, os, random
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIDDEN = ("ground_truth", "category_note", "expected_ring")
RESULT_KEYS = {"entity_id", "target_type", "platform", "identifier", "risk_score", "status", "is_official",
               "signals", "reasons", "exclusion_reason", "review_required", "evidence_source",
               "evidence_timestamp", "ring_id"}
ENGINE_KEYS = {"entity_id", "target_type", "platform", "identifier", "is_official", "exclusion_reason",
               "signals", "evidence_source", "evidence_timestamp", "indicators", "evidence"}
CATEGORIES = {"identity", "content", "metadata"}
SIGNAL_NAMES = {
    "social_profile": {"handle_similarity": "identity", "name_similarity": "identity",
                       "scam_phrase": "content", "account_age": "metadata"},
    "app_listing": {"app_name_similarity": "identity", "package_similarity": "identity",
                    "description_similarity": "content", "credential_bait": "content",
                    "publisher_mismatch": "metadata"},
}
STATUSES = {"CLEARED", "NOT_FLAGGED", "FLAGGED"}

def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)

def clean(r):
    return {k: v for k, v in r.items() if k not in HIDDEN}

@pytest.fixture(scope="session")
def brands():
    return {b["brand_id"]: b for b in load("data/brand_registry.json")["brands"]}

@pytest.fixture(scope="session")
def social():
    return load("data/social_profiles.json")

@pytest.fixture(scope="session")
def apps():
    return load("data/app_listings.json")

# ------------------------------------------------------------------ data files
def test_data_ids_unique_and_fields(social, apps, brands):
    ids = [r["entity_id"] for r in social + apps]
    assert len(ids) == len(set(ids))
    for r in social:
        assert r["target_type"] == "social_profile" and r["username"].startswith("@")
    for r in apps:
        assert r["target_type"] == "app_listing" and r["package_id"]
    for r in social + apps:
        assert r["brand_id"] in brands and r["evidence_source"] == "simulated"
        assert r["ground_truth"] in {"official", "impersonator", "benign"}

def test_registry_handles_belong_to_one_brand(brands):
    seen = {}
    for b in brands.values():
        for plat, hs in b["official_handles"].items():
            for h in hs:
                key = (plat, h.lower())
                assert key not in seen or seen[key] == b["brand_id"], f"{key} registered twice"
                seen[key] = b["brand_id"]
        for a in b["official_apps"]:
            key = ("pkg", a["package_id"])
            assert key not in seen, f"{key} registered twice"
            seen[key] = b["brand_id"]

# ------------------------------------------------------------------ engines
def _engine_cases(module, records, brands, target):
    mod = pytest.importorskip(module)
    for r in records:
        cand = clean(r)
        before = copy.deepcopy(cand)
        out = mod.evaluate(brands[r["brand_id"]], cand)
        assert cand == before, "engine mutated the candidate"
        yield r, out

def _check_engine_output(r, out, target):
    assert ENGINE_KEYS <= set(out), f"{r['entity_id']}: missing {ENGINE_KEYS - set(out)}"
    assert out["entity_id"] == r["entity_id"]
    assert out["target_type"] == target
    assert out["platform"] == r["platform"]
    assert out["evidence_source"] == r["evidence_source"]
    assert out["identifier"] == (r["username"] if target == "social_profile" else r["package_id"])
    assert isinstance(out["is_official"], bool)
    assert out["evidence_timestamp"] is None or isinstance(out["evidence_timestamp"], str)
    assert isinstance(out["signals"], dict) and isinstance(out["indicators"], dict) and isinstance(out["evidence"], dict)
    for name, s in out["signals"].items():
        assert name in SIGNAL_NAMES[target], f"{r['entity_id']}: unknown signal {name}"
        assert set(s) >= {"value", "category", "reason"}
        assert s["category"] == SIGNAL_NAMES[target][name], f"{name} wrong category"
        assert s["value"] is None or (isinstance(s["value"], (int, float)) and 0.0 <= s["value"] <= 1.0), \
            f"{r['entity_id']}.{name} value {s['value']} not in 0..1 (did you forget to divide RapidFuzz by 100?)"
        assert isinstance(s["reason"], str)

def test_social_engine_output_shape(social, brands):
    for r, out in _engine_cases("social_engine", social, brands, "social_profile"):
        _check_engine_output(r, out, "social_profile")

def test_app_engine_output_shape(apps, brands):
    for r, out in _engine_cases("app_engine", apps, brands, "app_listing"):
        _check_engine_output(r, out, "app_listing")

def test_engines_recognise_registered_official_assets(social, apps, brands):
    for module, recs in (("social_engine", social), ("app_engine", apps)):
        for r, out in _engine_cases(module, recs, brands, None):
            assert out["is_official"] == (r["ground_truth"] == "official"), \
                f"{r['entity_id']} ({r['ground_truth']}): is_official={out['is_official']}"
            if out["is_official"]:
                assert out["exclusion_reason"], "official asset needs an exclusion_reason"

def test_missing_fields_do_not_crash_engines(social, apps, brands):
    for module, recs in (("social_engine", social), ("app_engine", apps)):
        mod = pytest.importorskip(module)
        for r in recs[:6]:
            c = clean(r)
            for k in ("bio", "display_name", "account_age_days", "contact_number", "redirect_url",
                      "publisher", "description"):
                c[k] = None
            mod.evaluate(brands[r["brand_id"]], c)

# ------------------------------------------------------------------ scoring
def eo(signals, official=False, target="social_profile"):
    """Build a synthetic engine output. signals: {category: value|None}."""
    names = {"identity": "handle_similarity", "content": "scam_phrase", "metadata": "account_age"}
    return {"entity_id": "x_01", "target_type": target, "platform": "Instagram", "identifier": "@x",
            "is_official": official, "exclusion_reason": "registered handle" if official else None,
            "signals": {names[c]: {"value": v, "category": c, "reason": ""} for c, v in signals.items()},
            "evidence_source": "simulated", "evidence_timestamp": None, "indicators": {}, "evidence": {"k": 1}}

@pytest.fixture(scope="module")
def combine():
    return pytest.importorskip("score_engine").combine

def active_count(sig):
    return sum(1 for v in sig.values() if v is not None and v >= 0.60)

def test_result_has_exactly_the_frozen_fields(combine):
    out = combine(eo({"identity": 0.9, "content": 0.8, "metadata": 0.9}))
    assert set(out) == RESULT_KEYS, f"extra: {set(out) - RESULT_KEYS}, missing: {RESULT_KEYS - set(out)}"
    for banned in ("evidence_hash", "label", "evidence", "indicators"):
        assert banned not in out
    assert out["ring_id"] is None
    assert out["status"] in STATUSES and 0.0 <= out["risk_score"] <= 1.0
    assert isinstance(out["reasons"], list) and isinstance(out["review_required"], bool)

def test_official_is_cleared_before_scoring(combine):
    out = combine(eo({"identity": 1.0, "content": 1.0, "metadata": 1.0}, official=True))
    assert out["status"] == "CLEARED" and out["risk_score"] == 0.0
    assert out["is_official"] is True and out["exclusion_reason"]
    assert out["review_required"] is False

def test_all_null_is_not_flagged_and_zero(combine):
    out = combine(eo({"identity": None, "content": None, "metadata": None}))
    assert out["status"] == "NOT_FLAGGED" and out["risk_score"] == 0.0 and out["review_required"] is False
    out = combine({**eo({}), "signals": {}})
    assert out["status"] == "NOT_FLAGGED"

def test_one_category_never_flags(combine):
    out = combine(eo({"identity": 1.0, "content": None, "metadata": None}))
    assert out["status"] != "FLAGGED"
    if out["risk_score"] >= 0.70:
        assert out["review_required"] is True

def test_two_inactive_categories_never_flag(combine):
    assert combine(eo({"identity": 0.59, "content": 0.59, "metadata": 0.59}))["status"] != "FLAGGED"

def test_two_strong_categories_flag(combine):
    assert combine(eo({"identity": 0.95, "content": 0.95, "metadata": None}))["status"] == "FLAGGED"

def test_correlated_signals_count_once(combine):
    e = eo({"identity": 0.95, "content": None, "metadata": None})
    e["signals"]["name_similarity"] = {"value": 0.95, "category": "identity", "reason": ""}
    out = combine(e)
    assert out["status"] != "FLAGGED", "two identity signals must count as ONE category"

def test_null_signals_do_not_change_score(combine):
    base = combine(eo({"identity": 0.8, "content": 0.8}))["risk_score"]
    with_null = combine(eo({"identity": 0.8, "content": 0.8, "metadata": None}))["risk_score"]
    assert base == with_null, "a missing signal changed the score (nulls must be ignored)"

def test_missing_categories_are_renormalized(combine):
    """Encodes proposed ruling 17: weights are renormalized over categories that have data, so if every
    available category has the same value v, risk_score == v. Delete or adjust ONLY if ruling 17 differs."""
    for v in (0.3, 0.6, 0.8, 1.0):
        for cats in (("identity",), ("identity", "content"), ("content", "metadata"), ("identity", "content", "metadata")):
            sig = {c: v for c in cats}
            got = combine(eo(sig))["risk_score"]
            assert abs(got - v) < 1e-9, f"{sig}: expected {v}, got {got} (missing data is lowering the score)"

def test_status_and_review_rules_over_a_grid(combine):
    vals = [None, 0.0, 0.5, 0.59, 0.6, 0.7, 0.95, 1.0]
    for ident, cont, meta in itertools.product(vals, repeat=3):
        sig = {"identity": ident, "content": cont, "metadata": meta}
        out = combine(eo(sig))
        s, st, rev = out["risk_score"], out["status"], out["review_required"]
        assert 0.0 <= s <= 1.0, sig
        assert st in {"FLAGGED", "NOT_FLAGGED"}, sig
        n = active_count(sig)
        if st == "FLAGGED":
            assert s >= 0.70 and n >= 2, f"bad flag {sig} score={s}"
        else:
            assert not (s >= 0.70 and n >= 2), f"should have flagged {sig} score={s}"
        expected_rev = (s >= 0.70 and n < 2) or (st == "NOT_FLAGGED" and 0.50 <= s < 0.70)
        assert rev == expected_rev, f"review_required wrong for {sig} score={s} status={st}"

def test_result_signals_are_flat_rounded_floats(combine):
    """Ruling 18: result `signals` = {name: float}, non-null scored signals only, 3 decimals."""
    out = combine(eo({"identity": 0.9123456, "content": None, "metadata": 0.5}))
    assert out["signals"] == {"handle_similarity": 0.912, "account_age": 0.5}
    assert combine(eo({"identity": 1.0}, official=True))["signals"] == {}

def test_two_categories_at_exactly_0_70_flag(combine):
    """Ruling 17: comparisons use the score rounded to 6 decimals (float noise must not matter)."""
    for pair in (("content", "metadata"), ("identity", "content"), ("identity", "metadata")):
        out = combine(eo({pair[0]: 0.7, pair[1]: 0.7}))
        assert out["risk_score"] == 0.7 and out["status"] == "FLAGGED", pair

def test_combine_rejects_bad_input(combine):
    """Ruling 19 (pending Member 4 acknowledgement): fail loudly, no silent defaults."""
    bad_range = eo({"identity": 1.5})
    with pytest.raises((ValueError, TypeError, KeyError)):
        combine(bad_range)
    bad_cat = eo({"identity": 0.9})
    bad_cat["signals"]["handle_similarity"]["category"] = "nonsense"
    with pytest.raises((ValueError, TypeError, KeyError)):
        combine(bad_cat)
    missing = eo({"identity": 0.9})
    del missing["entity_id"]
    with pytest.raises((ValueError, TypeError, KeyError)):
        combine(missing)

def test_combine_rejects_invalid_target_type(combine):
    """Section 3: target_type must be exactly `social_profile` or `app_listing`."""
    for bad in ("social", "app", "", None, "SOCIAL_PROFILE"):
        e = eo({"identity": 0.9})
        e["target_type"] = bad
        with pytest.raises((ValueError, TypeError)):
            combine(e)
    for good in ("social_profile", "app_listing"):
        combine(eo({"identity": 0.9}, target=good))

def test_combine_is_deterministic_and_pure(combine):
    e = eo({"identity": 0.9, "content": 0.8, "metadata": 0.5})
    before = copy.deepcopy(e)
    assert combine(e) == combine(e)
    assert e == before, "combine mutated its input"

# ------------------------------------------------------------------ report builder
def sample_inputs(combine):
    cands = [
        {"entity_id": "soc_02", "target_type": "social_profile", "display_name": "Beta", "username": "@b"},
        {"entity_id": "soc_01", "target_type": "social_profile", "display_name": "Alpha", "username": "@a"},
        {"entity_id": "app_01", "target_type": "app_listing", "app_name": "App One", "package_id": "com.a"},
        {"entity_id": "soc_03", "target_type": "social_profile", "display_name": None, "username": "@c"},
    ]
    outs = []
    for c, sig in zip(cands, [{"identity": 0.9, "content": 0.9}, {"identity": 0.1}, {"identity": 0.9, "content": 0.9}, {"identity": 0.2}]):
        e = eo(sig, target=c["target_type"])
        e["entity_id"], e["identifier"] = c["entity_id"], c.get("username") or c["package_id"]
        e["evidence"] = {"for": c["entity_id"]}
        outs.append(e)
    results = [combine(o) for o in outs]
    return results, {"brand_id": "brand_01", "name": "Zenbank"}, cands, outs

@pytest.fixture(scope="module")
def build():
    return pytest.importorskip("report_builder").build_report

def test_report_structure(combine, build):
    results, brand, cands, outs = sample_inputs(combine)
    rep = build(results, brand, cands, outs)
    assert set(rep) == {"brand", "results", "clusters"}
    assert rep["brand"]["brand_id"] == "brand_01" and rep["brand"]["name"] == "Zenbank"
    assert rep["clusters"] == []
    json.dumps(rep, sort_keys=True)
    for r in rep["results"]:
        assert set(r) == RESULT_KEYS | {"label", "evidence"}, f"unexpected keys {set(r) ^ (RESULT_KEYS | {'label', 'evidence'})}"
        assert "evidence_hash" not in r and r["ring_id"] is None

def test_report_labels_and_evidence(combine, build):
    results, brand, cands, outs = sample_inputs(combine)
    by_id = {r["entity_id"]: r for r in build(results, brand, cands, outs)["results"]}
    assert by_id["soc_01"]["label"] == "Alpha" and by_id["app_01"]["label"] == "App One"
    assert by_id["soc_03"]["label"] is None, "missing label must be null, never guessed"
    assert by_id["soc_02"]["evidence"] == {"for": "soc_02"}
    rep = build(results, brand, [], [])
    assert all(r["label"] is None and r["evidence"] == {} for r in rep["results"])

def test_report_sorted_pure_and_deterministic(combine, build):
    results, brand, cands, outs = sample_inputs(combine)
    snap = copy.deepcopy((results, brand, cands, outs))
    rep = build(results, brand, cands, outs)
    assert (results, brand, cands, outs) == snap, "build_report mutated its inputs"
    ids = [r["entity_id"] for r in rep["results"]]
    assert ids == sorted(ids)
    shuffled = list(results); random.Random(1).shuffle(shuffled)
    rep2 = build(shuffled, brand, cands, outs)
    assert json.dumps(rep, sort_keys=True) == json.dumps(rep2, sort_keys=True), "report depends on input order"
    assert json.dumps(rep, sort_keys=True) == json.dumps(build(results, brand, cands, outs), sort_keys=True)

def test_report_shares_no_objects_with_inputs(combine, build):
    """Ruling 21: deep copies, so editing the report can never alter results or engine outputs."""
    results, brand, cands, outs = sample_inputs(combine)
    rep = build(results, brand, cands, outs)
    orig = {r["entity_id"]: r for r in results}
    eouts = {o["entity_id"]: o for o in outs}
    for r in rep["results"]:
        o = orig[r["entity_id"]]
        assert r is not o and r["signals"] is not o["signals"] and r["reasons"] is not o["reasons"]
        assert r["evidence"] is not eouts[r["entity_id"]]["evidence"]

def test_report_does_not_change_decisions(combine, build):
    results, brand, cands, outs = sample_inputs(combine)
    rep = {r["entity_id"]: r for r in build(results, brand, cands, outs)["results"]}
    for r in results:
        for k in ("status", "risk_score", "review_required", "reasons"):
            assert rep[r["entity_id"]][k] == r[k]

def test_report_clusters_sorted_and_ring_id_filled(combine, build):
    results, brand, cands, outs = sample_inputs(combine)
    clusters = [{"ring_id": "ring_B", "linked_candidate_ids": ["soc_02"], "reasons": []},
                {"ring_id": "ring_A", "linked_candidate_ids": ["soc_01", "app_01"], "reasons": []}]
    rep = build(results, brand, cands, outs, clusters)
    assert [c["ring_id"] for c in rep["clusters"]] == ["ring_A", "ring_B"]

def test_report_rejects_overlapping_or_malformed_clusters(combine, build):
    """Ruling 22: a candidate in two clusters, a duplicate ring_id, or a malformed cluster must raise."""
    results, brand, cands, outs = sample_inputs(combine)
    overlap = [{"ring_id": "ring_A", "linked_candidate_ids": ["soc_01", "app_01"], "reasons": []},
               {"ring_id": "ring_B", "linked_candidate_ids": ["app_01", "soc_02"], "reasons": []}]
    dup_ring = [{"ring_id": "ring_A", "linked_candidate_ids": ["soc_01"], "reasons": []},
                {"ring_id": "ring_A", "linked_candidate_ids": ["soc_02"], "reasons": []}]
    no_ring = [{"linked_candidate_ids": ["soc_01", "soc_02"], "reasons": []}]
    no_links = [{"ring_id": "ring_A", "reasons": []}]
    for bad in (overlap, dup_ring, no_ring, no_links):
        with pytest.raises(ValueError):
            build(results, brand, cands, outs, bad)

def test_report_accepts_disjoint_clusters(combine, build):
    results, brand, cands, outs = sample_inputs(combine)
    ok = [{"ring_id": "ring_A", "linked_candidate_ids": ["soc_01", "app_01"], "reasons": []},
          {"ring_id": "ring_B", "linked_candidate_ids": ["soc_02"], "reasons": []}]
    rep = build(results, brand, cands, outs, ok)
    ring = {r["entity_id"]: r["ring_id"] for r in rep["results"]}
    assert ring["soc_01"] == ring["app_01"] == "ring_A" and ring["soc_02"] == "ring_B" and ring["soc_03"] is None

# ------------------------------------------------------------------ v0.8 rulings 23-26
def test_registry_optional_fields_are_lists_of_strings(brands):
    """Rulings 24 and 26: optional lists; absent is allowed, wrong type is not."""
    for b in brands.values():
        for key in ("official_descriptions", "authorized_publishers", "official_contact_numbers"):
            if key in b:
                assert isinstance(b[key], list) and all(isinstance(x, str) and x for x in b[key]), (b["brand_id"], key)

@pytest.mark.xfail(reason="Ruling 23 pending: Member 2 to keep the last 10 digits (remove this marker once it passes)", strict=False)
def test_contact_number_normalization_ruling_23():
    n = pytest.importorskip("normalization").normalize_contact_number
    same = {n("+91 90000 11111"), n("90000 11111"), n("090000-11111"), n("(+91) 9000011111")}
    assert same == {"9000011111"}, same
    assert n("+91 90000 11112") != n("+91 90000 11111"), "one digit apart must not match"
    assert n("12345") is None and n(None) is None and n("") is None

RECORD_KEYS = {"ring_id", "linked_candidate_ids", "link_reasons"}

def _cluster_inputs(phone_b="+91 90000 11111"):
    base = {"target_type": "social_profile", "platform": "X", "brand_id": "brand_01", "evidence_source": "simulated"}
    cands = [
        {**base, "entity_id": "c1", "contact_number": "+91 90000 11111", "redirect_url": None},
        {**base, "entity_id": "c2", "contact_number": phone_b, "redirect_url": None},
        {**base, "entity_id": "c3", "contact_number": None, "redirect_url": "http://bad.example/pay"},
        {**base, "entity_id": "c4", "contact_number": None, "redirect_url": "http://bad.example/pay"},
        {**base, "entity_id": "c5", "contact_number": "+91 90000 11112", "redirect_url": None},   # one digit off
        {**base, "entity_id": "c6", "contact_number": "+91 90000 11111", "redirect_url": None},   # NOT_FLAGGED
        {**base, "entity_id": "c7", "contact_number": None, "redirect_url": "http://bad.example/other"},
    ]
    status = {"c1": "FLAGGED", "c2": "FLAGGED", "c3": "FLAGGED", "c4": "FLAGGED", "c5": "FLAGGED", "c6": "NOT_FLAGGED", "c7": "FLAGGED"}
    results = [{"entity_id": c["entity_id"], "status": status[c["entity_id"]]} for c in cands]
    return results, cands

def test_cluster_record_structure_ruling_25():
    import re
    cluster = pytest.importorskip("clustering").cluster
    results, cands = _cluster_inputs()
    snap = copy.deepcopy((results, cands))
    out = cluster(results, cands)
    assert (results, cands) == snap, "clustering mutated its inputs"
    assert out == cluster(results, cands), "clustering must be deterministic"
    seen, rings = set(), set()
    for c in out:
        assert set(c) >= RECORD_KEYS
        assert re.fullmatch(r"ring_\d{3}", c["ring_id"]) and c["ring_id"] not in rings
        rings.add(c["ring_id"])
        assert isinstance(c["linked_candidate_ids"], list) and len(c["linked_candidate_ids"]) >= 2
        assert c["linked_candidate_ids"] == sorted(c["linked_candidate_ids"])
        assert not (seen & set(c["linked_candidate_ids"])), "a candidate is in two clusters"
        seen |= set(c["linked_candidate_ids"])
        assert c["link_reasons"], "every cluster needs at least one link reason"
        for lr in c["link_reasons"]:
            assert set(lr) >= {"candidate_id_1", "candidate_id_2", "indicator_type", "reason"}
            assert lr["indicator_type"] in {"contact_number", "redirect_url"} and isinstance(lr["reason"], str) and lr["reason"]
            assert lr["candidate_id_1"] in c["linked_candidate_ids"] and lr["candidate_id_2"] in c["linked_candidate_ids"]
    groups = sorted(sorted(c["linked_candidate_ids"]) for c in out)
    assert groups == [["c1", "c2"], ["c3", "c4"]], groups   # c5 (one digit off), c6 (not flagged), c7 (alone) stay out

@pytest.mark.xfail(reason="Ruling 23 pending: needs last-10-digit normalization (remove this marker once it passes)", strict=False)
def test_clustering_links_numbers_written_differently():
    cluster = pytest.importorskip("clustering").cluster
    results, cands = _cluster_inputs(phone_b="90000 11111")
    groups = sorted(sorted(c["linked_candidate_ids"]) for c in cluster(results, cands))
    assert ["c1", "c2"] in groups, groups

def _publisher_signal(brand, publisher, package="com.thirdparty.x"):
    app_engine = pytest.importorskip("app_engine")
    cand = {"entity_id": "app_x", "target_type": "app_listing", "brand_id": "b", "platform": "Android",
            "app_name": "Brand Helper", "package_id": package, "publisher": publisher, "description": None,
            "contact_number": None, "redirect_url": None, "evidence_source": "simulated"}
    return app_engine.evaluate(brand, cand)["signals"]["publisher_mismatch"]["value"]

def test_publisher_mismatch_uses_official_plus_authorized_publishers():
    """CONTRACT section 2 (ruling 26): mismatch is measured against the official publisher PLUS
    authorized_publishers; if there are no authorized publishers, the official publisher alone counts."""
    base = {"brand_id": "b", "name": "Brand", "official_handles": {}, "official_domains": [],
            "official_apps": [{"platform": "Android", "package_id": "com.brand.app", "publisher": "Brand Ltd"}]}
    with_auth = {**base, "authorized_publishers": ["Brand Partner Co"]}
    assert _publisher_signal(base, "Brand Ltd") == 0.0, "official publisher must not count as a mismatch"
    assert _publisher_signal(base, "Random Studio") == 1.0
    assert _publisher_signal(with_auth, "Brand Ltd") == 0.0, "official publisher must still match when authorized list exists"
    assert _publisher_signal(with_auth, "Brand Partner Co") == 0.0
    assert _publisher_signal(with_auth, "Random Studio") == 1.0
    assert _publisher_signal(with_auth, None) is None, "unknown publisher is null, never a mismatch"

def test_report_accepts_real_cluster_records(combine, build):
    """Ruling 25 + 22: the cluster module's records must pass the report builder's validation."""
    cluster = pytest.importorskip("clustering").cluster
    results, brand, cands, outs = sample_inputs(combine)
    for c in cands:
        c.update({"platform": "Instagram", "contact_number": "+91 90000 99999", "redirect_url": None})
    flagged = [dict(r, status="FLAGGED") for r in results]
    clusters = cluster(flagged, cands)
    assert clusters, "expected one cluster (all share a number)"
    build(results, brand, cands, outs, clusters)

# ------------------------------------------------------------------ end to end (needs all real modules)
def test_end_to_end_official_assets_never_flagged(social, apps, brands):
    se, ae, sc = (pytest.importorskip(m) for m in ("social_engine", "app_engine", "score_engine"))
    for engine, recs in ((se, social), (ae, apps)):
        for r in recs:
            out = sc.combine(engine.evaluate(brands[r["brand_id"]], clean(r)))
            assert set(out) == RESULT_KEYS
            if r["ground_truth"] == "official":
                assert out["status"] == "CLEARED", f"{r['entity_id']} official asset not CLEARED"
