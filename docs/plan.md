# Lightweight CRM — Project Plan

> Source of truth for project state across Claude Code sessions. Read this first in every session.

## Current Status

**Phase:** Complete — all 13 tasks implemented
**Tests:** 76 passing
**Last session:** 2026-03-24

## Completed Tasks

| # | Task | Commit | Tests |
|---|------|--------|-------|
| 1 | Project Scaffolding | `<sha>` | — |
| 2 | Migration System | `<sha>` | 3 |
| 3 | Initial Schema | `<sha>` | 2 |
| 4 | Contacts & Emails CRUD | `<sha>` | 14 |
| 5 | Deals CRUD | `<sha>` | 11 |
| 6 | Interactions CRUD | `<sha>` | 8 |
| 7 | Action Items & Notes CRUD | `<sha>` | 10 |
| 8 | Reporting Queries | `<sha>` | 11 |
| 9 | Parquet Export | `<sha>` | 3 |
| 10 | CSV Import | `<sha>` | 6 |
| 11 | Integration Helpers | `<sha>` | 7 |
| 12 | Streamlit Dashboard | `<sha>` | — (manual) |
| 13 | CLAUDE.md | `<sha>` | — |

### Notable Deviation

Task 5 added `db/migrations/002_drop_stage_history_deal_fk.sql` — DuckDB has a FK limitation where updating a parent row (`UPDATE deals SET stage=...`) fails if a child table references the parent's PK, even when the PK isn't changing. The migration recreates `stage_history` without the FK on `deal_id`. Referential integrity is enforced in application code (`delete_deal` explicitly handles cascade).

## Architecture Summary

- **Stack:** DuckDB + Python + Streamlit (password-gated dashboard)
- **Data flow:** Claude Code → Python CRUD → local DuckDB → Parquet export → git push → Streamlit Cloud reads Parquet
- **Integrations:** Granola, Gmail, Google Calendar via Claude MCP
- **Users:** the operator (writes via Claude Code), a teammate (reads via the Streamlit dashboard)

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| DuckDB over Supabase | Zero cost, no external deps, single-writer pattern fits |
| Parquet export for dashboard | Avoids binary DuckDB file in git history |
| Separate action_items table | Per-item ownership and completion tracking |
| Password gate on Streamlit | Free tier is public; simple password sufficient for a two-person team |
| FK dropped on stage_history.deal_id | DuckDB FK limitation blocks parent row updates; app code enforces integrity |

## References

- **Design spec:** `docs/superpowers/specs/2026-03-23-lightweight-crm-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-03-23-lightweight-crm.md`

## Verification Commands

```bash
pytest -v                          # 76 tests, all should pass
python3 scripts/init_db.py         # Initialize local DB
streamlit run dashboard/app.py     # Launch dashboard
```

## Session Log

| Date | Session | What Happened |
|------|---------|---------------|
| 2026-03-23 | Design | Brainstormed architecture, chose DuckDB+Streamlit. Wrote spec, 2 review passes. |
| 2026-03-23 | Planning | 13-task plan with TDD steps. Reviewer approved. |
| 2026-03-24 | Implementation | Executed Tasks 1-11 via subagent-driven development. 76 tests passing. Task 11 uncommitted. Tasks 12-13 remain. |
| 2026-03-24 | Completion | Committed Task 11. Implemented Tasks 12-13 via subagent-driven development with spec + quality reviews. All 13 tasks complete. |
