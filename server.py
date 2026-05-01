# CECS 327 Assignment 8

import os
import json
import socket
import psycopg2
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

CHRIS_DATABASE_URL = os.getenv("CHRIS_DATABASE_URL")
PARTNER_DATABASE_URL = os.getenv("PARTNER_DATABASE_URL")
LOCAL_HOUSE = os.getenv("LOCAL_HOUSE", "House A")
PARTNER_HOUSE = "House B" if LOCAL_HOUSE == "House A" else "House A"

# Approx UTC time of when sharing occurred
SHARING_START_UTC = os.getenv("SHARING_START_UTC", "2026-04-30T00:00:00+00:00")

# Assumption for electricity calculation:
# Ammeter readings are treated as amps
# Power = volts * amps
# Household voltage estimated to be 120v in US
SENSOR_TABLE = "sensor_data_virtual"
HOUSE_VOLTAGE = 120
PST = timezone(timedelta(hours=-8), "PST")


DEVICE_METADATA = {
    # Chris / House A devices
    "Dishwasher_Board": {
        "house": "House A",
        "device_type": "dishwasher",
        "device_group": "Old Dishwasher",
        "owner": "Chris"
    },
    "Fridgeboard": {
        "house": "House A",
        "device_type": "fridge",
        "device_group": "SmartFridge 1",
        "owner": "Chris"
    },
    "Fridgeboard duplicate 1 876baa87-2d42-4d36-b3eb-c5b5026a6b3b": {
        "house": "House A",
        "device_type": "fridge",
        "device_group": "SmartFridge 2",
        "owner": "Chris"
    },

    # Matthew / House B devices
    "Arduino": {
        "house": "House B",
        "device_type": "fridge",
        "device_group": "Fridge",
        "owner": "Matthew"
    },
    "Arduino1": {
        "house": "House B",
        "device_type": "dishwasher",
        "device_group": "Dishwasher",
        "owner": "Matthew"
    },
    "Arduino2": {
        "house": "House B",
        "device_type": "microwave",
        "device_group": "Microwave",
        "owner": "Matthew"
    }
}


def parse_time(value):
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(timezone.utc)


SHARING_START_TIME = parse_time(SHARING_START_UTC)

# Designate which is the local House depending on whose system the program is being run on
if LOCAL_HOUSE == "House A":
    LOCAL_DATABASE_URL = CHRIS_DATABASE_URL
    PARTNER_DATABASE_URL_ACTIVE = PARTNER_DATABASE_URL
    LOCAL_DATABASE_NAME = "Chris / House A NeonDB"
    PARTNER_DATABASE_NAME = "Partner / House B NeonDB"
else:
    LOCAL_DATABASE_URL = PARTNER_DATABASE_URL
    PARTNER_DATABASE_URL_ACTIVE = CHRIS_DATABASE_URL
    LOCAL_DATABASE_NAME = "Matthew / House B NeonDB"
    PARTNER_DATABASE_NAME = "Partner / House A NeonDB"


DATABASES = {
    "local": {
        "name": LOCAL_DATABASE_NAME,
        "url": LOCAL_DATABASE_URL
    },
    "partner": {
        "name": PARTNER_DATABASE_NAME,
        "url": PARTNER_DATABASE_URL_ACTIVE
    }
}

def get_database(db_key):
    db = DATABASES.get(db_key)

    if db and db["url"]:
        return db

    return None


def load_payload(payload):
    if isinstance(payload, str):
        return json.loads(payload)

    return payload


def get_boards_by_type(device_type):
    return [
        board_name
        for board_name, info in DEVICE_METADATA.items()
        if info["device_type"] == device_type
    ]


def get_all_boards():
    return list(DEVICE_METADATA.keys())


def is_moisture_sensor(sensor_name):
    sensor_name = sensor_name.lower()
    return "moisture" in sensor_name or "humidity" in sensor_name


def is_water_sensor(sensor_name):
    sensor_name = sensor_name.lower()
    return (
        "water" in sensor_name
        or "gallon" in sensor_name
        or "gal" in sensor_name
        or "liter" in sensor_name
        or "litre" in sensor_name
    )


