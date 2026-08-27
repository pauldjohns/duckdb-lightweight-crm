# Lightweight CRM — Design Spec

## Overview

A local-first, CLI-driven CRM built on DuckDB and Python, operated primarily through Claude Code. Replaces a manual Coda table with a queryable database, automated integrations (Granola, Gmail, Google Calendar via Claude MCP), and a password-gated Streamlit dashboard for visual reporting.

Two users: the operator (primary — writes data via Claude Code) and teammate (reads, queries, views dashboard).

## Goals

- **Zero infrastructure cost** — no paid backend, database, or hosting
- **CLI-driven workflow** — interact via natural language through Claude Code
- **Automated data capture** — scheduled agents sync meetings, emails, and calendar events for known contacts
- **Analytical reporting** — pipeline health, conversion rates, contact aging, activity tracking
- **Shared dashboard** — a teammate accesses via URL, password-gated

## Non-Goals

- Mobile app or native UI
- Multi-tenant access control beyond a simple password gate
- Real-time collaborative editing
- Marketing automation or email campaigns

---

## Architecture

```
lightweight-crm/
├── src/
│   ├── models.py           # Schema definitions and table creation
│   ├── crud.py             # Create, read, update, delete operations
│   ├── import_csv.py       # Coda CSV importer with field mapping
│   ├── queries.py          # Reporting and analytical queries
│   ├── integrations.py     # Helpers for structuring Granola/Gmail/Calendar data
│   └── export.py           # Export DuckDB views to Parquet for dashboard
├── dashboard/
│   └── app.py              # Streamlit dashboard (password-gated)
├── data/
│   └── exports/            # Parquet files for dashboard (committed to git)
├── db/
│   ├── migrations/         # Schema migration scripts (sequential SQL files)
│   └── .gitkeep            # crm.duckdb is gitignored, lives here locally
├── scripts/
│   └── init_db.py          # Database initialization entry point
├── requirements.txt
├── .gitignore
├── .env.example            # Template for dashboard password
└── CLAUDE.md
```

### Migration Convention

Migration files in `db/migrations/` follow the naming pattern `NNN_description.sql` (e.g., `001_initial_schema.sql`, `002_add_contact_emails.sql`). `init_db.py` runs all migration files in alphabetical order. A `_migrations_applied` table in DuckDB tracks which migrations have been executed, ensuring idempotent runs — each migration is applied at most once.

### Parquet Export Convention

`export.py` exports the following files to `data/exports/`:

- `contacts.parquet` — full contacts table joined with primary email from `contact_emails`
- `deals.parquet` — full deals table
- `interactions.parquet` — full interactions table
- `action_items.parquet` — full action_items table
- `notes.parquet` — full notes table
- `stage_history.parquet` — full stage_history table
- `pipeline_stages.parquet` — full pipeline_stages reference table

These are raw table exports. The Streamlit dashboard handles joins and aggregations at query time using DuckDB's in-process Parquet reader.

### Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Database | DuckDB | Embedded, zero-cost, columnar storage optimized for analytical queries |
| Language | Python 3.11+ | DuckDB's best-supported client, rich data ecosystem |
| Dashboard | Streamlit | Interactive Python dashboards, free hosting on Streamlit Cloud |
| Dashboard data | Parquet exports | Avoids committing binary DB to git; Parquet is compact, columnar, and DuckDB reads it natively |
| Hosting | GitHub + Streamlit Cloud | Free, auto-deploys from repo |
| Integrations | Claude MCP | Direct access to Granola, Gmail, Google Calendar — no custom API code |

### Key Design Decisions

