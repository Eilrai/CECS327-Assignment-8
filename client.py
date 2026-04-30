# CECS 327 Assignment 8

import socket


SUPPORTED_QUERIES = {
    "1": "What is the average moisture inside our kitchen fridges in the past hours, week and month?",
    "2": "What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?",
    "3": "Which house consumed more electricity in the past 24 hours, and by how much?"
}


def get_server_port():
    while True:
        port_input = input("Enter server port number: ").strip()

        try:
            port = int(port_input)

            if 0 <= port <= 65535:
                return port

            print("Error: Port must be between 0 and 65535.\n")

        except ValueError:
            print("Error: Invalid port number.\n")


def connect_to_server():
    while True:
        server_ip = input("Enter server IP address: ").strip()
        server_port = get_server_port()

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((server_ip, server_port))

            print(f"\nConnected to server at {server_ip}:{server_port}\n")
            return client_socket

        except socket.gaierror:
            print("Error: Invalid IP address or hostname.\n")
        except ConnectionRefusedError:
            print("Error: Connection refused. Make sure the server is running.\n")
        except TimeoutError:
            print("Error: Connection timed out.\n")
        except OSError as error:
            print(f"Connection error: {error}\n")


def display_menu():
    print("Pick a query:")
    print("1. Get average moisture readings for kitchen fridges")
    print("2. Get average water consumption for smart dishwashers")
    print("3. Compare electricity usage between houses")
    print("4. Quit")


def get_user_query():
    while True:
        display_menu()
        choice = input("\nEnter your choice: ").strip()

        if choice == "4" or choice.lower() == "quit":
            return None

        if choice in SUPPORTED_QUERIES:
            return SUPPORTED_QUERIES[choice]

        print("\nSorry, this query cannot be processed. Please try one of the supported queries.\n")


def start_client():
    client_socket = connect_to_server()

    try:
        while True:
            query = get_user_query()

            if query is None:
                print("\nClosing client.")
                break

            print("\nSending query to server...")
            client_socket.sendall(query.encode())

            response = client_socket.recv(8192).decode()

            print("\nServer response:")
            print(response)
            print()

    except OSError as error:
        print(f"Communication error: {error}")

    finally:
        client_socket.close()
        print("Client socket closed.")


if __name__ == "__main__":
    start_client()