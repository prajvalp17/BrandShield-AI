
"""
BrandShield AI - Threat Ring Clustering
Member 3: Optional clustering

Contract interface:
    cluster(results: list[dict], candidates: list[dict]) -> list[dict]

Only FLAGGED candidates are linked. A link requires an exact match
on a normalized contact number or normalized full redirect URL.

Clustering does not calculate or modify risk scores.
"""

from itertools import combinations

from normalization import (
    normalize_contact_number,
    normalize_redirect_url,
)


def cluster(results: list[dict], candidates: list[dict]) -> list[dict]:
    """
    Group FLAGGED candidates using shared normalized indicators.

    Args:
        results: Frozen final results from score_engine.combine().
        candidates: Original candidate input records.

    Returns:
        A list of disjoint clusters. Each cluster contains:
            ring_id
            linked_candidate_ids
            link_reasons

        Every link reason contains:
            candidate_id_1
            candidate_id_2
            indicator_type
            reason
    """

    # Index original candidates by entity_id.
    candidates_by_id = {}

    for candidate in candidates:
        entity_id = candidate.get("entity_id")
        if entity_id is not None:
            candidates_by_id[str(entity_id)] = candidate

    # Frozen results determine which candidates are FLAGGED.
    # The original candidates supply the raw indicators.
    flagged = {}

    for result in results:
        if result.get("status") != "FLAGGED":
            continue

        entity_id = result.get("entity_id")
        if entity_id is None:
            continue

        entity_id = str(entity_id)
        candidate = candidates_by_id.get(entity_id)

        if candidate is None:
            # No candidate record means there are no trustworthy
            # indicators to use for clustering.
            continue

        contact_number = normalize_contact_number(
            candidate.get("contact_number")
        )
        redirect_url = normalize_redirect_url(
            candidate.get("redirect_url")
        )

        flagged[entity_id] = {
            "contact_number": contact_number,
            "redirect_url": redirect_url,
        }

    candidate_ids = sorted(flagged)

    # Union-Find data structure.
    parent = {
        entity_id: entity_id
        for entity_id in candidate_ids
    }

    def find(entity_id):
        """Find the representative of a connected component."""
        while parent[entity_id] != entity_id:
            parent[entity_id] = parent[parent[entity_id]]
            entity_id = parent[entity_id]

        return entity_id

    def union(entity_a, entity_b):
        """Merge two connected components deterministically."""
        root_a = find(entity_a)
        root_b = find(entity_b)

        if root_a == root_b:
            return

        smaller, larger = sorted((root_a, root_b))
        parent[larger] = smaller

    # Store each direct link and its explicit reason.
    link_reasons = []

    for entity_a, entity_b in combinations(candidate_ids, 2):
        indicators_a = flagged[entity_a]
        indicators_b = flagged[entity_b]

        reasons_for_pair = []

        contact_a = indicators_a["contact_number"]
        contact_b = indicators_b["contact_number"]

        if contact_a and contact_b and contact_a == contact_b:
            reasons_for_pair.append({
                "candidate_id_1": entity_a,
                "candidate_id_2": entity_b,
                "indicator_type": "contact_number",
                "reason": "Exact match on normalized contact number",
            })

        url_a = indicators_a["redirect_url"]
        url_b = indicators_b["redirect_url"]

        if url_a and url_b and url_a == url_b:
            reasons_for_pair.append({
                "candidate_id_1": entity_a,
                "candidate_id_2": entity_b,
                "indicator_type": "redirect_url",
                "reason": "Exact match on normalized full redirect URL",
            })

        if reasons_for_pair:
            union(entity_a, entity_b)
            link_reasons.extend(reasons_for_pair)

    # Collect candidates by connected component.
    components = {}

    for entity_id in candidate_ids:
        root = find(entity_id)
        components.setdefault(root, []).append(entity_id)

    # Only components with two or more linked candidates are clusters.
    linked_components = [
        sorted(members)
        for members in components.values()
        if len(members) > 1
    ]

    # Deterministic ring assignment.
    linked_components.sort(key=lambda members: members[0])

    clusters = []

    for index, members in enumerate(linked_components, start=1):
        member_set = set(members)

        reasons = [
            reason
            for reason in link_reasons
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


def find_suspicious_clusters(results: list[dict],
                             candidates: list[dict]) -> list[dict]:
    """Descriptive alias for the contract's cluster() function."""
    return cluster(results, candidates)


def detect_clusters(results: list[dict],
                    candidates: list[dict]) -> list[dict]:
    """Compatibility alias for callers using detect_clusters()."""
    return cluster(results, candidates)
