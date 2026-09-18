# QAD campaign dashboard: Python update

This version ports the team changes in `38624c9c-bc02-48b9-ae4e-73ff1e7655dd.jsx`. Application layout, callbacks, BigQuery queries and calculations are authored in Python using Dash. Dash supplies its browser runtime internally.

## Today’s local live-data demo

Start with LOCAL-LIVE.md and run_live_local.py. Deployment remains with your other team. The local launcher uses HTTPS, validates BigQuery access and prompts for a local viewer password without saving it.

## Update an existing installation

Stop the local server with Control+C. Extract the ZIP and replace these files in your existing project:

- app.py
- campaigns.py (new; required)
- model.py
- views.py
- bigquery.py
- demo.py
- config.py
- assets/original.css
- tests/ and this README for documentation and verification

Keep your .venv, credentials, environment variables and existing Vercel deployment configuration. Do not replace a team-maintained pyproject.toml with the earlier minimal example. This update adds no new dependencies. Start with `python app.py` in your activated virtual environment, then refresh the browser. If port 8050 is already occupied, stop your earlier dashboard process or use `python -c "from app import app; app.run(host='127.0.0.1', port=8051, debug=False)"` and open port 8051 instead.

For a fresh local installation (Python 3.9+; Python 3.12 recommended):

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8050. Default mode uses fictional records, session campaigns, titles and a fictional ETM owner. The browser tab title identifies sample data. Do not present those records as production data.

## Changes ported from the supplied artifact

1. Nine base campaigns, including the new EMEA QR Code Scan campaign `701TR000017vR5OYAU`, with the artifact's labels and order.
2. NAMER Theater and Breakout child campaigns discovered by ParentId and names containing TH Session or BR Session. Labels remove the same prefixes as the JSX. No invented production session IDs.
3. Eleven engagement widgets: seven NAMER and four EMEA. Theater and Breakout each occupy one widget regardless of session count. Their cells and detail cards show engaged sessions / discovered sessions, including 0/0 when no sessions exist.
4. Person and contact engagement totals count engaged widgets out of 11. Multiple engaged sessions in one group count once toward this total. Account headline totals still count engaged membership rows, matching the artifact. Account coverage counts distinct contacts engaged per widget.
5. Job titles in the person table, person detail, account contact list and contact detail.
6. Source-neutral record labels on person, contact and account names. Demo records are fictional.
7. ETM Owners column in Account Engagement and ETM OWNERS section in account detail. Only Licensed EU or Remote EU accounts qualify. Active territory models and active user assignments are used. Supply Chain matches Supply* types with AE; ERP matches Named*, ERP* or Channel* types with AE or Channel Manager; Redzone matches Redzone* types with AE. Owner names are deduplicated per business unit. No matches show a dash.
8. Campaign Performance no longer displays or queries hierarchy member totals. Sourced and influenced pipeline cards retain their layout, filters and ACV calculations. Discovered sessions are included in attribution. Same-event primary-sourced opportunities are excluded from influenced totals; influenced opportunities are deduplicated within each event.

## Artifact page structure

The dashboard contains only the three artifact tabs: Campaign Performance, Person Engagement and Account Engagement. The additional category heatmap, its aggregation functions and its styling have been removed. Person Engagement ends with its records and pagination, as in the supplied JSX.

## BigQuery source contract

Create these read-only BigQuery tables in the configured dataset. Application Default Credentials must have `bigquery.jobs.create` and `bigquery.tables.getData`.

The default table names are `campaigns`, `opportunities`, `influence`, `members`, `accounts`, `territories` and `users`; override them with the `BQ_*_TABLE` settings. Required columns are the normalized fields referenced in `bigquery.py`: campaign `id`, `name`, `parent_id`; opportunity `id`, `campaign_id`, `acv`, `is_won`, `sa_hit`; influence `campaign_id`, `opportunity_id`, `primary_campaign_id`, `acv`, `is_won`, `sa_hit`; member identity, title, account, campaign, status, response and date columns; and account, territory and user columns used by the ETM rules.

Confirm the campaign IDs, source mappings, currency policy and intended audience. Credentials must be delivered via your approved secret-management process, not embedded in the source.

## Live configuration

```text
DATA_MODE=live
BQ_PROJECT=company-analytics
BQ_DATASET=marketing_dashboard
BQ_LOCATION=US
BQ_CAMPAIGNS_TABLE=campaigns
APP_USERS_FILE=/run/secrets/dashboard-users.json
```

Use a pre-approved GCP service account or `gcloud auth application-default login` for local development. Source tables must expose ACV in the dashboard currency. Missing ACV contributes zero, as in the artifact.

Use `python hash_password.py` to generate each approved viewer's username/password-hash entry. Combine entries in a protected JSON file for APP_USERS_FILE. Live mode requires HTTPS and approved viewer authentication. All viewers see the configured BigQuery dataset. The app performs read-only queries and does not update BigQuery. APP_USERS_JSON may supply the same approved username/hash mapping through environment settings instead of a file; the local launcher configures this automatically.

A conventional Linux host can run `gunicorn --bind 127.0.0.1:8050 --workers 2 --threads 4 --timeout 65 app:server` behind an HTTPS proxy. Only trusted proxies may reach Gunicorn; preserve Host and securely configure forwarded HTTPS handling. Vercel deployment requires the existing Flask entrypoint setup and a deployment-compatible way to provision viewer credentials; this package does not implement or verify that live-host integration.

## Implementation and verification limits

The Python adapter uses direct BigQuery reads rather than the artifact's Claude/MCP query transport. It retrieves complete query results, validates source values, applies request deadlines and caches complete snapshots for 60 seconds per process. Config is scoped to each render snapshot; discovered sessions do not mutate global configuration across requests. Session discovery runs when the snapshot refreshes, whereas the JSX discovers once per browser app load. A failed ETM query can therefore block the complete snapshot. Queries are not an atomic database snapshot.

The collection deadline remains 50 seconds and each query is capped at 20,000 records. Territory IN clauses are batched in groups of 100. Large datasets may require a paged or background collection design after load testing. No live-data failure falls back to demo data or partial results.

`python -m unittest discover -s tests -v` verifies discovery, grouping, ETM rules, adapter query shape, links/titles and snapshot-context isolation checks. Live BigQuery reconciliation, permissions, target-browser pixel comparison and Vercel deployment have not been verified. The original table narrow-screen limitations are retained. This is a source update, not a claim that a production deployment has been approved.
