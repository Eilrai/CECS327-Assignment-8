# CECS 327 Assignment 5: Echo Client and Server
# Thien (Chris) Nguyen
# 030088940

import socket

def start_server():
    host = input("Enter server IP address to bind to: ").strip() # Take user input for desired server IP 
    
    while True:
        port_input = input("Enter port number to listen on: ").strip() # Take user input for desired port number to listen on

        # Edge case handling
        try:
            port = int(port_input)
            if 0 <= port <= 65535:
                break
            else:
                print("Error: Port must be between 0 and 65535.")
        except ValueError:
            print("Error: Please enter a valid integer for the port.")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Confirmation that server is up and listening for potential client
    try:
        server_socket.bind((host, port))
        server_socket.listen(1)
        print(f"\nServer is listening on {host}:{port}")
        print("Waiting for a client to connect...\n")

        conn, addr = server_socket.accept()
        print(f"Connected by {addr}")

    # Incoming data handling 
        while True:
            data = conn.recv(1024)
            if not data:
                print("Client disconnected.")
                break

            message = data.decode()
            print(f"Received from client: {message}")

            # Replies to client with user's message in uppercase
            response = message.upper()
            conn.sendall(response.encode())
            print(f"Sent back: {response}")

    except OSError as e:
        print(f"Socket error: {e}")
    finally:
        server_socket.close()
        print("Server socket closed.")

if __name__ == "__main__":
    start_server()