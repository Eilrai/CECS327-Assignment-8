# CECS 327 Assignment 8
# TCP Server - Fridge Moisture Checkpoint

import os
import json
import socket
import psycopg2
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

CHRIS_DATABASE_URL = os.getenv("CHRIS_DATABASE_URL")

DEVICE_METADATA = {
    "Dishwasher_Board": {
        "house": "House A",
        "device_type": "dishwasher",
        "device_group": "Old Dishwasher"
    },
    "Fridgeboard": {
        "house": "House A",
        "device_type": "fridge",
        "device_group": "SmartFridge 1"
    },
    "Fridgeboard duplicate 1 876baa87-2d42-4d36-b3eb-c5b5026a6b3b": {
        "house": "House A",
        "device_type": "fridge",
        "device_group": "SmartFridge 2"
    }
}


def get_boards_by_type(device_type):
    boards = []

    for board_name, info in DEVICE_METADATA.items():
        if info["device_type"] == device_type:
            boards.append(board_name)

    return boards


def is_moisture_sensor(sensor_name):
    sensor_name = sensor_name.lower()
    return "moisture" in sensor_name or "humidity" in sensor_name


def parse_moisture_readings(db_time, payload):
    if isinstance(payload, str):
        payload = json.loads(payload)

    board_name = payload.get("board_name")

    if board_name not in DEVICE_METADATA:
        return []

    device_info = DEVICE_METADATA[board_name]

    if device_info["device_type"] != "fridge":
        return []

    readings = []

    for key, value in payload.items():
        if not is_moisture_sensor(key):
            continue

        try:
            readings.append({
                "time": db_time,
                "board_name": board_name,
                "device_group": device_info["device_group"],
                "value": float(value)
            })
        except (ValueError, TypeError):
            pass

    return readings


def fetch_fridge_moisture_readings(start_time, end_time):
    fridge_boards = get_boards_by_type("fridge")

    conn = psycopg2.connect(CHRIS_DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT time, payload
        FROM sensor_data_virtual
        WHERE time >= %s
          AND time < %s
          AND payload->>'board_name' = ANY(%s)
        ORDER BY time ASC;
    """, (start_time, end_time, fridge_boards))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    readings = []

    for db_time, payload in rows:
        readings.extend(parse_moisture_readings(db_time, payload))

    return readings


def average(values):
    if len(values) == 0:
        return None

    return sum(values) / len(values)


def format_average(value):
    if value is None:
        return "No data available"

    return f"{value:.2f}%"


def values_since(readings, start_time):
    values = []

    for reading in readings:
        if reading["time"] >= start_time:
            values.append(reading["value"])

    return values


def get_average_fridge_moisture_response():
    now = datetime.now(timezone.utc)

    time_windows = {
        "Past hour": now - timedelta(hours=1),
        "Past week": now - timedelta(days=7),
        "Past month": now - timedelta(days=30)
    }

    month_start = time_windows["Past month"]
    readings = fetch_fridge_moisture_readings(month_start, now)

    lines = [
        "Average moisture inside House A kitchen fridges:",
        ""
    ]

    for label, start_time in time_windows.items():
        values = values_since(readings, start_time)
        avg = average(values)
        lines.append(f"{label}: {format_average(avg)} based on {len(values)} reading(s)")

    lines.extend([
        "",
        "Data source: Chris / House A NeonDB",
        "",
        "Boards included:"
    ])

    for board in get_boards_by_type("fridge"):
        lines.append(f"- {board}")

    return "\n".join(lines)


MOISTURE_QUERY = "what is the average moisture inside our kitchen fridges in the past hours, week and month?"
WATER_QUERY = "what is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?"
ELECTRICITY_QUERY = "which house consumed more electricity in the past 24 hours, and by how much?"

def process_query(query):
    query = query.strip().lower()

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
