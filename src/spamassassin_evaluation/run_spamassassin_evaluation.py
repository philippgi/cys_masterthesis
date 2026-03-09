import socket


def test_tcp_connection(host="127.0.0.1", port=783, timeout=5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            print(f"Connection successful: {host}:{port} is reachable")
    except Exception as e:
        print("Connection failed:")
        print(repr(e))


def main():
    print("Testing TCP connection to SpamAssassin...\n")
    test_tcp_connection()


if __name__ == "__main__":
    main()