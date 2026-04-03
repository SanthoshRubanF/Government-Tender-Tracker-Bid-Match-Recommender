from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from tender_tracker.auth import is_auth_configured, verify_password
from tender_tracker.config import AppConfig, load_config
from tender_tracker.db import ensure_database_ready, fetch_tenders_dataframe, get_sync_snapshot
from tender_tracker.matcher import rank_tenders
from tender_tracker.profile_parser import ProfileValidationError, load_profile_text
from tender_tracker.services import SyncResult, is_sync_due, sync_tenders


APP_TITLE = "Government Tender Tracker & Bid-Match Recommender"


def _safe_autorefresh(interval_seconds: int) -> None:
    if interval_seconds <= 0:
        return

    try:
        from streamlit_autorefresh import st_autorefresh

        st_autorefresh(interval=interval_seconds * 1000, key="tender_tracker_refresh")
    except Exception:
        return


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "Never"

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.astimezone().strftime("%d %b %Y %I:%M %p")


def _filter_tenders(dataframe: pd.DataFrame, query: str) -> pd.DataFrame:
    cleaned_query = query.strip()
    if not cleaned_query or dataframe.empty:
        return dataframe

    columns = [
        column
        for column in ("title", "description", "reference_no", "department", "location")
        if column in dataframe.columns
    ]
    if not columns:
        return dataframe

    mask = pd.Series(False, index=dataframe.index)
    for column in columns:
        mask = mask | dataframe[column].fillna("").str.contains(
            cleaned_query,
            case=False,
            regex=False,
        )
    return dataframe[mask]


def _display_sync_feedback(result: SyncResult | None) -> None:
    if not result or not result.message:
        return

    if result.performed and result.success:
        st.success(result.message)
    elif result.performed:
        st.error(result.message)
    elif result.attempted:
        st.info(result.message)


def _render_login(config: AppConfig) -> None:
    if st.session_state.get("logged_in"):
        return

    st.title(APP_TITLE)
    st.caption("Secure sign-in is required before the dashboard is available.")

    if not is_auth_configured(config):
        st.error("Authentication is not configured yet.")
        st.markdown(
            """
            Add credentials in `.streamlit/secrets.toml` or as environment variables:

            - `TENDER_TRACKER_USERNAME`
            - `TENDER_TRACKER_PASSWORD_HASH`
            - `TENDER_TRACKER_PASSWORD_SALT`
            - `TENDER_TRACKER_PASSWORD_ITERATIONS` (optional)

            Use `python scripts/generate_password_hash.py` to create the hash and salt.
            """
        )
        st.stop()

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        valid_username = username == config.auth_username
        valid_password = verify_password(
            password=password,
            expected_hash=config.auth_password_hash,
            salt=config.auth_password_salt,
            iterations=config.auth_iterations,
        )
        if valid_username and valid_password:
            st.session_state["logged_in"] = True
            st.rerun()
        st.error("Invalid credentials.")
        st.stop()

    st.info("Sign in to view tender data, refresh the feed, and upload your company profile.")
    st.stop()


def _prepare_display_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    prepared = dataframe.copy()
    if "match_score" in prepared.columns:
        prepared["match_score"] = (prepared["match_score"] * 100).round(2)
    columns = [
        column
        for column in (
            "title",
            "reference_no",
            "department",
            "closing_date",
            "bid_opening_date",
            "match_score",
            "shared_keywords",
            "source_url",
        )
        if column in prepared.columns
    ]
    return prepared[columns]


def _render_tender_table(dataframe: pd.DataFrame) -> None:
    display = _prepare_display_dataframe(dataframe)
    if display.empty:
        st.info("No tenders matched the current filters.")
        return

    column_config = {}
    if "match_score" in display.columns:
        column_config["match_score"] = st.column_config.NumberColumn(
            "Match Score (%)",
            format="%.2f",
        )
    if "source_url" in display.columns:
        column_config["source_url"] = st.column_config.LinkColumn(
            "Source URL",
            display_text="Open source",
        )

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config=column_config,
    )


