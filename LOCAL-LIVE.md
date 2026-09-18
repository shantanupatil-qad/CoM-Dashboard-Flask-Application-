# Today: localhost with Salesforce live data

This workflow is for a controlled demonstration on your own laptop. It binds only to `127.0.0.1`, so stakeholders cannot open this URL from their computers. The dashboard keeps its three tabs and does not fall back to sample data in live mode.

## Obtain these before starting

Ask the Salesforce administrator for a read-only Integration User and OAuth Connected App using the client-credentials flow. Confirm the My Domain URL, OAuth client ID, client secret, API version, required object permissions, ACV currency, and intended audience. Do not send client secrets through this chat.

## Run on your Mac

The live launcher requires Python 3.9 or newer; Python 3.12 is recommended:

```sh
python3 -m venv .venv-live
source .venv-live/bin/activate
python -m pip install -r requirements-local.txt
python run_live_local.py
```

The launcher asks for the Salesforce My Domain URL, OAuth client ID, OAuth client secret, API version, and local dashboard username/password. Credentials are kept in the running process and are not written to project files.

The launcher validates Salesforce access and loads the full dataset before starting. If it succeeds, open:

https://127.0.0.1:8051

The default launcher uses a temporary self-signed local HTTPS certificate. A browser certificate warning is expected for your own `127.0.0.1` server. If your managed browser blocks it, ask IT for an approved local certificate:

```sh
python run_live_local.py --cert /path/to/local-cert.pem --key /path/to/local-key.pem
```

Sign in with the local username and password you chose. Open `https://127.0.0.1:8051/readyz` to verify live-source readiness after authentication. `/healthz` checks only that the process is running.

Port occupied? Stop the previous copy, or run `python run_live_local.py --port 8052`. Stop with Control+C.

## Verify before screen-sharing

Compare a NAMER/EMEA sourced and influenced total against the agreed Salesforce report filters. Check a person with multiple Theater sessions, one EMEA QR membership and one EU account's ETM owners. Confirm the expected dates, titles and all 11 engagement widgets.

The snapshot cache lasts 60 seconds per process. The full collection has a 50-second deadline and a 20,000-row cap per query. No live-data failure falls back to demo data or partial results.
