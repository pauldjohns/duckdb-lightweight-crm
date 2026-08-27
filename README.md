# duckdb-lightweight-crm

A CRM that is a single DuckDB file on your laptop, driven from the command line or from an AI coding
agent, with a read-only Streamlit dashboard for whoever else needs to see the pipeline. No SaaS seat,
no per-user pricing, no vendor holding your contact data.

Built for a two-person company where one person writes and the other only ever reads.

## Model

Six tables, all in `db/migrations/`:

| Table | What it holds |
|---|---|
| `contacts` | people, with company, role, and a free-text owner |
| `deals` | opportunities, each on a pipeline stage |
| `stage_history` | every stage transition, so conversion and time-in-stage are queryable |
| `interactions` | meetings, emails and calls, each optionally tied to a deal |
| `action_items` | follow-ups with a due date and a done flag |
| `notes` | anything that isn’t an interaction |

`src/crud.py` is the whole write surface. `src/queries.py` holds the reporting reads – pipeline by
stage, stale contacts, conversion rates, activity over a window. `src/integrations.py` shapes
meeting-notes and mail-thread payloads into interactions, so an agent with access to those tools can
log a call without inventing a schema.

## Why DuckDB rather than SQLite or Postgres

The workload is analytical, not transactional: a few writes a day, and reads that group and window
over the whole history. DuckDB does those in-process with no server, reads and writes Parquet
natively, and keeps the entire database in one file you can copy, back up, or hand to someone.

That Parquet support is what makes the dashboard cheap. `src/export.py` writes each table to
`data/exports/`; the Streamlit app reads only those files. The dashboard never touches the database
and cannot write to it, so a public-tier host is safe to point at the exports.

## Run it

```bash
pip install -r requirements.txt
python scripts/init_db.py
pytest -q
```

`scripts/init_db.py` applies the migrations in order and is safe to re-run. From there, work through
`src/crud.py` – from Python, from a REPL, or by pointing Claude Code at the repo and asking it to log
a meeting.

Dashboard:

```bash
streamlit run dashboard/streamlit_app.py
```

It is password-gated through `st.secrets["dashboard_password"]`. That is a gate, not security: it
suits a private pipeline view for a colleague, not regulated data.

## Importing what you already have

`src/import_csv.py` maps a flat CSV export (the shape a Coda or Airtable table dumps) onto contacts,
companies and deals, matching on company name and skipping rows it has already seen.
`examples/companies.example.csv` shows the column contract with synthetic rows.

## What is deliberately missing

The database, the Parquet exports and the CSV imports are gitignored. The repo this was extracted
from committed them – a real pipeline of named people at named companies – which is exactly the
mistake this repo is set up not to repeat. `db/crm.duckdb` and `data/` are yours and stay local.

If you do want the exports in version control so a hosted dashboard can read them, understand what
you are publishing: contact names, employers, deal values, and meeting summaries. A private repo is
the floor, and a private repo is not a data-protection strategy.

## Layout

```
src/          crud, queries, export, csv import, integration helpers
tests/        76 tests, no network, no fixtures beyond a temp database
db/migrations three ordered .sql files
scripts/      init_db.py - applies migrations
dashboard/    read-only Streamlit app over the Parquet exports
docs/         the original design spec and implementation plan
examples/     synthetic CSV with the real column contract
```