def _render_sidebar(config: AppConfig, snapshot) -> SyncResult | None:
    with st.sidebar:
        st.subheader("Session")
        st.write(f"Source: `{config.source_name}`")
        st.write(f"Database: `{config.database_path.name}`")
        if st.button("Logout", width="stretch"):
            st.session_state.clear()
            st.rerun()

        st.divider()
        st.subheader("Data Sync")
        st.write(f"Stored tenders: {snapshot.total_tenders}")
        st.write(f"Last successful sync: {_format_timestamp(snapshot.last_successful_sync_at)}")
        if snapshot.latest_sync_status == "error" and snapshot.latest_sync_message:
            st.warning(snapshot.latest_sync_message)

        if st.button("Sync now", width="stretch"):
            with st.spinner("Refreshing tender feed..."):
                return sync_tenders(config, force=True)

    return None


def _automatic_sync_if_due(config: AppConfig) -> SyncResult | None:
    if not is_sync_due(config):
        return None

    with st.spinner("Refreshing tender feed..."):
        return sync_tenders(config, force=False)


def _render_dashboard(config: AppConfig) -> None:
    auto_result = _automatic_sync_if_due(config)
    snapshot = get_sync_snapshot(config.database_path)
    manual_result = _render_sidebar(config, snapshot)
    result_to_show = manual_result or auto_result
    _display_sync_feedback(result_to_show)

    dataframe = fetch_tenders_dataframe(config.database_path)

    st.title(APP_TITLE)
    st.caption("Track current public tenders and rank them against your company profile.")

    upload_col, filter_col = st.columns([1, 1])
    with upload_col:
        uploaded_file = st.file_uploader(
            "Upload company profile",
            type=["csv", "txt", "md"],
            help="CSV files can use a `services` column, but any text columns will be accepted.",
        )
    with filter_col:
        search_query = st.text_input(
            "Search tenders",
            placeholder="Reference number, title, department",
        )
        minimum_score_percentage = st.slider(
            "Minimum match score",
            min_value=0,
            max_value=100,
            value=5,
            step=5,
        )

    profile_details = None
    ranked_dataframe = dataframe

    if uploaded_file is not None:
        try:
            profile_text, profile_details = load_profile_text(uploaded_file)
            ranked_dataframe = rank_tenders(
                profile_text,
                dataframe,
                minimum_score=minimum_score_percentage / 100,
            )
        except ProfileValidationError as exc:
            st.error(str(exc))
            ranked_dataframe = dataframe.iloc[0:0].copy()
    else:
        ranked_dataframe = dataframe.copy()

    filtered_dataframe = _filter_tenders(ranked_dataframe, search_query)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Stored tenders", snapshot.total_tenders)
    metric_columns[1].metric("Visible tenders", len(filtered_dataframe))
    metric_columns[2].metric("New in latest sync", snapshot.latest_sync_new_count)
    metric_columns[3].metric("Last sync", _format_timestamp(snapshot.last_successful_sync_at))

    if profile_details:
        st.caption(
            "Profile loaded from "
            f"`{profile_details['file_name']}` using columns: "
            f"{', '.join(profile_details['columns_used'])}"
        )
    else:
        st.info("Upload a company profile to rank tenders by relevance.")

    _render_tender_table(filtered_dataframe)

    if not filtered_dataframe.empty:
        st.download_button(
            "Download current results as CSV",
            data=filtered_dataframe.to_csv(index=False).encode("utf-8"),
            file_name="matched_tenders.csv",
            mime="text/csv",
        )

    with st.expander("How matching works"):
        st.write(
            "The matcher compares normalized keywords from your uploaded profile "
            "against tender title, description, department, reference number, and location."
        )
        st.write(
            "Match scores are cosine similarity percentages based on token overlap, "
            "so better tender descriptions will improve ranking quality."
        )


def run_app() -> None:
    st.set_page_config(page_title="Tender Tracker", page_icon="TT", layout="wide")
    config = load_config()
    database_notice = ensure_database_ready(config.database_path)
    _safe_autorefresh(config.auto_refresh_seconds)
    if database_notice:
        st.warning(database_notice)
    _render_login(config)
    _render_dashboard(config)
