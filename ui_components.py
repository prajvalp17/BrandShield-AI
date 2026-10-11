import streamlit as st


STATUS_ICON = {
    "FLAGGED": "🚩",
    "NOT_FLAGGED": "🟡",
    "CLEARED": "✅",
}




def render_metric_row(total: int, flagged: int, review: int, cleared: int) -> None:
    st.subheader("Overview")
    st.caption("Current results for the selected brand")

    a, b, c, d = st.columns(4)

    a.metric("Total entities", total)
    b.metric("Flagged", flagged)
    c.metric("Needs review", review)
    d.metric("Cleared", cleared)


def render_result_card(result: dict, candidate: dict, label, safe_text) -> None:
    status = result.get("status", "NOT AVAILABLE")
    title_label = safe_text(label)
    identifier = safe_text(result.get("identifier"))
    icon = STATUS_ICON.get(status, "ℹ️")

    with st.container(border=True):
        top_left, top_right = st.columns([4, 1])
        with top_left:
            st.markdown(f"**{icon} {title_label}**")
            st.caption(
                f"{safe_text(result.get('platform'))} · "
                f"{safe_text(result.get('target_type'))} · "
                f"`{safe_text(result.get('entity_id'))}`"
            )
            st.write(f"**Identifier:** {identifier}")
        with top_right:
            st.metric("Risk score", f"{float(result.get('risk_score', 0.0)):.3f}")
            st.caption(f"Status: **{status}**")

        if result.get("is_official"):
            st.success(
                "Official asset cleared: "
                + safe_text(result.get("exclusion_reason"))
            )

        if result.get("review_required"):
            st.warning("Manual review recommended by the scoring output.")

        reasons = result.get("reasons") or []
        with st.expander("Why this status? / Evidence", expanded=(status == "FLAGGED")):
            if reasons:
                st.markdown("**Reasons returned by scoring engine**")
                for reason in reasons:
                    st.write(f"• {reason}")
            else:
                st.write("No reasons recorded")

            
            signals = result.get("signals") or {}
            if signals:
                st.markdown("**Signals returned by scoring engine**")
                for name, detail in signals.items():
                    # Contract v0.7: result signals are flat floats.
                    # Temporary compatibility: old mock values are dicts.
                    if isinstance(detail, dict):
                        value = detail.get("value")
                        category = detail.get("category")
                        reason = detail.get("reason")
                    else:
                        value = detail
                        category = None
                        reason = None

                    if value is None:
                        value_display = "Not available"
                    else:
                        try:
                            value_display = f"{float(value):.3f}"
                        except (TypeError, ValueError):
                            value_display = "Not available"

                    st.write(f"- `{name}`: {value_display}")

                    if category or reason:
                        st.caption(
                            " · ".join(
                                str(part)
                                for part in (category, reason)
                                if part
                            )
                        )


            st.markdown("**Candidate details**")
            fields = (
                ["username", "display_name", "bio", "account_age_days"]
                if result.get("target_type") == "social_profile"
                else ["app_name", "package_id", "publisher", "description"]
            )
            for field in fields:
                st.write(f"- **{field}:** {safe_text(candidate.get(field))}")

        with st.expander("Raw result record"):
            st.json(result, expanded=False)


def render_threat_rings(clusters: list[dict], candidates_by_id: dict, safe_text) -> None:
    st.subheader("Threat Rings")
    st.caption(
        "Possible connections based on shared indicators. "
        "A link does not establish common ownership."
    )

    if not clusters:
        st.info("No linked Threat Rings were returned for this brand.")
        return

    for cluster in clusters:
        ring_id = cluster.get("ring_id", "Unknown ring")
        member_ids = cluster.get("linked_candidate_ids") or []
        reasons = cluster.get("link_reasons") or []

        with st.container(border=True):
            st.markdown(f"### 🔗 {safe_text(ring_id)}")
            st.caption(
                f"{len(member_ids)} linked members · Possible connection"
            )

            st.markdown("**Members**")
            for entity_id in member_ids:
                candidate = candidates_by_id.get(str(entity_id), {})
                label = (
                    candidate.get("display_name")
                    or candidate.get("app_name")
                    or candidate.get("username")
                    or entity_id
                )
                st.markdown(
                    f"- **{safe_text(label)}** "
                    f"(`{safe_text(entity_id)}`)"
                )

            st.markdown("**Link reasons**")
            if not reasons:
                st.caption("No link reasons supplied.")
            else:
                for reason in reasons:
                    first = reason.get("candidate_id_1", "Unknown")
                    second = reason.get("candidate_id_2", "Unknown")
                    indicator = reason.get("indicator_type", "indicator")
                    detail = reason.get("reason", "Reason not supplied")

                    st.markdown(
                        f"- `{safe_text(first)}` ↔ `{safe_text(second)}`"
                    )
                    st.caption(
                        f"{safe_text(indicator)}: {safe_text(detail)}"
                    )
