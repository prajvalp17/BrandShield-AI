from report_builder import build_report


def _sample_results():
    return [
        {
            "entity_id": "soc_02",
            "target_type": "social_profile",
            "platform": "Instagram",
            "identifier": "@beta",
            "risk_score": 0.65,
            "status": "NOT_FLAGGED",
            "is_official": False,
            "signals": {"handle_similarity": {"value": 0.7, "category": "identity", "reason": "similar"}},
            "reasons": ["Borderline risk"],
            "exclusion_reason": None,
            "review_required": True,
            "evidence_source": "simulated",
            "evidence_timestamp": None,
            "ring_id": None,
        },
        {
            "entity_id": "soc_01",
            "target_type": "social_profile",
            "platform": "Instagram",
            "identifier": "@alpha",
            "risk_score": 0.0,
            "status": "CLEARED",
            "is_official": True,
            "signals": {},
            "reasons": ["Matched official asset"],
            "exclusion_reason": "official_asset",
            "review_required": False,
            "evidence_source": "simulated",
            "evidence_timestamp": None,
            "ring_id": None,
        },
    ]


def test_build_report_uses_exact_top_level_keys_and_preserves_frozen_result_fields():
    results = _sample_results()
    brand = {"brand_id": "brand_01", "name": "Example Brand"}
    candidates = [
        {"entity_id": "soc_01", "target_type": "social_profile", "display_name": "Alpha Support"},
        {"entity_id": "soc_02", "target_type": "social_profile", "display_name": "Beta Support"},
    ]
    engine_outputs = [
        {"entity_id": "soc_01", "evidence": {"source": "official registry"}},
        {"entity_id": "soc_02", "evidence": {"source": "manual review"}},
    ]

    report = build_report(results, brand, candidates, engine_outputs)

    assert list(report.keys()) == ["brand", "results", "clusters"]
    assert report["brand"] == {"brand_id": "brand_01", "name": "Example Brand"}
    assert report["clusters"] == []
    assert report["results"][0]["entity_id"] == "soc_01"
    assert report["results"][0]["label"] == "Alpha Support"
    assert report["results"][0]["evidence"] == {"source": "official registry"}
    assert report["results"][0]["status"] == "CLEARED"
    assert report["results"][0]["ring_id"] is None
    assert report["results"][0]["risk_score"] == 0.0


def test_build_report_uses_app_label_and_engine_evidence_by_entity_id():
    results = [{
        "entity_id": "app_01",
        "target_type": "app_listing",
        "platform": "Android",
        "identifier": "com.example.app",
        "risk_score": 0.8,
        "status": "FLAGGED",
        "is_official": False,
        "signals": {},
        "reasons": ["suspicious app"],
        "exclusion_reason": None,
        "review_required": False,
        "evidence_source": "simulated",
        "evidence_timestamp": None,
        "ring_id": None,
    }]
    brand = {"brand_id": "brand_02", "name": "Brand Two"}
    candidates = [{"entity_id": "app_01", "target_type": "app_listing", "app_name": "Example App"}]
    engine_outputs = [{"entity_id": "app_01", "evidence": {"matched_package": "com.example.app"}}]

    report = build_report(results, brand, candidates, engine_outputs)

    assert report["results"][0]["label"] == "Example App"
    assert report["results"][0]["evidence"] == {"matched_package": "com.example.app"}
    assert report["results"][0]["status"] == "FLAGGED"


def test_build_report_sets_ring_id_from_clusters_and_sorts_deterministically():
    results = [
        {"entity_id": "soc_02", "target_type": "social_profile", "platform": "Instagram", "identifier": "@beta", "risk_score": 0.5, "status": "NOT_FLAGGED", "is_official": False, "signals": {}, "reasons": [], "exclusion_reason": None, "review_required": False, "evidence_source": "simulated", "evidence_timestamp": None, "ring_id": None},
        {"entity_id": "soc_01", "target_type": "social_profile", "platform": "Instagram", "identifier": "@alpha", "risk_score": 0.7, "status": "FLAGGED", "is_official": False, "signals": {}, "reasons": [], "exclusion_reason": None, "review_required": False, "evidence_source": "simulated", "evidence_timestamp": None, "ring_id": None},
    ]
    brand = {"brand_id": "brand_03", "name": "Brand Three"}
    candidates = [
        {"entity_id": "soc_01", "target_type": "social_profile", "display_name": "Alpha Support"},
        {"entity_id": "soc_02", "target_type": "social_profile", "display_name": "Beta Support"},
    ]
    engine_outputs = [
        {"entity_id": "soc_01", "evidence": {"match": "a"}},
        {"entity_id": "soc_02", "evidence": {"match": "b"}},
    ]
    clusters = [
        {"ring_id": "ring_b", "linked_candidate_ids": ["soc_02"]},
        {"ring_id": "ring_a", "linked_candidate_ids": ["soc_01"]},
    ]

    report = build_report(results, brand, candidates, engine_outputs, clusters)

    assert [item["entity_id"] for item in report["results"]] == ["soc_01", "soc_02"]
    assert [cluster["ring_id"] for cluster in report["clusters"]] == ["ring_a", "ring_b"]
    assert report["results"][0]["ring_id"] == "ring_a"
    assert report["results"][1]["ring_id"] == "ring_b"


