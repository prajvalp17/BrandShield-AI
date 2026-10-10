from __future__ import annotations
from copy import deepcopy
from typing import Any


def _safe_label(candidate: dict[str, Any] | None, target_type: str | None) -> Any:
    if not isinstance(candidate, dict):
        return None
    if target_type == "social_profile":
        return candidate.get("display_name")
    if target_type == "app_listing":
        return candidate.get("app_name")
    return None


def _sorted_clusters(clusters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not clusters:
        return []

    normalized: list[dict[str, Any]] = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        ring_id = cluster.get("ring_id")
        linked = cluster.get("linked_candidate_ids")
        if ring_id is None or not isinstance(linked, list):
            continue
        cleaned = deepcopy(cluster)
        cleaned["linked_candidate_ids"] = [str(entity_id) for entity_id in linked if entity_id is not None]
        normalized.append(cleaned)

    return sorted(
        normalized,
        key=lambda cluster: (
            cluster.get("ring_id") is None,
            str(cluster.get("ring_id") if cluster.get("ring_id") is not None else ""),
        ),
    )


def build_report(
    results: list[dict[str, Any]],
    brand: dict[str, Any],
    candidates: list[dict[str, Any]],
    engine_outputs: list[dict[str, Any]],
    clusters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the report data while preserving the frozen result schema."""
    candidate_by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates or []:
        if isinstance(candidate, dict):
            entity_id = candidate.get("entity_id")
            if entity_id is not None:
                candidate_by_id[str(entity_id)] = candidate

    engine_output_by_id: dict[str, dict[str, Any]] = {}
    for engine_output in engine_outputs or []:
        if isinstance(engine_output, dict):
            entity_id = engine_output.get("entity_id")
            if entity_id is not None:
                engine_output_by_id[str(entity_id)] = engine_output

    sorted_clusters = _sorted_clusters(clusters)
    cluster_by_entity: dict[str, Any] = {}
    for cluster in sorted_clusters:
        ring_id = cluster.get("ring_id")
        linked = cluster.get("linked_candidate_ids") or []
        if ring_id is None:
            continue
        for entity_id in linked:
            if entity_id is not None:
                cluster_by_entity[str(entity_id)] = ring_id

    report_results: list[dict[str, Any]] = []
    for result in sorted(results or [], key=lambda item: str(item.get("entity_id") if isinstance(item, dict) else "")):
        if not isinstance(result, dict):
            continue
        report_result = dict(result)
        entity_id = result.get("entity_id")
        candidate = candidate_by_id.get(str(entity_id)) if entity_id is not None else None
        report_result["label"] = _safe_label(candidate, candidate.get("target_type") if isinstance(candidate, dict) else None)

        engine_output = engine_output_by_id.get(str(entity_id)) if entity_id is not None else None
        evidence = engine_output.get("evidence") if isinstance(engine_output, dict) and isinstance(engine_output.get("evidence"), dict) else {}
        report_result["evidence"] = deepcopy(evidence)

        ring_id = cluster_by_entity.get(str(entity_id)) if entity_id is not None else None
        report_result["ring_id"] = ring_id if ring_id is not None else None
        report_results.append(report_result)

    return {
        "brand": {
            "brand_id": brand.get("brand_id") if isinstance(brand, dict) else None,
            "name": brand.get("name") if isinstance(brand, dict) else None,
        },
        "results": report_results,
        "clusters": sorted_clusters,
    }
