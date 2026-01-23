from http.server import HTTPServer
from api.tarot import handler  # imports your BaseHTTPRequestHandler subclass

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), handler)
    print("Listening on http://127.0.0.1:8000")
    server.serve_forever()