def test_build_report_preserves_link_reasons_and_ring_assignment():
    results = [
        {"entity_id": "soc_01", "target_type": "social_profile", "platform": "Instagram", "identifier": "@alpha", "risk_score": 0.7, "status": "FLAGGED", "is_official": False, "signals": {}, "reasons": ["risk"], "exclusion_reason": None, "review_required": False, "evidence_source": "simulated", "evidence_timestamp": None, "ring_id": None},
        {"entity_id": "soc_02", "target_type": "social_profile", "platform": "Instagram", "identifier": "@beta", "risk_score": 0.2, "status": "NOT_FLAGGED", "is_official": False, "signals": {}, "reasons": [], "exclusion_reason": None, "review_required": False, "evidence_source": "simulated", "evidence_timestamp": None, "ring_id": None},
        {"entity_id": "soc_03", "target_type": "social_profile", "platform": "Instagram", "identifier": "@gamma", "risk_score": 0.1, "status": "NOT_FLAGGED", "is_official": False, "signals": {}, "reasons": [], "exclusion_reason": None, "review_required": False, "evidence_source": "simulated", "evidence_timestamp": None, "ring_id": None},
    ]
    brand = {"brand_id": "brand_04", "name": "Brand Four"}
    candidates = [
        {"entity_id": "soc_01", "target_type": "social_profile", "display_name": "Alpha"},
        {"entity_id": "soc_02", "target_type": "social_profile", "display_name": "Beta"},
        {"entity_id": "soc_03", "target_type": "social_profile", "display_name": "Gamma"},
    ]
    engine_outputs = [
        {"entity_id": "soc_01", "evidence": {"note": "alpha"}},
        {"entity_id": "soc_02", "evidence": {"note": "beta"}},
        {"entity_id": "soc_03", "evidence": {"note": "gamma"}},
    ]
    clusters = [
        {"ring_id": "ring_01", "linked_candidate_ids": ["soc_01", "soc_02"], "link_reasons": [{"from": "soc_01", "to": "soc_02", "reason": "shared redirect"}]},
        {"ring_id": "ring_02", "linked_candidate_ids": ["soc_03"], "link_reasons": [{"from": "soc_03", "to": "soc_03", "reason": "solo ring"}]},
    ]

    report = build_report(results, brand, candidates, engine_outputs, clusters)

    assert report["clusters"][0]["link_reasons"][0]["reason"] == "shared redirect"
    assert report["results"][0]["ring_id"] == "ring_01"
    assert report["results"][1]["ring_id"] == "ring_01"
    assert report["results"][2]["ring_id"] == "ring_02"


def test_build_report_keeps_unassigned_results_none_and_ignores_malformed_clusters():
    results = [
        {"entity_id": "soc_01", "target_type": "social_profile", "platform": "Instagram", "identifier": "@alpha", "risk_score": 0.1, "status": "NOT_FLAGGED", "is_official": False, "signals": {}, "reasons": [], "exclusion_reason": None, "review_required": False, "evidence_source": "simulated", "evidence_timestamp": None, "ring_id": None},
        {"entity_id": "soc_02", "target_type": "social_profile", "platform": "Instagram", "identifier": "@beta", "risk_score": 0.2, "status": "NOT_FLAGGED", "is_official": False, "signals": {}, "reasons": [], "exclusion_reason": None, "review_required": False, "evidence_source": "simulated", "evidence_timestamp": None, "ring_id": None},
    ]
    brand = {"brand_id": "brand_05", "name": "Brand Five"}
    candidates = [
        {"entity_id": "soc_01", "target_type": "social_profile", "display_name": "Alpha"},
        {"entity_id": "soc_02", "target_type": "social_profile", "display_name": "Beta"},
    ]
    engine_outputs = [
        {"entity_id": "soc_01", "evidence": {}},
        {"entity_id": "soc_02", "evidence": {}},
    ]
    clusters = [
        {"ring_id": "ring_01", "linked_candidate_ids": ["soc_99"]},
        {"ring_id": None, "linked_candidate_ids": ["soc_02"]},
        123,
        {"linked_candidate_ids": ["soc_01"]},
    ]

    report = build_report(results, brand, candidates, engine_outputs, clusters)

    assert len(report["clusters"]) == 1
    assert report["clusters"][0]["ring_id"] == "ring_01"
    assert report["results"][0]["ring_id"] is None
    assert report["results"][1]["ring_id"] is None


def test_build_report_does_not_mutate_input_results_or_candidates():
    results = [{
        "entity_id": "soc_03",
        "target_type": "social_profile",
        "platform": "Instagram",
        "identifier": "@gamma",
        "risk_score": 0.2,
        "status": "NOT_FLAGGED",
        "is_official": False,
        "signals": {},
        "reasons": [],
        "exclusion_reason": None,
        "review_required": False,
        "evidence_source": "simulated",
        "evidence_timestamp": None,
        "ring_id": None,
    }]
    original_result = dict(results[0])
    candidates = [{"entity_id": "soc_03", "target_type": "social_profile", "display_name": "Gamma"}]
    engine_outputs = [{"entity_id": "soc_03", "evidence": {"k": "v"}}]

    report = build_report(results, {"brand_id": "brand_04", "name": "Brand Four"}, candidates, engine_outputs)

    assert results[0] == original_result
    assert report["results"][0]["label"] == "Gamma"
    assert report["results"][0]["evidence"] == {"k": "v"}
    assert "label" not in results[0]
    assert "evidence" not in results[0]
