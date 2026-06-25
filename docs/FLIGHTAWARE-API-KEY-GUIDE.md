# FlightAware AeroAPI Key Setup

This guide walks you through creating a FlightAware account and obtaining an AeroAPI key for AirportHub's scheduled flight data refresh feature.

## Prerequisites

- A valid email address
- A credit card (required for all tiers, even the free Personal tier)

## Step 1: Create a FlightAware Account

1. Go to [https://www.flightaware.com/account/join](https://www.flightaware.com/account/join)
2. Fill in your name, email, and password
3. Verify your email address via the confirmation link

> If you already have a FlightAware account, skip to Step 2.

## Step 2: Sign Up for AeroAPI

1. Go to the AeroAPI signup page: [https://www.flightaware.com/aeroapi/signup/personal](https://www.flightaware.com/aeroapi/signup/personal)
2. Select the **Personal** tier (recommended for demos — see [Pricing Tiers](#pricing-tiers) below)
3. Accept the Terms of Service
4. Enter your payment information (credit card required even for the free tier)
5. Complete the signup

## Step 3: Get Your API Key

1. After signup, go to the AeroAPI portal: [https://www.flightaware.com/aeroapi/portal](https://www.flightaware.com/aeroapi/portal)
2. Your API key is displayed on the portal dashboard
3. Copy the key — you'll need it during AirportHub deployment

> **Important**: The API key is a long alphanumeric string. It is NOT your FlightAware username or password.

## Step 4: Test Your API Key

Verify the key works by running this curl command (replace `YOUR_API_KEY`):

```bash
curl -s -H "x-apikey: YOUR_API_KEY" \
  "https://aeroapi.flightaware.com/aeroapi/airports/KJFK" | head -c 200
```

A successful response returns JSON with airport data. A `401` error means the key is invalid.

## Step 5: Use the Key in AirportHub Deployment

When running `deploy.py`, you'll be prompted:

```
FlightAware API key (hidden, press Enter to skip): 
```

Paste your API key. It will be stored securely in AWS Secrets Manager as `airporthub/flightaware/api-key`. The key is never passed as a CLI argument or stored in CloudFormation parameters.

---

## Pricing Tiers

AirportHub only needs the **Personal** tier. Here's a comparison:

| | Personal | Standard | Premium |
|---|---|---|---|
| **Monthly minimum** | Free ($5 credit/mo) | $100/mo | $1,000/mo |
| **Rate limit** | 10 result sets/min | 5 result sets/sec | 100 result sets/sec |
| **Use case** | Personal / academic | Business / B2C | B2B commercial |
| **Historical data** | No | Yes | Yes |
| **Alerts** | No | Yes | Yes |
| **Support** | Community forum | Email | Email + phone |

### What AirportHub Uses

AirportHub's scheduled refresh Lambda calls these endpoints once every 24 hours per airport:

| Endpoint | Cost per call |
|---|---|
| `GET /airports/{id}/flights/departures` | $0.005 |
| `GET /airports/{id}/flights/arrivals` | $0.005 |
| `GET /airports/{id}/flights/scheduled_departures` | $0.005 |
| `GET /airports/{id}/flights/scheduled_arrivals` | $0.005 |

With the default 10 seeded airports, that's approximately **$0.20/day** or **~$6/month** — well within the Personal tier's $5 free monthly credit. You may see a small overage charge of ~$1/month.

### Recommendation for Demos

- **Personal tier** is sufficient for AirportHub demos
- No monthly minimum — you only pay per query beyond the $5 free credit
- If you're an ADS-B feeder, you get $10/month free instead of $5

---

## Troubleshooting

### "401 Unauthorized" errors
- Verify your API key is correct (no extra spaces or newlines)
- Ensure you signed up for **AeroAPI v4** (not the legacy FlightXML v2/v3)
- Check your account status at [https://www.flightaware.com/aeroapi/portal](https://www.flightaware.com/aeroapi/portal)

### "429 Too Many Requests"
- Personal tier is limited to 10 result sets per minute
- AirportHub's 24-hour refresh schedule should never hit this limit
- If testing manually, wait 60 seconds between bursts

### No flight data returned
- AeroAPI uses **ICAO airport codes** (e.g., `KJFK`), not IATA codes (`JFK`)
- AirportHub handles this mapping automatically — no action needed
- Small/regional airports may have limited flight data

### Billing questions
- View your current charges at [https://www.flightaware.com/aeroapi/portal](https://www.flightaware.com/aeroapi/portal)
- Contact FlightAware support: [https://support.flightaware.com](https://support.flightaware.com)

---

## Useful Links

| Resource | URL |
|---|---|
| AeroAPI Portal (manage key & billing) | [flightaware.com/aeroapi/portal](https://www.flightaware.com/aeroapi/portal) |
| API Documentation | [flightaware.com/aeroapi/portal/documentation](https://www.flightaware.com/aeroapi/portal/documentation) |
| Pricing Details | [flightaware.com/commercial/aeroapi](https://www.flightaware.com/commercial/aeroapi/) |
| Support / FAQ | [support.flightaware.com](https://support.flightaware.com) |
| Discussion Forum | [discussions.flightaware.com](https://discussions.flightaware.com) |
