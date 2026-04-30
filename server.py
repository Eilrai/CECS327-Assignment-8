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

SENSOR_TABLE = "sensor_data_virtual"

# Assumption for electricity calculation:
# Ammeter readings are treated as amps
# Power = volts * amps
# Household voltage estimated to be 120v in US
HOUSE_VOLTAGE = 120


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
}}


def get_database_sources():
    sources = []

    if CHRIS_DATABASE_URL:
        sources.append({
            "name": "Chris / House A NeonDB",
            "url": CHRIS_DATABASE_URL
        })

    if PARTNER_DATABASE_URL:
        sources.append({
            "name": "Partner / House B NeonDB",
            "url": PARTNER_DATABASE_URL
        })

    return sources


def load_payload(payload):
    if isinstance(payload, str):
        return json.loads(payload)

    return payload


def get_boards_by_type(device_type):
    boards = []

    for board_name, info in DEVICE_METADATA.items():
        if info["device_type"] == device_type:
            boards.append(board_name)

    return boards


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


def fetch_rows(start_time, end_time, board_names):
    all_rows = []

    for source in get_database_sources():
        conn = psycopg2.connect(source["url"])
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

        for db_time, payload in rows:
            all_rows.append({
                "time": db_time,
                "payload": payload,
                "stored_in": source["name"]
            })

    return all_rows


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
    if len(values) == 0:
        return None

    return sum(values) / len(values)


def values_since(readings, start_time):
    values = []

    for reading in readings:
        if reading["time"] >= start_time:
            values.append(reading["value"])

    return values


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


def get_average_fridge_moisture_response():
    now = datetime.now(timezone.utc)

    time_windows = {
        "Past hour": now - timedelta(hours=1),
        "Past week": now - timedelta(days=7),
        "Past month": now - timedelta(days=30)
    }

    month_start = time_windows["Past month"]
    fridge_boards = get_boards_by_type("fridge")

    rows = fetch_rows(month_start, now, fridge_boards)
    readings = parse_sensor_readings(rows, "fridge", is_moisture_sensor)

    lines = [
        "Average moisture inside our kitchen fridges:",
        ""
    ]

    for label, start_time in time_windows.items():
        values = values_since(readings, start_time)
        avg = average(values)
        lines.append(f"{label}: {format_percent(avg)} based on {len(values)} reading(s)")

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

    rows = fetch_rows(month_start, now, dishwasher_boards)
    readings = parse_sensor_readings(rows, "dishwasher", is_water_sensor)

    lines = [
        "Average water consumption per cycle across our smart dishwashers:",
        ""
    ]

    for label, start_time in time_windows.items():
        values = values_since(readings, start_time)
        avg = average(values)
        lines.append(f"{label}: {format_gallons(avg)} based on {len(values)} reading(s)")

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
    all_boards = get_all_boards()
    rows = fetch_rows(start_time, end_time, all_boards)

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

    return readings


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

    for house, data in totals.items():
        avg_amps = average(data["amp_readings"])

        if avg_amps is None:
            data["kwh"] = 0.0
        else:
            avg_watts = avg_amps * HOUSE_VOLTAGE
            data["kwh"] = (avg_watts / 1000) * total_hours

    return totals


def get_electricity_comparison_response():
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=24)

    readings = get_electricity_readings(start_time, now)
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
        "- Formula: kWh = (average amps * volts / 1000) * hours",
        "",
        "Metadata used:",
        "- House ownership came from DEVICE_METADATA",
        "- Electricity readings were grouped by house",
        "- Board names were used to connect each record back to its device and house",
        "",
        "Reading counts:"
    ]

    for house in ["House A", "House B"]:
        count = len(totals.get(house, {}).get("amp_readings", []))
        lines.append(f"- {house}: {count} electricity reading(s)")

    if house_b_kwh == 0.0:
        lines.extend([
            "",
            "Note:",
            "House B currently shows 0.0000 kWh. If this is unexpected, add your partner's",
            "real board names to DEVICE_METADATA and set PARTNER_DATABASE_URL in your .env file."
        ])

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