- **DuckDB file is local only (gitignored).** The `.duckdb` file never enters version control. Instead, `export.py` writes Parquet snapshots to `data/exports/`, which are committed and pushed. This avoids binary blob bloat in git history while still giving Streamlit Cloud access to current data. The Streamlit dashboard reads Parquet directly using DuckDB's in-process Parquet reader — no database file needed on the server side.
- **No ORM.** DuckDB's Python API is SQL-native. Raw SQL in `queries.py` keeps things simple and lets Claude Code generate ad-hoc queries easily.
- **One deal per contact.** At the current stage (design partner recruitment), each contact maps to a single deal/pipeline opportunity. The schema supports multiple deals per contact if needed later, but CRUD operations and dashboard views assume 1:1 for now.
- **Stage history as a separate table.** Every deal stage change is logged with a timestamp, enabling time-in-stage and conversion analysis without reconstructing history from snapshots.
- **Integration helpers, not integration engines.** `integrations.py` provides functions to structure data from MCP sources (Granola, Gmail, Calendar) into interaction records. Claude Code orchestrates the actual MCP calls — the Python code just handles data shaping and persistence.
- **`crud.py` owns `updated_at` and `last_contact_date`.** DuckDB has no triggers. All UPDATE operations in `crud.py` explicitly set `updated_at = now()`. When a new interaction is created, `crud.py` also updates `contacts.last_contact_date` to match.

---

## Data Model

### contacts

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| name | VARCHAR | NOT NULL |
| company | VARCHAR | |
| title | VARCHAR | |
| linkedin_url | VARCHAR | |
| last_contact_date | DATE | Maintained by crud.py when interactions are created |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now(), set explicitly on UPDATE |

### contact_emails

Supports multiple email addresses per contact for integration matching.

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| contact_id | INTEGER | FK → contacts.id, NOT NULL |
| email | VARCHAR | NOT NULL, UNIQUE |
| is_primary | BOOLEAN | DEFAULT false — `crud.py` enforces single-primary per contact (sets others to false before setting one to true) |

### deals

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| contact_id | INTEGER | FK → contacts.id, NOT NULL |
| name | VARCHAR | NOT NULL — e.g., "Acme Corp - Opportunity" |
| stage | VARCHAR | NOT NULL, FK → pipeline_stages.name |
| value | DECIMAL(12,2) | |
| expected_close | DATE | |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now(), set explicitly on UPDATE |

### interactions

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| contact_id | INTEGER | FK → contacts.id, NOT NULL |
| deal_id | INTEGER | FK → deals.id, nullable — associates interaction with a specific deal when relevant |
| type | VARCHAR | NOT NULL — meeting, email, call |
| summary | TEXT | |
| next_connect_date | DATE | |
| source | VARCHAR | manual, granola, gmail, calendar |
| occurred_at | TIMESTAMP | DEFAULT now() — when the interaction actually happened (may differ from created_at for synced data) |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now(), set explicitly on UPDATE |

### action_items

Separate table for action items, allowing per-item ownership and tracking. Supports the "what are my open action items?" query directly.

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| interaction_id | INTEGER | FK → interactions.id, NOT NULL |
| description | TEXT | NOT NULL |
| owner | VARCHAR | Free text — typically the operator's name, teammate name, or contact name |
| due_date | DATE | |
| completed | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMP | DEFAULT now() |

### notes

Persistent context about a contact — preferences, background info, relationship details. Distinct from interactions, which are time-bound events.

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| contact_id | INTEGER | FK → contacts.id, NOT NULL |
| content | TEXT | NOT NULL |
| created_at | TIMESTAMP | DEFAULT now() |

Examples: "Prefers async communication", "Decision-maker is CTO", "Met at SaaStr 2025".

### stage_history

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| deal_id | INTEGER | FK → deals.id, NOT NULL |
| from_stage | VARCHAR | NULL for initial stage assignment |
| to_stage | VARCHAR | NOT NULL, FK → pipeline_stages.name |
| changed_at | TIMESTAMP | DEFAULT now() |

### pipeline_stages

Reference table defining all valid stages.

| Column | Type | Constraints |
|--------|------|-------------|
| name | VARCHAR | PK |
| category | VARCHAR | NOT NULL — active, paused, closed |
| sort_order | INTEGER | NOT NULL — determines display and progression order |

**Active (progressive):**

