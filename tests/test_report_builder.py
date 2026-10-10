import pytest

from clustering import cluster
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


def _valid_cluster_inputs():
    entity_ids = ("c1", "c2", "c3", "c4")
    results = [
        {
            "entity_id": entity_id,
            "target_type": "social_profile",
            "platform": "X",
            "identifier": f"@{entity_id}",
            "risk_score": 0.9,
            "status": "FLAGGED",
            "is_official": False,
            "signals": {},
            "reasons": [],
            "exclusion_reason": None,
            "review_required": False,
            "evidence_source": "simulated",
            "evidence_timestamp": None,
            "ring_id": None,
        }
        for entity_id in entity_ids
    ]
    candidates = [
        {
            "entity_id": "c1",
            "target_type": "social_profile",
            "platform": "X",
            "brand_id": "brand_01",
            "evidence_source": "simulated",
            "display_name": "Candidate 1",
            "contact_number": "+91 90000 11111",
            "redirect_url": None,
        },
        {
            "entity_id": "c2",
            "target_type": "social_profile",
            "platform": "X",
            "brand_id": "brand_01",
            "evidence_source": "simulated",
            "display_name": "Candidate 2",
            "contact_number": "90000 11111",
            "redirect_url": None,
        },
        {
            "entity_id": "c3",
            "target_type": "social_profile",
            "platform": "X",
            "brand_id": "brand_01",
            "evidence_source": "simulated",
            "display_name": "Candidate 3",
            "contact_number": None,
            "redirect_url": "http://bad.example/pay",
        },
        {
            "entity_id": "c4",
            "target_type": "social_profile",
            "platform": "X",
            "brand_id": "brand_01",
            "evidence_source": "simulated",
            "display_name": "Candidate 4",
            "contact_number": None,
            "redirect_url": "http://bad.example/pay",
        },
    ]
    engine_outputs = [
        {"entity_id": entity_id, "evidence": {"source": entity_id}}
        for entity_id in entity_ids
    ]
    clusters = cluster(results, candidates)
    return (
        results,
        {"brand_id": "brand_01", "name": "Brand One"},
        candidates,
        engine_outputs,
        clusters,
    )


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
    results, brand, candidates, engine_outputs, clusters = _valid_cluster_inputs()
    clusters = list(reversed(clusters))

    report = build_report(results, brand, candidates, engine_outputs, clusters)

    assert [item["entity_id"] for item in report["results"]] == [
        "c1", "c2", "c3", "c4",
    ]
    assert [cluster["ring_id"] for cluster in report["clusters"]] == [
        "ring_001", "ring_002",
    ]
    assert [item["ring_id"] for item in report["results"]] == [
        "ring_001", "ring_001", "ring_002", "ring_002",
    ]


def test_build_report_preserves_link_reasons_and_ring_assignment():
    results, brand, candidates, engine_outputs, clusters = _valid_cluster_inputs()

    report = build_report(results, brand, candidates, engine_outputs, clusters)

    assert report["clusters"][0]["link_reasons"][0] == {
        "candidate_id_1": "c1",
        "candidate_id_2": "c2",
        "indicator_type": "contact_number",
        "reason": "Exact match on normalized contact number",
    }
    assert report["clusters"][1]["link_reasons"][0] == {
        "candidate_id_1": "c3",
        "candidate_id_2": "c4",
        "indicator_type": "redirect_url",
        "reason": "Exact match on normalized full redirect URL",
    }
    assert [item["ring_id"] for item in report["results"]] == [
        "ring_001", "ring_001", "ring_002", "ring_002",
    ]


def test_build_report_keeps_unassigned_results_none_for_valid_clusters():
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
    clusters = [{"ring_id": "ring_01", "linked_candidate_ids": ["soc_99"]}]

    report = build_report(results, brand, candidates, engine_outputs, clusters)

    assert len(report["clusters"]) == 1
    assert report["clusters"][0]["ring_id"] == "ring_01"
    assert report["results"][0]["ring_id"] is None
    assert report["results"][1]["ring_id"] is None