def is_electricity_sensor(sensor_name):
    sensor_name = sensor_name.lower()
    return (
        "electric" in sensor_name
        or "ammeter" in sensor_name
        or "current" in sensor_name
        or "power" in sensor_name
        or "watt" in sensor_name
        or "anmeter" in sensor_name
    )


def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def format_pst(dt):
    return dt.astimezone(PST).strftime("%Y-%m-%d %I:%M %p PST")


def query_database(db_key, start_time, end_time, board_names):
    db = get_database(db_key)

    if not db or not board_names:
        return []

    conn = psycopg2.connect(db["url"])
    cur = conn.cursor()

    cur.execute(f"""
        SELECT time, payload
        FROM {SENSOR_TABLE}
        WHERE time >= %s
          AND time < %s
          AND payload->>'board_name' = ANY(%s)
        ORDER BY time ASC;
    """, (start_time, end_time, board_names))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "time": db_time,
            "payload": payload,
            "stored_in": db["name"],
            "db_key": db_key
        }
        for db_time, payload in rows
    ]


def add_plan(plans, db_key, start_time, end_time, board_name):
    if start_time >= end_time:
        return

    db = get_database(db_key)

    if db is None:
        return

    key = (db_key, start_time, end_time)

    if key not in plans:
        plans[key] = []

    plans[key].append(board_name)


def build_fetch_plan(start_time, end_time, board_names):
    plans = {}
    local_incomplete = False
    missing_partner_db = False

    for board_name in board_names:
        info = DEVICE_METADATA[board_name]

        # Assumes the "local" database based on the .env variable

        if info["house"] == LOCAL_HOUSE:
            add_plan(plans, "local", start_time, end_time, board_name)
            continue

        if start_time < SHARING_START_TIME:
            local_incomplete = True

            pre_end = min(end_time, SHARING_START_TIME)
            post_start = max(start_time, SHARING_START_TIME)

            if get_database("partner"):
                add_plan(plans, "partner", start_time, pre_end, board_name)
            else:
                missing_partner_db = True

            # After sharing begins, House A's local DB should have the replicated House B rows.
            # If the local DB is unavailable, fall back to the House B's original DB.
            if get_database("local"):
                add_plan(plans, "local", post_start, end_time, board_name)
            else:
                add_plan(plans, "partner", post_start, end_time, board_name)
        else:
            # Entire query window is after sharing began, so House A's local DB should
            # already contain the replicated House B rows. Avoids double counting.
            if get_database("local"):
                add_plan(plans, "local", start_time, end_time, board_name)
            else:
                add_plan(plans, "partner", start_time, end_time, board_name)

    return plans, local_incomplete, missing_partner_db


def fetch_rows(start_time, end_time, board_names):
    plans, local_incomplete, missing_partner_db = build_fetch_plan(
        start_time,
        end_time,
        board_names
    )

    rows = []
    sources_used = set()

    for (db_key, seg_start, seg_end), boards in plans.items():
        rows.extend(query_database(db_key, seg_start, seg_end, boards))

        db = get_database(db_key)
        if db:
            sources_used.add(db["name"])

    return rows, {
        "local_incomplete": local_incomplete,
        "missing_partner_db": missing_partner_db,
        "sources_used": sorted(sources_used)
    }


def parse_sensor_readings(rows, target_device_type, sensor_checker):
    readings = []

    for row in rows:
        payload = load_payload(row["payload"])
        board_name = payload.get("board_name")

        if board_name not in DEVICE_METADATA:
            continue

        device_info = DEVICE_METADATA[board_name]

        if device_info["device_type"] != target_device_type:
            continue

        for key, value in payload.items():
            if key in ("board_name", "timestamp"):
                continue

            if not sensor_checker(key) and not sensor_checker(board_name):
                continue

            numeric_value = safe_float(value)

            if numeric_value is None:
                continue

            readings.append({
                "time": row["time"],
                "board_name": board_name,
                "house": device_info["house"],
                "device_group": device_info["device_group"],
                "value": numeric_value,
                "sensor_name": key,
                "stored_in": row["stored_in"]
            })

    return readings


def average(values):
    if not values:
        return None

    return sum(values) / len(values)


def values_since(readings, start_time, value_key="value"):
    return [
        reading[value_key]
        for reading in readings
        if reading["time"] >= start_time
    ]


def format_percent(value):
    if value is None:
        return "No data available"

    return f"{value:.2f}%"


