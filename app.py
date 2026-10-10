
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import streamlit as st

import social_engine
import app_engine
import score_engine
import clustering
from report_builder import build_report
from ui_components import render_metric_row, render_result_card


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

EVALUATION_ONLY_FIELDS = {
    "ground_truth",
    "category_note",
    "expected_ring",
}

STATUS_OPTIONS = [
    "All",
    "FLAGGED",
    "NOT_FLAGGED",
    "CLEARED",
]

TYPE_OPTIONS = {
    "All": "All types",
    "social_profile": "Social profiles",
    "app_listing": "App listings",
}

RISK_RANGES = {
    "All scores": (None, None),
    "Below 0.50": (None, 0.50),
    "0.50 to below 0.70": (0.50, 0.70),
    "0.70 and above": (0.70, None),
}


st.set_page_config(
    page_title="BrandShield AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def safe_text(value: Any) -> str:
    """Display missing values without guessing."""
    return "Not available" if value is None or value == "" else str(value)


def candidate_label(candidate: dict) -> str | None:
    """Return the dataset's supplied display label."""
    if candidate.get("target_type") == "social_profile":
        return candidate.get("display_name")
    if candidate.get("target_type") == "app_listing":
        return candidate.get("app_name")
    return None


def candidate_for_detection(candidate: dict) -> dict:
    """Remove evaluation-only fields before processing candidates."""
    return {
        key: value
        for key, value in candidate.items()
        if key not in EVALUATION_ONLY_FIELDS
    }


def load_json(filename: str) -> Any:
    """Load a repository dataset using a path relative to this file."""
    path = DATA_DIR / filename
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_datasets() -> tuple[list[dict], list[dict], list[dict]]:
    registry = load_json("brand_registry.json")
    social_profiles = load_json("social_profiles.json")
    app_listings = load_json("app_listings.json")

    brands = registry.get("brands")
    if not isinstance(brands, list):
        raise ValueError("Brand registry must contain a brands list.")

    if not isinstance(social_profiles, list):
        raise ValueError("Social profile dataset must be a list.")

    if not isinstance(app_listings, list):
        raise ValueError("App listing dataset must be a list.")

    return brands, social_profiles, app_listings


def canonical_json_bytes(report: dict) -> bytes:
    """Serialize a report into deterministic canonical JSON bytes."""
    text = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def build_report_safely(
    results: list[dict],
    brand: dict,
    candidates: list[dict],
    engine_outputs: list[dict],
    clusters: list[dict] | None = None,
) -> tuple[dict, bool]:
    """Retry without optional clusters only when cluster validation fails."""
    try:
        report = build_report(
            results,
            brand,
            candidates,
            engine_outputs,
            clusters=clusters,
        )
        return report, clusters is not None
    except ValueError:
        if clusters is None:
            raise

        report = build_report(
            results,
            brand,
            candidates,
            engine_outputs,
            clusters=None,
        )
        return report, False


def run_detection_pipeline(
    brand: dict,
    candidates: list[dict],
) -> tuple[list[dict], list[dict], list[dict], dict, bool]:
    """Run the shared detection, scoring, clustering and reporting pipeline."""
    engine_outputs = []
    results = []

    for candidate in candidates:
        target_type = candidate.get("target_type")

        if target_type == "social_profile":
            engine_output = social_engine.evaluate(brand, candidate)
        elif target_type == "app_listing":
            engine_output = app_engine.evaluate(brand, candidate)
        else:
            raise ValueError(
                f"Unsupported target type for {candidate.get('entity_id')}: "
                f"{target_type!r}"
            )

        engine_outputs.append(engine_output)

        # M4 owns all risk scores and final status decisions.
        results.append(score_engine.combine(engine_output))

    clusters = []
    clustering_available = True

    try:
        clusters = clustering.cluster(results, candidates)
    except ValueError as exc:
        clustering_available = False
        st.warning(
            "Threat Rings could not be generated. The core report "
            f"remains available. Details: {exc}"
        )

    report, report_clustering_available = build_report_safely(
        results,
        brand,
        candidates,
        engine_outputs,
        clusters=clusters if clustering_available else None,
    )

    clustering_available = (
        clustering_available and report_clustering_available
    )

    return results, engine_outputs, clusters, report, clustering_available


def matches_risk_range(score: Any, selected_range: str) -> bool:
    """Filter using the returned score; never modify or recompute it."""
    lower, upper = RISK_RANGES[selected_range]

    try:
        value = float(score)
    except (TypeError, ValueError):
        return False

    if lower is not None and value < lower:
        return False
    if upper is not None and value >= upper:
        return False
    return True


def main() -> None:
    st.title("🛡️ BrandShield AI")
    st.caption(
        "Brand impersonation monitoring prototype · Shared development dataset"
    )

    st.warning(
        "This dashboard uses simulated candidate records, not live detections "
        "or verified real-world findings. Risk scores and statuses come from "
        "the shared scoring engine."
    )

    try:
        brands, social_profiles, app_listings = load_datasets()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        st.error(f"Unable to load the local development datasets: {exc}")
        st.stop()

    if not brands:
        st.error("The brand registry contains no brands.")
        st.stop()

    brand_names = [brand["name"] for brand in brands]
    if len(brand_names) != len(set(brand_names)):
        st.error("Brand names must be unique for the current selector.")
        st.stop()

    with st.sidebar:
        st.header("Filters")

        selected_name = st.selectbox("Brand", brand_names)
        selected_brand = next(
            brand for brand in brands if brand["name"] == selected_name
        )

        brand_id = selected_brand["brand_id"]

        raw_candidates = [
            candidate
            for candidate in social_profiles + app_listings
            if candidate.get("brand_id") == brand_id
        ]

        # Strip evaluation labels before candidates enter any pipeline stage.
        candidates = [
            candidate_for_detection(candidate)
            for candidate in raw_candidates
        ]

        status_filter = st.selectbox("Status", STATUS_OPTIONS)

        type_filter = st.selectbox(
            "Entity type",
            list(TYPE_OPTIONS),
            format_func=lambda value: TYPE_OPTIONS[value],
        )

        platform_options = [
            "All",
            *sorted({
                str(candidate["platform"])
                for candidate in candidates
                if candidate.get("platform")
            }),
        ]
        platform_filter = st.selectbox("Platform", platform_options)

        risk_filter = st.selectbox(
            "Risk score range",
            list(RISK_RANGES),
        )

        search = st.text_input(
            "Search",
            placeholder="Name, username, package ID...",
        )

        st.divider()
        st.caption(
            "Filters affect displayed cards only. Metrics and exports cover "
            "the complete selected-brand dataset."
        )

    if not candidates:
        st.info("No candidates are available for this brand.")
        st.stop()

    try:
        results, engine_outputs, clusters, report, clustering_available = (
            run_detection_pipeline(selected_brand, candidates)
        )
    except Exception as exc:
        st.error(f"Unable to generate the detection report: {exc}")
        st.stop()

    candidates_by_id = {
        candidate["entity_id"]: candidate
        for candidate in candidates
    }

    rows = []

    for result in results:
        candidate = candidates_by_id.get(result.get("entity_id"), {})
        label = candidate_label(candidate)

        searchable = " ".join(
            str(value or "")
            for value in (
                result.get("entity_id"),
                result.get("identifier"),
                result.get("platform"),
                result.get("target_type"),
                label,
                candidate.get("username"),
                candidate.get("app_name"),
                candidate.get("display_name"),
                candidate.get("package_id"),
                candidate.get("publisher"),
            )
        ).casefold()

        if (
            status_filter != "All"
            and result.get("status") != status_filter
        ):
            continue

        if (
            type_filter != "All"
            and result.get("target_type") != type_filter
        ):
            continue

        if (
            platform_filter != "All"
            and result.get("platform") != platform_filter
        ):
            continue

        if not matches_risk_range(result.get("risk_score"), risk_filter):
            continue

        if search.strip() and search.strip().casefold() not in searchable:
            continue

        rows.append((result, candidate, label))

    # Metrics always describe the complete selected-brand result set.
    flagged = sum(result.get("status") == "FLAGGED" for result in results)
    review = sum(bool(result.get("review_required")) for result in results)
    cleared = sum(result.get("status") == "CLEARED" for result in results)

    st.subheader(f"Monitoring: {selected_brand['name']}")
    render_metric_row(
        total=len(results),
        flagged=flagged,
        review=review,
        cleared=cleared,
    )

    st.subheader(f"Entities ({len(rows)} shown)")

    if not rows:
        st.info("No entities match these filters.")
    else:
        for result, candidate, label in rows:
            render_result_card(result, candidate, label, safe_text)

    st.divider()
    st.subheader("Export report")
    st.write(
        "Download the complete report for the selected brand as canonical JSON."
    )

    if clustering_available:
        st.caption(
            f"Threat Rings available: {len(report['clusters'])} clusters. "
            "Connections indicate possible links, not confirmed common ownership."
        )
    else:
        st.caption(
            "Threat Rings are unavailable. The core report remains available."
        )

    exported_bytes = canonical_json_bytes(report)
    digest = hashlib.sha256(exported_bytes).hexdigest()

    left, right = st.columns([2, 3])

    with left:
        st.download_button(
            label="⬇️ Download JSON report",
            data=exported_bytes,
            file_name=f"brandshield_{selected_brand['brand_id']}_report.json",
            mime="application/json",
            use_container_width=True,
        )

    with right:
        st.caption("SHA-256 of the exact bytes offered for download")
        st.code(digest, language=None)

    with st.expander("Preview report structure"):
        st.json(report, expanded=False)

    st.caption(
        "This prototype uses simulated candidate data. The scoring engine "
        "supplies risk scores and statuses. The SHA-256 hash verifies the "
        "exported bytes, not the authenticity of the underlying evidence."
    )


if __name__ == "__main__":
    main()