| sort_order | name |
|------------|------|
| 1 | Responded |
| 2 | Call Scheduled |
| 3 | Discovery & Demo |
| 4 | Evaluation |
| 5 | Committed |
| 6 | Referral Partner |

**Paused (sort_order 100+):**

| sort_order | name |
|------------|------|
| 100 | Reconnect later |
| 101 | Interest / Blocked - Red Tape (Org) |
| 102 | Interest / Blocked - internal process |

**Closed (sort_order 200+):**

| sort_order | name |
|------------|------|
| 200 | Went Dark |
| 201 | No Show |
| 202 | Not a Fit - ICP Mismatch |
| 203 | Not a Fit - Tire Kicker |
| 204 | Not a Fit - No Need |

Stage changes on a deal are validated against this table. Moving a deal to a new stage automatically inserts a `stage_history` record.

---

## Claude Code Interaction Model

Claude Code is the primary interface. Natural language commands that Claude translates into Python script invocations.

### CRUD Operations

- "Add a new contact: Jane Doe, Acme Corp, VP Engineering, jane@acme.com"
- "Move Jane Doe's deal to Discovery & Demo"
- "Log a call with Jane — discussed timeline, she needs internal approval. Follow up March 30."
- "Add a note for Jane: prefers async communication, decision-maker is CTO"
- "Delete the duplicate contact for John Smith"

### Queries

- "Show me all deals at Discovery & Demo stage"
- "Who haven't I talked to in 30 days?"
- "What are my open action items?"
- "Show me the pipeline by stage"
- "What's my upcoming schedule with contacts this week?"

### Integration Commands (On-Demand)

- "Pull my Granola notes from today's meeting with Jane and log them"
- "Summarize my recent email thread with Jane and add it as an interaction"
- "What meetings do I have this week with CRM contacts?"

Claude Code uses MCP tools to fetch data from Granola/Gmail/Calendar, then calls the Python `integrations.py` helpers to structure and persist the data.

---

## Integrations

### Automatic (Scheduled via Claude Code Triggers)

Scheduled using Claude Code's remote trigger/cron feature (`/schedule`). Each sync runs as a Claude Code session that:

1. Opens the DuckDB database
2. Calls MCP tools to fetch recent data
3. Matches against known contacts
4. Writes new interaction records
5. Runs `export.py` to update Parquet files
6. Commits and pushes

**Granola sync (daily):**
- Query recent meetings via `query_granola_meetings`
- Match attendees against known contacts (by email via `contact_emails`, then by name)
- For matches, create an interaction record (type: meeting, source: granola) with the meeting summary

**Gmail sync (daily):**
- Search recent messages via `gmail_search_messages`
- Match sender/recipient against `contact_emails.email`
- For matches, create an interaction record (type: email, source: gmail) with a thread summary

**Calendar sync (daily):**
- List upcoming events via `gcal_list_events`
- Match attendees against known contacts
- For matches, update `next_connect_date` on the most recent interaction or create a placeholder interaction

**Matching logic:** Match on email address first (exact match against `contact_emails.email`). Fall back to name matching (case-insensitive against `contacts.name`) only for Granola meetings, where email may not be available. Name-only matches are logged for manual confirmation — they create interactions with a `[UNCONFIRMED MATCH]` prefix in the summary.

### On-Demand (User-Initiated)

User asks Claude Code to pull specific data. Claude uses MCP tools directly, then passes results through `integrations.py` to persist. This is for richer, targeted actions where the user wants full meeting transcripts, detailed email summaries, or manual overrides.

---

## Dashboard

### Access

- Hosted on Streamlit Cloud (free tier), deployed from the GitHub repo
- Password-gated: `st.text_input` password check before rendering any page content
- Password stored in Streamlit Cloud secrets (not in repo)
- Dashboard reads from Parquet files in `data/exports/`, not directly from DuckDB

### Views

**1. Pipeline Snapshot**
- Horizontal bar chart or funnel showing count of deals at each active stage
- Summary cards for total active, paused, and closed deals
- Table of deals at each stage with contact name, company, and last contact date

