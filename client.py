# CECS 327 Assignment 5: Echo Client and Server
# Thien (Chris) Nguyen
# 030088940

import socket

def start_client():
    # Take user input for desired server IP address and port number
    while True:
        server_ip = input("Enter server IP address: ").strip()
        port_input = input("Enter server port number: ").strip()

        # Edge case handling
        try:
            server_port = int(port_input)
            if not (0 <= server_port <= 65535):
                print("Error: Port must be between 0 and 65535.\n")
                continue
        except ValueError:
            print("Error: Invalid port number.\n")
            continue

        # Handles connectivity state
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((server_ip, server_port))
            print(f"Connected to server at {server_ip}:{server_port}\n")
            break

        # Error handling
        except socket.gaierror:
            print("Error: Invalid IP address or hostname.\n")
        except ConnectionRefusedError:
            print("Error: Connection refused. Make sure the server is running and reachable.\n")
        except TimeoutError:
            print("Error: Connection timed out.\n")
        except OSError as e:
            print(f"Connection error: {e}\n")

    try:
        while True:
            message = input("Enter a message to send ('quit' to exit): ")

            # Gives client the option to exit by typing "quit"
            if message.lower() == "quit":
                print("Closing client.")
                break

            # Message transmission handling
            client_socket.sendall(message.encode())
            response = client_socket.recv(1024).decode()
            print(f"Server response: {response}\n")

    except OSError as e:
        print(f"Communication error: {e}")
    finally:
        client_socket.close()
        print("Client socket closed.")

if __name__ == "__main__":
    start_client()
