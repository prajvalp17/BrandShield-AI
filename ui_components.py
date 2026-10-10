import streamlit as st


STATUS_ICON = {
    "FLAGGED": "🚩",
    "NOT_FLAGGED": "🟡",
    "CLEARED": "✅",
}


def render_metric_row(total: int, flagged: int, review: int, cleared: int) -> None:
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
            st.metric("Risk score", f"{float(result.get('risk_score', 0.0)):.2f}")
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