def test_build_report_rejects_candidate_in_multiple_clusters():
    clusters = [
        {"ring_id": "ring_01", "linked_candidate_ids": ["soc_01"]},
        {"ring_id": "ring_02", "linked_candidate_ids": ["soc_01"]},
    ]

    with pytest.raises(ValueError, match="soc_01"):
        build_report([], {}, [], [], clusters)


def test_build_report_rejects_duplicate_ring_ids():
    clusters = [
        {"ring_id": "ring_01", "linked_candidate_ids": ["soc_01"]},
        {"ring_id": "ring_01", "linked_candidate_ids": ["soc_02"]},
    ]

    with pytest.raises(ValueError, match="ring_01"):
        build_report([], {}, [], [], clusters)


def test_build_report_rejects_cluster_missing_ring_id():
    with pytest.raises(ValueError, match="ring_id"):
        build_report([], {}, [], [], [{"linked_candidate_ids": ["soc_01"]}])


def test_build_report_rejects_cluster_missing_linked_candidate_ids():
    with pytest.raises(ValueError, match="linked_candidate_ids"):
        build_report([], {}, [], [], [{"ring_id": "ring_01"}])


@pytest.mark.parametrize("cluster", [
    123,
    {"ring_id": "ring_01", "linked_candidate_ids": None},
])
def test_build_report_rejects_malformed_cluster_records(cluster):
    with pytest.raises(ValueError):
        build_report([], {}, [], [], [cluster])


def test_build_report_allows_repeated_candidate_ids_within_one_cluster():
    result = {"entity_id": "soc_01", "signals": {}, "reasons": [], "ring_id": None}
    clusters = [{"ring_id": "ring_01", "linked_candidate_ids": ["soc_01", "soc_01"]}]

    report = build_report([result], {}, [], [], clusters)

    assert report["results"][0]["ring_id"] == "ring_01"
    assert report["clusters"][0]["linked_candidate_ids"] == ["soc_01", "soc_01"]


def test_build_report_does_not_mutate_input_results_or_candidates():
    results = [{
        "entity_id": "soc_03",
        "target_type": "social_profile",
        "platform": "Instagram",
        "identifier": "@gamma",
        "risk_score": 0.2,
        "status": "NOT_FLAGGED",
        "is_official": False,
        "signals": {"detail": {"values": ["original"]}},
        "reasons": [{"detail": ["original"]}],
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
    report["results"][0]["signals"]["detail"]["values"].append("report")
    report["results"][0]["reasons"][0]["detail"].append("report")

    assert results[0] == original_result
    assert results[0]["signals"]["detail"]["values"] == ["original"]
    assert results[0]["reasons"][0]["detail"] == ["original"]
    assert report["results"][0]["label"] == "Gamma"
    assert report["results"][0]["evidence"] == {"k": "v"}
    assert "label" not in results[0]
    assert "evidence" not in results[0]


def test_report_mutates_nested_evidence_without_changing_engine_outputs():
    results = [{
        "entity_id": "soc_04",
        "target_type": "social_profile",
        "platform": "Instagram",
        "identifier": "@delta",
        "risk_score": 0.55,
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
    candidates = [{"entity_id": "soc_04", "target_type": "social_profile", "display_name": "Delta"}]
    engine_outputs = [{"entity_id": "soc_04", "evidence": {"detail": {"note": "keep"}}}]

    report = build_report(results, {"brand_id": "brand_06", "name": "Brand Six"}, candidates, engine_outputs)
    report["results"][0]["evidence"]["detail"]["note"] = "changed"

    assert engine_outputs[0]["evidence"] == {"detail": {"note": "keep"}}
    assert report["results"][0]["evidence"]["detail"]["note"] == "changed"


def test_report_mutates_nested_link_reasons_without_changing_clusters_input():
    results, brand, candidates, engine_outputs, clusters = _valid_cluster_inputs()

    report = build_report(results, brand, candidates, engine_outputs, clusters)
    report["clusters"][0]["link_reasons"][0]["reason"] = "modified"

    assert (
        clusters[0]["link_reasons"][0]["reason"]
        == "Exact match on normalized contact number"
    )
    assert report["clusters"][0]["link_reasons"][0]["reason"] == "modified"