def format_gallons(value):
    if value is None:
        return "No data available"

    return f"{value:.2f} gallons"


def format_kwh(value):
    return f"{value:.4f} kWh"


def add_completeness_lines(lines, start_time, end_time, fetch_info):
    lines.extend([
        "",
        "Completeness check:",
        f"- Query window: {format_pst(start_time)} to {format_pst(end_time)}",
        f"- DataNiz sharing start: {format_pst(SHARING_START_TIME)}"
    ])

    if fetch_info["local_incomplete"]:
        lines.append("- This window includes pre-sharing time, so House B historical data was retrieved from the partner database.")
    else:
        lines.append("- This window is after sharing began, so the local database should contain the replicated peer data.")

    if fetch_info["missing_partner_db"]:
        lines.append("- Warning: PARTNER_DATABASE_URL is missing, so pre-sharing House B data may be incomplete.")

    lines.append("- Sources used:")

    if fetch_info["sources_used"]:
        for source in fetch_info["sources_used"]:
            lines.append(f"  - {source}")
    else:
        lines.append("  - No database sources were available")


def get_average_fridge_moisture_response():
    now = datetime.now(timezone.utc)

    time_windows = {
        "Past hour": now - timedelta(hours=1),
        "Past week": now - timedelta(days=7),
        "Past month": now - timedelta(days=30)
    }

    month_start = time_windows["Past month"]
    fridge_boards = get_boards_by_type("fridge")
    rows, fetch_info = fetch_rows(month_start, now, fridge_boards)
    readings = parse_sensor_readings(rows, "fridge", is_moisture_sensor)

    lines = [
        "Average moisture inside our kitchen fridges:",
        ""
    ]

    for label, start_time in time_windows.items():
        values = values_since(readings, start_time)
        avg = average(values)
        lines.append(f"{label}: {format_percent(avg)} based on {len(values)} reading(s)")

    add_completeness_lines(lines, month_start, now, fetch_info)

    lines.extend([
        "",
        "Metadata used:",
        "- Device type: fridge",
        "- Sensor type: moisture / humidity",
        "- House ownership preserved through DEVICE_METADATA",
        "",
        "Boards included:"
    ])

    for board in fridge_boards:
        lines.append(f"- {board}")

    return "\n".join(lines)


def get_average_water_response():
    now = datetime.now(timezone.utc)

    time_windows = {
        "Past hour": now - timedelta(hours=1),
        "Past week": now - timedelta(days=7),
        "Past month": now - timedelta(days=30)
    }

    month_start = time_windows["Past month"]
    dishwasher_boards = get_boards_by_type("dishwasher")
    rows, fetch_info = fetch_rows(month_start, now, dishwasher_boards)
    readings = parse_sensor_readings(rows, "dishwasher", is_water_sensor)

    lines = [
        "Average water consumption per cycle across our smart dishwashers:",
        ""
    ]

    for label, start_time in time_windows.items():
        values = values_since(readings, start_time)
        avg = average(values)
        lines.append(f"{label}: {format_gallons(avg)} based on {len(values)} reading(s)")

    add_completeness_lines(lines, month_start, now, fetch_info)

    lines.extend([
        "",
        "Metadata used:",
        "- Device type: dishwasher",
        "- Sensor type: water consumption",
        "- House ownership preserved through DEVICE_METADATA",
        "",
        "Boards included:"
    ])

    for board in dishwasher_boards:
        lines.append(f"- {board}")

    return "\n".join(lines)


def get_electricity_readings(start_time, end_time):
    rows, fetch_info = fetch_rows(start_time, end_time, get_all_boards())
    readings = []

    for row in rows:
        payload = load_payload(row["payload"])
        board_name = payload.get("board_name")

        if board_name not in DEVICE_METADATA:
            continue

        device_info = DEVICE_METADATA[board_name]

        for key, value in payload.items():
            if key in ("board_name", "timestamp"):
                continue

            if not is_electricity_sensor(key) and not is_electricity_sensor(board_name):
                continue

            numeric_value = safe_float(value)

            if numeric_value is None:
                continue

            readings.append({
                "time": row["time"],
                "board_name": board_name,
                "house": device_info["house"],
                "device_type": device_info["device_type"],
                "device_group": device_info["device_group"],
                "sensor_name": key,
                "amps": numeric_value,
                "stored_in": row["stored_in"]
            })

    return readings, fetch_info


