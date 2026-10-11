
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
from ui_components import (
    render_metric_row,
    render_result_card,
    render_threat_rings,
)

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
    # Premium BrandShield AI header
    st.markdown(
        """
<div style="padding: 34px 36px; margin: 20px 0 30px 0;
border: 1px solid rgba(96,165,250,0.55); border-radius: 22px;
background: linear-gradient(135deg, #1e3a5f 0%, #172554 55%, #172033 100%);
box-shadow: 0 16px 40px rgba(0,0,0,0.32);">
    <div style="color:#93c5fd; font-size:14px; font-weight:750;
    letter-spacing:2.5px; text-transform:uppercase; margin-bottom:16px;">
        BRAND PROTECTION · THREAT INTELLIGENCE
    </div>
    <div style="font-size:clamp(36px,4vw,52px); font-weight:850;
    color:#f8fafc; line-height:1.2;">
        🛡️ BrandShield <span style="color:#60a5fa">AI</span>
    </div>
    <div style="color:#d1dced; font-size:18px; margin-top:14px; line-height:1.6;">
        Monitor impersonation signals. Investigate possible connections.
    </div>
    <div style="margin-top:24px;">
        <span style="display:inline-block; padding:9px 14px;
        border-radius:20px; background:rgba(251,191,36,0.12);
        border:1px solid rgba(251,191,36,0.4); color:#fcd34d;
        font-size:13px; font-weight:750;">
            ● SIMULATED DATA · PROTOTYPE
        </span>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


    # Dashboard styling
    st.markdown(
        """
        <style>
        :root {
            --bs-accent: #60a5fa;
            --bs-border: rgba(148,163,184,0.25);
            --bs-muted: #b7c5d9;
        }

        .stApp {
            background:
                radial-gradient(
                    ellipse at 85% 0%,
                    rgba(37,99,235,0.16),
                    transparent 42%
                ),
                linear-gradient(
                    160deg,
                    #0b1020 0%,
                    #0e1422 55%,
                    #101827 100%
                );
        }

        .block-container {
            max-width: 1550px;
            padding-top: 1.5rem;
            padding-bottom: 3.5rem;
        }

        h1 {
            font-size: 2.8rem !important;
            font-weight: 800 !important;
            letter-spacing: -1px !important;
        }

        h2 {
            font-size: 2rem !important;
            font-weight: 750 !important;
        }

        h3 {
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: #93c5fd !important;
        }

        p, label {
            font-size: 1rem;
            line-height: 1.7;
        }

        [data-testid="stCaption"] {
            font-size: 0.98rem !important;
            line-height: 1.7;
            color: #b7c5d9;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: linear-gradient(
                180deg, #171e2d 0%, #121826 100%
            );
            border-right: 1px solid var(--bs-border);
        }

        [data-testid="stSidebar"] h2 {
            font-size: 1.3rem !important;
            color: #e7efff;
        }

        [data-testid="stSidebar"] label {
            font-size: 1rem !important;
        }

        /* Metric cards */
        [data-testid="stMetric"] {
            background: linear-gradient(
                145deg,
                rgba(30,41,59,0.98),
                rgba(17,24,39,0.98)
            );
            border: 1px solid rgba(96,165,250,0.34);
            border-radius: 18px;
            padding: 24px 22px;
            min-height: 112px;
            box-shadow: 0 10px 28px rgba(0,0,0,0.18);
            transition: border-color 160ms ease,
                        transform 160ms ease;
        }

        [data-testid="stMetric"]:hover {
            border-color: rgba(96,165,250,0.75);
            transform: translateY(-2px);
        }

        [data-testid="stMetricLabel"] p {
            color: var(--bs-muted) !important;
            font-size: 1rem !important;
            font-weight: 650 !important;
        }

        [data-testid="stMetricValue"] {
            color: #f1f6ff;
            font-size: 2.4rem !important;
            font-weight: 800 !important;
        }

        /* Candidate and Threat Ring panels */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: linear-gradient(
                145deg,
                rgba(24,34,51,0.92),
                rgba(15,22,35,0.96)
            );
            border: 1px solid var(--bs-border);
            border-radius: 18px;
            padding: 8px;
            box-shadow: 0 10px 28px rgba(0,0,0,0.16);
            transition: border-color 160ms ease;
        }

        [data-testid="stVerticalBlockBorderWrapper"]:hover {
            border-color: rgba(96,165,250,0.5);
        }

        [data-testid="stVerticalBlockBorderWrapper"] p {
            font-size: 1.05rem !important;
            line-height: 1.8 !important;
        }

        /* Filters */
        [data-testid="stSelectbox"] > div > div,
        [data-testid="stTextInput"] > div > div {
            border-radius: 11px;
        }

        [data-testid="stSelectbox"] > div > div:focus-within,
        [data-testid="stTextInput"] > div > div:focus-within {
            border-color: var(--bs-accent);
            box-shadow: 0 0 0 2px rgba(96,165,250,0.13);
        }

        /* Download button */
        .stDownloadButton > button {
            border: 1px solid rgba(96,165,250,0.55);
            background: linear-gradient(110deg,#2563eb,#1d4ed8);
            color: white;
            border-radius: 11px;
            font-size: 1rem;
            font-weight: 700;
            padding: 12px 18px;
            transition: all 160ms ease;
        }

        .stDownloadButton > button:hover {
            border-color: #93c5fd;
            background: linear-gradient(110deg,#3b82f6,#2563eb);
            color: white;
            transform: translateY(-1px);
        }

        /* Notices, expanders and report hash */
        [data-testid="stAlert"] {
            border-radius: 13px;
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--bs-border);
            border-radius: 12px;
            overflow: hidden;
        }

        code {
            border-radius: 5px;
            color: #93c5fd !important;
        }

        [data-testid="stCode"] {
            border: 1px solid var(--bs-border);
            border-radius: 12px;
        }

        hr {
            border-color: var(--bs-border);
            margin-top: 2rem;
            margin-bottom: 2rem;
        }

        @media (max-width: 768px) {
            .block-container {
                padding: 1rem 1rem 2rem;
            }

            h2 {
                font-size: 1.6rem !important;
            }

            [data-testid="stMetric"] {
                padding: 16px;
            }

            [data-testid="stMetricValue"] {
                font-size: 1.8rem !important;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                transition: none !important;
                transform: none !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Prototype disclaimer
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

        # Strip evaluation labels before candidates enter the pipeline.
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

    # Metrics describe the complete selected-brand result set.
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

    st.divider()

    if clustering_available:
        render_threat_rings(
            report.get("clusters", []),
            candidates_by_id,
            safe_text,
        )
    else:
        st.subheader("Threat Rings")
        st.warning("Threat Rings are currently unavailable.")

    st.divider()

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
