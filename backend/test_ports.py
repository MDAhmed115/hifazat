import socket
for p in [3000, 5000, 8000, 8080, 9000, 8888]:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p))
        print(p, "OK")
    except OSError as e:
        print(p, "BLOCKED:", e)
    finally:
        s.close()
