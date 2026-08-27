# dashboard/app.py
import streamlit as st
import duckdb
import pandas as pd
from pathlib import Path

EXPORTS_DIR = Path(__file__).parent.parent / "data" / "exports"


def check_password():
    """Password gate — blocks all content until correct password entered."""
    if st.session_state.get("authenticated"):
        return True
    password = st.text_input("Password", type="password")
    if password and password == st.secrets.get("dashboard_password", ""):
        st.session_state.authenticated = True
        st.rerun()
    elif password:
        st.error("Incorrect password")
    return False


def load_table(name):
    """Load a Parquet file as a DataFrame using DuckDB."""
    path = EXPORTS_DIR / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM '{path}'").df()


# --- Views ---


def pipeline_snapshot():
    st.header("Pipeline Snapshot")
    deals = load_table("deals")
    stages = load_table("pipeline_stages")
    contacts = load_table("contacts")

    if deals.empty or stages.empty:
        st.info("No deal data available yet.")
        return

    active_stages = stages[stages["category"] == "active"].sort_values("sort_order")
    paused_stages = stages[stages["category"] == "paused"]
    closed_stages = stages[stages["category"] == "closed"]

    # Summary cards
    col1, col2, col3 = st.columns(3)
    col1.metric("Active", len(deals[deals["stage"].isin(active_stages["name"])]))
    col2.metric("Paused", len(deals[deals["stage"].isin(paused_stages["name"])]))
    col3.metric("Closed", len(deals[deals["stage"].isin(closed_stages["name"])]))

    # Bar chart of deals per active stage
    stage_order = active_stages["name"].tolist()
    active_deals = deals[deals["stage"].isin(stage_order)]
    if not active_deals.empty:
        counts = (
            active_deals.groupby("stage").size().reindex(stage_order, fill_value=0)
        )
        st.bar_chart(counts)

    # Detail table
    if not contacts.empty and not deals.empty:
        merged = deals.merge(
            contacts[["id", "name", "company", "last_contact_date"]],
            left_on="contact_id", right_on="id", suffixes=("_deal", "_contact"),
        )
        st.dataframe(
            merged[["name_contact", "company", "stage", "last_contact_date"]]
            .rename(columns={"name_contact": "Contact", "last_contact_date": "Last Contact"})
            .sort_values("stage"),
            use_container_width=True,
        )


def conversion_rates():
    st.header("Conversion Rates")
    history = load_table("stage_history")
    stages = load_table("pipeline_stages")

    if history.empty:
        st.info("No stage transition data yet.")
        return

    active = stages[stages["category"] == "active"].sort_values("sort_order")

    # Compute sequential transitions
    merged = history.merge(
        active[["name", "sort_order"]], left_on="from_stage", right_on="name",
        how="inner",
    ).rename(columns={"sort_order": "from_order"})
    merged = merged.merge(
        active[["name", "sort_order"]], left_on="to_stage", right_on="name",
        how="inner", suffixes=("", "_to"),
    ).rename(columns={"sort_order": "to_order"})

    sequential = merged[merged["to_order"] == merged["from_order"] + 1]

    if sequential.empty:
        st.info("No sequential stage transitions recorded yet.")
        return

    entries = history.groupby("to_stage")["deal_id"].nunique().rename("entries")
    trans = sequential.groupby(["from_stage", "to_stage"]).size().reset_index(name="transitions")
    trans = trans.merge(entries, left_on="from_stage", right_index=True, how="left")
    trans["conversion_pct"] = (trans["transitions"] / trans["entries"] * 100).round(1)

    st.dataframe(
        trans[["from_stage", "to_stage", "transitions", "entries", "conversion_pct"]]
        .rename(columns={
            "from_stage": "From", "to_stage": "To",
            "transitions": "Transitions", "entries": "Entered From",
            "conversion_pct": "Conversion %",
        }),
        use_container_width=True,
    )


def time_in_stage_view():
    st.header("Time in Stage")
    history = load_table("stage_history")
    stages = load_table("pipeline_stages")

    if history.empty:
        st.info("No stage transition data yet.")
        return

    active_names = stages[stages["category"] == "active"]["name"].tolist()

    # Calculate durations using DuckDB on the Parquet file directly
    path = EXPORTS_DIR / "stage_history.parquet"
    result = duckdb.query(f"""
        WITH durations AS (
            SELECT to_stage AS stage, changed_at AS entered_at,
                   LEAD(changed_at) OVER (PARTITION BY deal_id ORDER BY changed_at) AS exited_at
            FROM '{path}'
        )
        SELECT stage,
               ROUND(AVG(DATEDIFF('second', entered_at,
                   COALESCE(exited_at, CURRENT_TIMESTAMP)) / 86400.0), 1) AS avg_days,
               COUNT(*) AS deals
        FROM durations
        WHERE stage IN ({','.join(f"'{s}'" for s in active_names)})
        GROUP BY stage
        ORDER BY stage
    """).df()

    if not result.empty:
        st.bar_chart(result.set_index("stage")["avg_days"])
        st.dataframe(result, use_container_width=True)


