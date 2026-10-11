"""End-to-end contract checks on the REAL pipeline and the development data (CONTRACT v0.8.2).
engines -> score_engine.combine -> clustering.cluster -> report_builder.build_report.
Complements test_contract.py (synthetic cases) by running everything together on data/."""
import hashlib, json, os, random, re
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIDDEN = ("ground_truth", "category_note", "expected_ring")
FROZEN = {"entity_id", "target_type", "platform", "identifier", "risk_score", "status", "is_official", "signals",
          "reasons", "exclusion_reason", "review_required", "evidence_source", "evidence_timestamp", "ring_id"}
CATEGORY_OF = {"handle_similarity": "identity", "name_similarity": "identity", "scam_phrase": "content",
               "account_age": "metadata", "app_name_similarity": "identity", "package_similarity": "identity",
               "description_similarity": "content", "credential_bait": "content", "publisher_mismatch": "metadata"}

def canon(d):
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

@pytest.fixture(scope="module")
def pipeline():
    se, ae, sc, cl, rb = (pytest.importorskip(m) for m in
                          ("social_engine", "app_engine", "score_engine", "clustering", "report_builder"))
    load = lambda p: json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
    brands = {b["brand_id"]: b for b in load("data/brand_registry.json")["brands"]}
    cands, outs, res = [], [], []
    for eng, recs in ((se, load("data/social_profiles.json")), (ae, load("data/app_listings.json"))):
        for r in recs:
            c = {k: v for k, v in r.items() if k not in HIDDEN}
            eo = eng.evaluate(brands[r["brand_id"]], c)
            cands.append(c); outs.append(eo); res.append(sc.combine(eo))
    clusters = cl.cluster(res, cands)
    brand = brands["brand_01"]
    report = rb.build_report(res, brand, cands, outs, clusters)
    return dict(rb=rb, res=res, cands=cands, outs=outs, clusters=clusters, brand=brand, report=report,
                status={r["entity_id"]: r["status"] for r in res})

def test_report_top_level_and_brand(pipeline):
    rep = pipeline["report"]
    assert set(rep) == {"brand", "results", "clusters"}
    assert set(rep["brand"]) >= {"brand_id", "name"}

def test_report_results_have_frozen_fields_plus_label_and_evidence_only(pipeline):
    for x in pipeline["report"]["results"]:
        assert set(x) == FROZEN | {"label", "evidence"}, x["entity_id"]
        assert "evidence_hash" not in x

def test_report_ordering(pipeline):
    rep = pipeline["report"]
    ids = [x["entity_id"] for x in rep["results"]]
    rings = [c["ring_id"] for c in rep["clusters"]]
    assert ids == sorted(ids) and rings == sorted(rings)

def test_cluster_records_follow_ruling_25(pipeline):
    cl, status = pipeline["clusters"], pipeline["status"]
    assert cl, "expected at least one cluster on the development data"
    assert all(re.fullmatch(r"ring_\d{3}", c["ring_id"]) for c in cl)
    assert len({c["ring_id"] for c in cl}) == len(cl)
    seen = [i for c in cl for i in c["linked_candidate_ids"]]
    assert len(seen) == len(set(seen)), "a candidate is in two clusters"
    assert all(status[i] == "FLAGGED" for i in seen), "only FLAGGED candidates may be linked"
    for c in cl:
        ids = c["linked_candidate_ids"]
        assert len(ids) >= 2 and ids == sorted(ids)
        assert c["link_reasons"]
        for l in c["link_reasons"]:
            assert set(l) >= {"candidate_id_1", "candidate_id_2", "indicator_type", "reason"}
            assert l["indicator_type"] in {"contact_number", "redirect_url"} and l["reason"]
            assert l["candidate_id_1"] in ids and l["candidate_id_2"] in ids

def test_ring_id_only_in_report_copy(pipeline):
    ring = {i: c["ring_id"] for c in pipeline["clusters"] for i in c["linked_candidate_ids"]}
    assert all(r["ring_id"] is None for r in pipeline["res"]), "combine must leave ring_id None"
    assert all(x["ring_id"] == ring.get(x["entity_id"]) for x in pipeline["report"]["results"])

def test_labels_and_evidence_come_from_inputs(pipeline):
    cands = {c["entity_id"]: c for c in pipeline["cands"]}
    outs = {o["entity_id"]: o for o in pipeline["outs"]}
    for x in pipeline["report"]["results"]:
        c = cands[x["entity_id"]]
        assert x["label"] == c.get("display_name" if x["target_type"] == "social_profile" else "app_name")
        assert x["evidence"] == outs[x["entity_id"]]["evidence"]

def test_report_is_deterministic_and_hash_reproducible(pipeline):
    p = pipeline
    shuffled = list(p["res"]); random.Random(7).shuffle(shuffled)
    again = p["rb"].build_report(shuffled, p["brand"], p["cands"], p["outs"], p["clusters"])
    assert canon(p["report"]) == canon(again)
    assert hashlib.sha256(canon(p["report"])).hexdigest() == hashlib.sha256(canon(again)).hexdigest()

def test_report_rejects_bad_clusters_ruling_22(pipeline):
    p, cl = pipeline, pipeline["clusters"]
    dup = list(cl) + [{"ring_id": cl[0]["ring_id"], "linked_candidate_ids": ["x1", "x2"], "link_reasons": []}]
    overlap = [cl[0], {"ring_id": "ring_099", "linked_candidate_ids": [cl[0]["linked_candidate_ids"][0], "zz"], "link_reasons": []}]
    for bad in (dup, overlap):
        with pytest.raises(ValueError):
            p["rb"].build_report(p["res"], p["brand"], p["cands"], p["outs"], bad)

def test_every_flagged_record_has_two_independent_categories(pipeline):
    flagged = [r for r in pipeline["res"] if r["status"] == "FLAGGED"]
    assert flagged
    for r in flagged:
        active = {CATEGORY_OF[n] for n, v in r["signals"].items() if v >= 0.60}
        assert len(active) >= 2 and r["risk_score"] >= 0.70, r["entity_id"]

def test_official_assets_never_flagged_on_dev_data(pipeline):
    for r in pipeline["res"]:
        if r["is_official"]:
            assert r["status"] == "CLEARED" and r["risk_score"] == 0.0
