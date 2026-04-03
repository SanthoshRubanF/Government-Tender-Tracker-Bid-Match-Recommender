# Government Tender Tracker & Bid-Match Recommender

Government Tender Tracker is a Streamlit application that pulls the public "Latest Tenders" feed from the CPPP eProcurement portal, stores the results in SQLite, and ranks tenders against an uploaded company profile.

The codebase is organized into focused modules for authentication, configuration, scraping, database access, synchronization, profile parsing, relevance scoring, and the Streamlit UI.

## Features

- Secure login using a username plus PBKDF2 password hashing
- Streamlit dashboard with tender search, filtering, CSV export, and manual sync
- Automatic sync when cached data becomes older than the configured interval
- SQLite persistence for tender records and sync history
- Idempotent tender upserts using stable fingerprints
- Request retries, timeout handling, and graceful fallback to cached data
- Detail-page enrichment for department, location, EMD, estimated value, and description
- Company profile uploads in CSV, TXT, and Markdown formats
- Keyword-overlap ranking using cosine similarity
- One-off sync script for Task Scheduler or cron-style automation
- Unit tests for auth, database behavior, matcher logic, profile parsing, and scraper parsing

## Project Structure

```text
.
|-- app.py
|-- requirements.txt
|-- scripts/
|   |-- generate_password_hash.py
|   `-- sync_tenders.py
|-- tender_tracker/
|   |-- auth.py
|   |-- config.py
|   |-- db.py
|   |-- matcher.py
|   |-- profile_parser.py
|   |-- scraper.py
|   |-- services.py
|   `-- ui.py
`-- tests/
    |-- test_auth.py
    |-- test_db.py
    |-- test_matcher.py
    |-- test_profile_parser.py
    `-- test_scraper.py
```

## How It Works

1. The app loads settings from environment variables or `.streamlit/secrets.toml`.
2. Users sign in with the configured username and hashed password.
3. The app ensures the SQLite database is ready before rendering the dashboard.
4. If the latest sync is stale, it automatically refreshes tenders from CPPP.
5. Tender rows are stored locally, enriched from detail pages when possible, and displayed in the dashboard.
6. When a company profile is uploaded, the matcher scores each tender based on token overlap and cosine similarity.

## Requirements

- Python 3.10 or newer
- Access to the public CPPP latest tenders page

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Generate a password hash:

```bash
python scripts/generate_password_hash.py
```

4. Create `.streamlit/secrets.toml` from `.streamlit/secrets.toml.example` and paste in the generated values.
5. Run the app:

```bash
streamlit run app.py
```

## Configuration

The app reads configuration from environment variables first and falls back to Streamlit secrets when available.

Authentication settings:

- `TENDER_TRACKER_USERNAME`
- `TENDER_TRACKER_PASSWORD_HASH`
- `TENDER_TRACKER_PASSWORD_SALT`
- `TENDER_TRACKER_PASSWORD_ITERATIONS`

Application settings:

- `TENDER_TRACKER_DB_PATH`
- `TENDER_TRACKER_SOURCE_URL`
- `TENDER_TRACKER_SOURCE_NAME`
- `TENDER_TRACKER_REQUEST_TIMEOUT`
- `TENDER_TRACKER_SYNC_INTERVAL_MINUTES`
- `TENDER_TRACKER_AUTO_REFRESH_SECONDS`
- `TENDER_TRACKER_MAX_TENDERS`

Default behavior:

- Database file: `tenders.db`
- Source name: `CPPP`
- Request timeout: `20` seconds
- Sync interval: `30` minutes
- Auto-refresh interval: `300` seconds
- Maximum scraped tenders per sync: `25`
- PBKDF2 iterations: `390000`

## Dashboard Usage

After signing in, the dashboard provides:

- Automatic sync when the cache is stale
- A sidebar action to run a manual sync immediately
- Tender metrics such as stored tender count and latest sync status
- Search across title, description, reference number, department, and location
- Profile-based ranking with a minimum score filter
- CSV export of the currently visible results

## Company Profile Uploads

Supported formats:

- `.csv`
- `.txt`
- `.md`

CSV parsing behavior:

- Preferred columns include `services`, `service`, `capabilities`, `capability`, `keywords`, `keyword`, `expertise`, and `description`
- If preferred columns are not present, the parser falls back to any text-like columns
- Empty or non-textual uploads are rejected with validation errors

Text uploads:

- TXT and Markdown files are decoded as text and normalized before matching

## Tender Synchronization

You can run a one-time sync outside Streamlit with:

```bash
python scripts/sync_tenders.py --force
```

Without `--force`, the sync script respects the configured freshness window and may skip a run if the last sync is still recent.

Each sync stores:

- overall success or failure
- fetched row count
- new tender count
- updated tender count
- a human-readable status message

If the source site cannot be reached, the app keeps serving cached tender data from SQLite.

## Testing

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

The current tests cover:

- password hashing and verification
- SQLite initialization and tender upserts
- backfilling export fields from raw payloads
- profile parsing rules
- keyword-based tender ranking
- scraper row parsing and detail-page enrichment

## Notes

- The scraper targets the public CPPP "Latest Tenders" section available on the eProcurement portal landing page.
- Some deeper tender flows on the portal may be CAPTCHA-protected or less automation-friendly, so this project intentionally focuses on the publicly accessible latest-tenders surface.
- The database layer includes recovery logic that can back up a damaged SQLite file and recreate a fresh database automatically.
