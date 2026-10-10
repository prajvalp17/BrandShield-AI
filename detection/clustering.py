
"""
BrandShield AI - Suspicious Cluster Detection
Member 3: App Detection & Clustering

Links FLAGGED candidates using exact normalized contact numbers
or exact normalized full redirect URLs.

This module does not calculate risk scores.
"""

from itertools import combinations

from normalization import (
    normalize_contact_number,
    normalize_redirect_url,
)


def find_suspicious_clusters(results: list[dict]) -> list[dict]:
    """
    Build clusters from final evaluation results.

    Expected result fields:
        entity_id
        status
        indicators:
            contact_number
            redirect_url

    Only candidates whose final status is FLAGGED can be linked.

    Returns:
        A list of cluster dictionaries containing ring_id,
        linked_candidate_ids, and link_reasons.
    """

    flagged = {}

    for result in results:
        if result.get("status") != "FLAGGED":
            continue

        entity_id = result.get("entity_id")
        if entity_id is None:
            continue

        indicators = result.get("indicators") or {}

        # Normalize again so this function works with raw or
        # already-normalized indicator values.
        contact_number = normalize_contact_number(
            indicators.get("contact_number")
        )
        redirect_url = normalize_redirect_url(
            indicators.get("redirect_url")
        )

        flagged[str(entity_id)] = {
            "contact_number": contact_number,
            "redirect_url": redirect_url,
        }

    candidate_ids = sorted(flagged)
    parent = {candidate_id: candidate_id for candidate_id in candidate_ids}

    def find(candidate_id):
        while parent[candidate_id] != candidate_id:
            parent[candidate_id] = parent[parent[candidate_id]]
            candidate_id = parent[candidate_id]
        return candidate_id

    def union(candidate_a, candidate_b):
        root_a = find(candidate_a)
        root_b = find(candidate_b)

        if root_a != root_b:
            # Deterministic root selection.
            smaller, larger = sorted((root_a, root_b))
            parent[larger] = smaller

    pair_reasons = []

    for candidate_a, candidate_b in combinations(candidate_ids, 2):
        indicators_a = flagged[candidate_a]
        indicators_b = flagged[candidate_b]

        reasons = []

        contact_a = indicators_a["contact_number"]
        contact_b = indicators_b["contact_number"]

        if contact_a and contact_b and contact_a == contact_b:
            reasons.append({
                "candidate_id_1": candidate_a,
                "candidate_id_2": candidate_b,
                "indicator_type": "contact_number",
                "reason": "Exact match on normalized contact number",
            })

        url_a = indicators_a["redirect_url"]
        url_b = indicators_b["redirect_url"]

        if url_a and url_b and url_a == url_b:
            reasons.append({
                "candidate_id_1": candidate_a,
                "candidate_id_2": candidate_b,
                "indicator_type": "redirect_url",
                "reason": "Exact match on normalized full redirect URL",
            })

        if reasons:
            union(candidate_a, candidate_b)
            pair_reasons.extend(reasons)

    # Group linked candidates by connected component.
    components = {}

    for candidate_id in candidate_ids:
        root = find(candidate_id)
        components.setdefault(root, []).append(candidate_id)

    # Keep only components containing at least one actual link.
    linked_components = [
        sorted(members)
        for members in components.values()
        if len(members) > 1
    ]
    linked_components.sort(key=lambda members: members[0])

    clusters = []

    for index, members in enumerate(linked_components, start=1):
        member_set = set(members)

        reasons = [
            reason
            for reason in pair_reasons
            if (
                reason["candidate_id_1"] in member_set
                and reason["candidate_id_2"] in member_set
            )
        ]

        clusters.append({
            "ring_id": f"ring_{index:03d}",
            "linked_candidate_ids": members,
            "link_reasons": reasons,
        })

    return clusters


# Compatibility alias for callers that prefer a shorter name.
def detect_clusters(results: list[dict]) -> list[dict]:
    """Alias for find_suspicious_clusters()."""
    return find_suspicious_clusters(results)
