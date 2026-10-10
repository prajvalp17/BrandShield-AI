
from clustering import cluster


def test_exact_contact_number_links_flagged_candidates():
    results = [
        {"entity_id": "app_01", "status": "FLAGGED"},
        {"entity_id": "soc_01", "status": "FLAGGED"},
    ]

    candidates = [
        {"entity_id": "app_01", "contact_number": "+91 98765-43210"},
        {"entity_id": "soc_01", "contact_number": "919876543210"},
    ]

    clusters = cluster(results, candidates)

    assert len(clusters) == 1
    assert clusters[0]["ring_id"] == "ring_001"
    assert clusters[0]["linked_candidate_ids"] == ["app_01", "soc_01"]
    assert clusters[0]["link_reasons"][0]["indicator_type"] == "contact_number"


def test_non_flagged_candidates_are_not_linked():
    results = [
        {"entity_id": "app_01", "status": "NOT_FLAGGED"},
        {"entity_id": "app_02", "status": "FLAGGED"},
    ]

    candidates = [
        {"entity_id": "app_01", "contact_number": "123456789"},
        {"entity_id": "app_02", "contact_number": "123456789"},
    ]

    assert cluster(results, candidates) == []


def test_domain_only_match_does_not_link():
    results = [
        {"entity_id": "app_01", "status": "FLAGGED"},
        {"entity_id": "app_02", "status": "FLAGGED"},
    ]

    candidates = [
        {"entity_id": "app_01", "redirect_url": "https://example.com/login"},
        {"entity_id": "app_02", "redirect_url": "https://example.com/pay"},
    ]

    assert cluster(results, candidates) == []


def test_identical_full_redirect_urls_link():
    results = [
        {"entity_id": "app_01", "status": "FLAGGED"},
        {"entity_id": "app_02", "status": "FLAGGED"},
    ]

    candidates = [
        {"entity_id": "app_01", "redirect_url": "HTTPS://EXAMPLE.COM/login"},
        {"entity_id": "app_02", "redirect_url": "https://example.com/login"},
    ]

    clusters = cluster(results, candidates)

    assert len(clusters) == 1
    assert clusters[0]["link_reasons"][0]["indicator_type"] == "redirect_url"


def test_one_digit_apart_phone_numbers_do_not_link():
    results = [
        {"entity_id": "app_01", "status": "FLAGGED"},
        {"entity_id": "app_02", "status": "FLAGGED"},
    ]

    candidates = [
        {"entity_id": "app_01", "contact_number": "9876543210"},
        {"entity_id": "app_02", "contact_number": "9876543211"},
    ]

    assert cluster(results, candidates) == []


def test_connected_candidates_form_one_cluster():
    results = [
        {"entity_id": "app_01", "status": "FLAGGED"},
        {"entity_id": "app_02", "status": "FLAGGED"},
        {"entity_id": "soc_01", "status": "FLAGGED"},
    ]

    candidates = [
        {"entity_id": "app_01", "contact_number": "1111111111"},
        {"entity_id": "app_02", "contact_number": "1111111111",
         "redirect_url": "https://example.com/login"},
        {"entity_id": "soc_01", "redirect_url": "https://example.com/login"},
    ]

    clusters = cluster(results, candidates)

    assert len(clusters) == 1
    assert clusters[0]["linked_candidate_ids"] == [
        "app_01", "app_02", "soc_01"
    ]
    assert len(clusters[0]["link_reasons"]) == 2


def test_each_candidate_belongs_to_at_most_one_cluster():
    results = [
        {"entity_id": "app_01", "status": "FLAGGED"},
        {"entity_id": "app_02", "status": "FLAGGED"},
        {"entity_id": "app_03", "status": "FLAGGED"},
        {"entity_id": "app_04", "status": "FLAGGED"},
    ]

    candidates = [
        {"entity_id": "app_01", "contact_number": "1111111111"},
        {"entity_id": "app_02", "contact_number": "1111111111"},
        {"entity_id": "app_03", "contact_number": "2222222222"},
        {"entity_id": "app_04", "contact_number": "2222222222"},
    ]

    clusters = cluster(results, candidates)

    all_ids = [
        entity_id
        for item in clusters
        for entity_id in item["linked_candidate_ids"]
    ]

    assert len(all_ids) == len(set(all_ids))
    assert len({item["ring_id"] for item in clusters}) == len(clusters)
