# Scheduled Refresh Microservice

EventBridge-triggered Lambda that refreshes live flight data from [FlightAware AeroAPI](https://www.flightaware.com/aeroapi/) into DocumentDB on a 24-hour schedule. Deployed as a self-contained microservice with its own ARC Region Switch child plan for DR failover.

## What It Does

1. **Scheduled Refresh Lambda** — Runs every 24 hours via EventBridge, fetches departures/arrivals for all seeded airports from FlightAware AeroAPI, and upserts them into DocumentDB.
2. **Schedule Toggle Lambda** — Called by the ARC child plan during failover to enable the EventBridge rule in the activating region and disable it in the deactivating region.
3. **ARC Child Plan** (`flightaware-app-switchover.yaml`) — A nested ARC Region Switch plan invoked by the parent plan's post-failover step, managing schedule ownership independently.

## Structure

```
scheduled-refresh-microservice/
├── lambda_function.py              # Scheduled refresh Lambda (entry point)
├── flightaware_client.py           # AeroAPI client — fetch, map, rate-limit
├── global-bundle.pem               # DocumentDB TLS CA bundle
├── requirements.txt                # pymongo, requests
├── flightaware-app-switchover.yaml # CloudFormation: Lambda + EventBridge + ARC child plan
└── schedule_toggle/
    └── lambda_function.py          # Schedule toggle Lambda (enable/disable EventBridge rules)
```

## How It Works

- EventBridge triggers `lambda_function.py` every 24 hours in the active region only.
- The Lambda reads all airports with ICAO codes from DocumentDB, calls FlightAware AeroAPI for each (capped at 15 airports per run), and upserts flights using `fa_flight_id + board_type` as the unique key.
- Stale flights older than 7 days are automatically cleaned up.
- Rate limiting: 7-second pause between airports to stay within AeroAPI's Personal tier (10 result sets/min). Early exit after 3 consecutive airports return 0 flights.

## DR Behavior

During an ARC Region Switch failover:

1. The parent plan invokes the `flightaware-app-switchover` child plan in Step 6 (post-failover cleanup).
2. The child plan calls the Schedule Toggle Lambda, which enables the EventBridge rule in the newly active region and disables it in the old region.
3. This ensures only one region runs the scheduled refresh at any time.
