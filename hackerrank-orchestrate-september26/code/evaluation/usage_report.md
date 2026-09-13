# Token Usage / Cost Report

## Agent Configuration

| Field | Value |
|-------|-------|
| Agent Type | Rule-based (no LLM) |
| Language | Python 3 (stdlib only) |
| Model Calls | 0 |
| Input Tokens | 0 |
| Output Tokens | 0 |
| Total Tokens | 0 |

## Per-Request Breakdown

| Metric | Value |
|--------|-------|
| Total Requests Processed | 250 |
| Average Model Calls per Request | 0 |
| Average Input Tokens per Request | 0 |
| Average Output Tokens per Request | 0 |
| Average Total Tokens per Request | 0 |

## Cost Estimate

| Item | Cost |
|------|------|
| LLM API Calls | $0.00 |
| Total Estimated Cost | **$0.00** |

## Explanation

This agent uses a fully deterministic, rule-based approach with **zero LLM API calls**. All intelligence is implemented via:

- **Regex pattern matching** — extracting salary amounts, pay dates, rent changes, and contract status from message text
- **Statistical recurrence detection** — counting settled event intervals and selecting the most common interval
- **Deterministic cash-flow simulation** — projecting inflows and outflows day-by-day for 90 days
- **Candidate plan enumeration and ranking** — evaluating 5 plan types against user constraints

No external API calls, no model inference, no token consumption. The agent runs entirely on CPU with Python standard library modules (`csv`, `re`, `datetime`, `collections`, `os`, `sys`).

## Dependencies

| Package | Type |
|---------|------|
| csv | stdlib |
| re | stdlib |
| datetime | stdlib |
| collections | stdlib |
| os | stdlib |
| sys | stdlib |