def estimate_kwh_by_house(readings, start_time, end_time):
    totals = {}

    for reading in readings:
        house = reading["house"]

        if house not in totals:
            totals[house] = {
                "amp_readings": [],
                "kwh": 0.0
            }

        totals[house]["amp_readings"].append(reading["amps"])

    total_hours = (end_time - start_time).total_seconds() / 3600

    for data in totals.values():
        avg_amps = average(data["amp_readings"])

        if avg_amps is not None:
            avg_watts = avg_amps * HOUSE_VOLTAGE
            data["kwh"] = (avg_watts / 1000) * total_hours

    return totals


def get_electricity_comparison_response():
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=24)

    readings, fetch_info = get_electricity_readings(start_time, now)
    totals = estimate_kwh_by_house(readings, start_time, now)

    house_a_kwh = totals.get("House A", {}).get("kwh", 0.0)
    house_b_kwh = totals.get("House B", {}).get("kwh", 0.0)
    difference = abs(house_a_kwh - house_b_kwh)

    if house_a_kwh > house_b_kwh:
        winner = "House A consumed more electricity"
    elif house_b_kwh > house_a_kwh:
        winner = "House B consumed more electricity"
    else:
        winner = "Both houses consumed the same amount of electricity"

    lines = [
        "Electricity usage comparison for the past 24 hours:",
        "",
        f"House A: {format_kwh(house_a_kwh)}",
        f"House B: {format_kwh(house_b_kwh)}",
        "",
        winner,
        f"Difference: {format_kwh(difference)}",
        "",
        "Calculation used:",
        f"- Assumed household voltage: {HOUSE_VOLTAGE}V",
        "- Simulated ammeter readings were treated as amps and converted to estimated kWh.",
        "- Formula: kWh = (average amps * volts / 1000) * hours"
    ]

    add_completeness_lines(lines, start_time, now, fetch_info)

    lines.extend([
        "",
        "Metadata used:",
        "- House ownership came from DEVICE_METADATA",
        "- Electricity readings were grouped by house",
        "- Board names connected each record back to its device and house",
        "",
        "Reading counts:"
    ])

    for house in ["House A", "House B"]:
        count = len(totals.get(house, {}).get("amp_readings", []))
        lines.append(f"- {house}: {count} electricity reading(s)")

    return "\n".join(lines)


MOISTURE_QUERY = "what is the average moisture inside our kitchen fridges in the past hours, week and month?"
WATER_QUERY = "what is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?"
ELECTRICITY_QUERY = "which house consumed more electricity in the past 24 hours, and by how much?"


def normalize_query(query):
    return query.strip().lower()


def process_query(query):
    query = normalize_query(query)

    if query == MOISTURE_QUERY:
        return get_average_fridge_moisture_response()

    if query == WATER_QUERY:
        return get_average_water_response()

    if query == ELECTRICITY_QUERY:
        return get_electricity_comparison_response()

    return "Sorry, this query cannot be processed. Please try one of the supported queries."


def get_port():
    while True:
        try:
            port = int(input("Enter port number to listen on: ").strip())

            if 0 <= port <= 65535:
                return port

            print("Error: Port must be between 0 and 65535.")

        except ValueError:
            print("Error: Please enter a valid integer for the port.")


def start_server():
    host = input("Enter server IP address to bind to: ").strip()
    port = get_port()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server_socket.bind((host, port))
        server_socket.listen(1)

        print(f"\nServer is listening on {host}:{port}")
        print("Waiting for a client to connect...\n")

        conn, addr = server_socket.accept()
        print(f"Connected by {addr}")

        with conn:
            while True:
                data = conn.recv(4096)

                if not data:
                    print("Client disconnected.")
                    break

                query = data.decode()
                print(f"Received from client: {query}")

                try:
                    response = process_query(query)
                except Exception as error:
                    response = f"Server error: {error}"

                conn.sendall(response.encode())
                print("Response sent to client.\n")

    except OSError as error:
        print(f"Socket error: {error}")

    finally:
        server_socket.close()
        print("Server socket closed.")


if __name__ == "__main__":
    start_server()