**2. Conversion Rates**
- Stage-to-stage conversion percentages for the active pipeline
- Calculated from `stage_history`: counts only direct sequential transitions (where `from_stage` sort_order = N and `to_stage` sort_order = N+1). Deals that skip stages are counted as conversions only for the stages they actually transitioned through.
- Filterable by time period

**3. Time-in-Stage**
- Average days spent at each active stage
- Calculated from `stage_history` timestamps (difference between entering and leaving a stage)
- Highlights outliers — deals stuck longer than 1.5x the average for that stage

**4. Activity Tracking**
- Interactions per week/month, broken down by type (meeting, email, call)
- Contacts going cold: those with no interaction in the last 14/30 days
- Trend line over time

**5. Contact Aging**
- Table of contacts sorted by days since last interaction
- Color-coded: green (<14 days), yellow (14-30 days), red (>30 days)
- Filterable by deal stage

**6. Upcoming Engagements**
- List view of scheduled meetings and follow-ups for the next 14 days
- Sourced from `interactions.next_connect_date` and Google Calendar sync
- Shows contact name, company, date, and context (last interaction summary)

---

## Data Update Flow

1. Data changes via Claude Code → Python script writes to local DuckDB file (`db/crm.duckdb`)
2. `export.py` runs → exports dashboard views as Parquet files to `data/exports/`
3. Commit and push Parquet files to GitHub
4. Streamlit Cloud auto-redeploys (~1-2 minutes)
5. Dashboard reads fresh Parquet data on next page load

Steps 2-3 can be automated as part of the Claude Code workflow (Claude runs export + commit after data changes) or done manually.

---

## CSV Import

One-time import from Coda export:

1. User provides CSV file
2. `import_csv.py` reads the CSV and displays a column mapping preview
3. Maps Coda columns to CRM schema fields (contacts, deals, contact_emails, interactions as applicable)
4. Runs as a single transaction — all rows succeed or none are committed
5. Creates initial `stage_history` entries for any deals with a current stage
6. Prints a summary: records imported per table, any skipped rows with reasons

The importer handles:
- Duplicate detection (by name + primary email combination)
- Date format normalization
- Empty/null field handling
- Stage validation against the `pipeline_stages` reference table

---

## Error Handling

**CSV import:** Transactional — if any row fails validation, the entire import rolls back. Validation errors (invalid stage, malformed date, missing required fields) are collected and reported at the end with row numbers and reasons.

**MCP integration failures:** If Granola, Gmail, or Calendar MCP tools are unavailable or return errors, the sync logs the failure and continues with available sources. Claude Code surfaces the error to the user. No partial data is written for a failed sync — each contact's interaction is committed only if the full fetch+parse succeeds.

**Stage validation:** Attempting to set a deal's stage to a value not in `pipeline_stages` raises a descriptive error naming the invalid stage and listing valid options.

**DuckDB corruption:** If the local DuckDB file becomes corrupted, it can be rebuilt from the Parquet exports in `data/exports/` plus the migration scripts in `db/migrations/`. This is a manual recovery process, not automated.

---

## Security Considerations

- **Dashboard password** stored in Streamlit Cloud secrets, never in the repo
- **`.env.example`** documents required secrets without containing values
- **`.gitignore`** excludes `db/crm.duckdb`, `db/crm.duckdb.wal`, `.env`, `__pycache__`. The `data/exports/*.parquet` files are intentionally tracked.
- **No PII in commit messages** — Claude Code should reference contacts by ID or first name only in commit messages
- **Streamlit Cloud free tier is publicly accessible** — the password gate is the only access control. Acceptable for two-teammate use; not suitable if the data becomes sensitive enough to require proper auth

---

## Future Considerations (Not In Scope)

These are explicitly deferred. Documenting them to avoid scope creep:

- Migration to Supabase/Postgres if concurrent writes become necessary
- Role-based access control
- Email/Slack notifications for pipeline changes
- Custom dashboard themes
- API endpoint for external integrations
- Mobile-friendly dashboard view