def activity_tracking():
    st.header("Activity Tracking")
    interactions = load_table("interactions")
    contacts = load_table("contacts")

    if interactions.empty:
        st.info("No interaction data yet.")
        return

    # Interactions by type
    by_type = interactions.groupby("type").size().reset_index(name="count")
    st.subheader("Interactions by Type")
    st.bar_chart(by_type.set_index("type")["count"])

    # Contacts going cold
    st.subheader("Contacts Going Cold")
    if not contacts.empty:
        contacts["last_contact_date"] = pd.to_datetime(contacts["last_contact_date"])
        contacts["days_silent"] = (
            pd.Timestamp.now() - contacts["last_contact_date"]
        ).dt.days

        cold_14 = contacts[
            (contacts["days_silent"] >= 14) | contacts["last_contact_date"].isna()
        ].sort_values("days_silent", ascending=False, na_position="first")

        if not cold_14.empty:
            st.dataframe(
                cold_14[["name", "company", "last_contact_date", "days_silent"]],
                use_container_width=True,
            )
        else:
            st.success("All contacts have been reached in the last 14 days.")


def contact_aging():
    st.header("Contact Aging")
    contacts = load_table("contacts")
    deals = load_table("deals")

    if contacts.empty:
        st.info("No contact data yet.")
        return

    contacts["last_contact_date"] = pd.to_datetime(contacts["last_contact_date"])
    contacts["days_since_contact"] = (
        pd.Timestamp.now() - contacts["last_contact_date"]
    ).dt.days

    def status_color(days):
        if pd.isna(days):
            return "red"
        if days < 14:
            return "green"
        if days <= 30:
            return "yellow"
        return "red"

    contacts["status"] = contacts["days_since_contact"].apply(status_color)

    # Stage filter
    if not deals.empty:
        all_stages = ["All"] + sorted(deals["stage"].unique().tolist())
        selected = st.selectbox("Filter by deal stage", all_stages)
        if selected != "All":
            deal_contacts = deals[deals["stage"] == selected]["contact_id"]
            contacts = contacts[contacts["id"].isin(deal_contacts)]

    st.dataframe(
        contacts[["name", "company", "last_contact_date", "days_since_contact", "status"]]
        .sort_values("days_since_contact", ascending=False, na_position="first"),
        use_container_width=True,
    )


def upcoming_engagements():
    st.header("Upcoming Engagements (14 days)")
    interactions = load_table("interactions")
    contacts = load_table("contacts")

    if interactions.empty:
        st.info("No interaction data yet.")
        return

    interactions["next_connect_date"] = pd.to_datetime(interactions["next_connect_date"])
    now = pd.Timestamp.now()
    upcoming = interactions[
        (interactions["next_connect_date"] >= now)
        & (interactions["next_connect_date"] <= now + pd.Timedelta(days=14))
    ]

    if upcoming.empty:
        st.info("No upcoming engagements in the next 14 days.")
        return

    if not contacts.empty:
        upcoming = upcoming.merge(
            contacts[["id", "name", "company"]],
            left_on="contact_id", right_on="id", suffixes=("", "_contact"),
        )
        st.dataframe(
            upcoming[["name", "company", "next_connect_date", "type", "summary"]]
            .rename(columns={"name": "Contact", "next_connect_date": "Date"})
            .sort_values("Date"),
            use_container_width=True,
        )


# --- Main ---


def main():
    st.set_page_config(page_title="CRM Dashboard", layout="wide")

    if not check_password():
        st.stop()

    st.title("Lightweight CRM Dashboard")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Pipeline", "Conversions", "Time in Stage",
        "Activity", "Contact Aging", "Upcoming",
    ])

    with tab1:
        pipeline_snapshot()
    with tab2:
        conversion_rates()
    with tab3:
        time_in_stage_view()
    with tab4:
        activity_tracking()
    with tab5:
        contact_aging()
    with tab6:
        upcoming_engagements()


if __name__ == "__main__":
    main()
