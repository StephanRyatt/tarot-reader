from http.server import HTTPServer
from urllib.parse import urlsplit

from api.tarot import handler as TarotHandler
from api.mcp import serve as serve_mcp

MCP_PATHS = {"/mcp", "/api/mcp"}


class DevHandler(TarotHandler):
    def _route(self) -> str:
        return urlsplit(self.path).path.rstrip("/") or "/"

    def _is_mcp(self) -> bool:
        return self._route() in MCP_PATHS

    def do_POST(self):
        if self._is_mcp():
            serve_mcp(self)
        else:
            super().do_POST()

    def do_GET(self):
        if self._is_mcp():
            return serve_mcp(self)
        if self._route().startswith("/.well-known/"):
            return self._send_json(404, {"error": "Not found"})
        return super().do_GET()

    def do_OPTIONS(self):
        if self._is_mcp():
            serve_mcp(self)
        else:
            self.send_error(501, "Unsupported method ('OPTIONS')")

    def do_DELETE(self):
        if self._is_mcp():
            serve_mcp(self)
        else:
            self.send_error(501, "Unsupported method ('DELETE')")


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), DevHandler)
    print("Listening on http://127.0.0.1:8000/api/tarot (any non-MCP path)")
    print("MCP at http://127.0.0.1:8000/mcp")
    server.serve_forever()
