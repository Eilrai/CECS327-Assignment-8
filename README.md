# CECS 327 Assignment 8
**Team Members:** Thien Nguyen and Matthew Saldivar  
Distributed IoT smart-house system using a TCP client/server and NeonDB sensor data from DataNiz.

## Files

- `client.py` - TCP client with a menu for the three supported queries
- `server.py` - TCP server that connects to the databases, retrieves sensor data, processes queries, and returns results
- `.env.example` - template for required environment variables
- `requirements.txt` - Python dependencies

## Setup

1. Clone the repository.

```bash
git clone <repo-url>
cd CECS327-Assignment-8
```

2. Create and activate a virtual environment.

```bash
python -m venv .venv
.venv\Scripts\activate
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies.

```bash
pip install -r requirements.txt
```

4. Create a `.env` file using `.env.example` as a template.

```text
CHRIS_DATABASE_URL=your_house_a_neondb_connection_string
PARTNER_DATABASE_URL=your_house_b_neondb_connection_string
LOCAL_HOUSE=House A
SHARING_START_UTC=2026-04-30T00:00:00+00:00
```

Do not commit the real `.env` file to GitHub.

## Running the System

1. Start the server first.

```bash
python server.py
```

When prompted, enter the IP address and port to bind to. For local testing, use:

```text
127.0.0.1
5000
```

2. Start the client in another terminal.

```bash
python client.py
```

When prompted, enter the same server IP and port.

```text
127.0.0.1
5000
```

3. Choose one of the supported menu options.

```text
1. Get average moisture readings for kitchen fridges
2. Get average water consumption for smart dishwashers
3. Compare electricity usage between houses
4. Quit
```

## Supported Queries

The client only sends these assignment queries to the server:

1. Average moisture inside kitchen fridges for the past hour, week, and month
2. Average water consumption per cycle across smart dishwashers for the past hour, week, and month
3. Which house consumed more electricity in the past 24 hours, and by how much

Any unsupported input is rejected by the client.

## Notes

- The server uses `DEVICE_METADATA` in `server.py` to match board names to houses, device types, and owners.
- `LOCAL_HOUSE` decides which database is treated as the local database.
- If a query includes time before `SHARING_START_UTC`, the server retrieves missing historical peer data from the partner database.
- Electricity is estimated with: `kWh = (average amps * 120 / 1000) * hours`.
- Output times are formatted in PST.
