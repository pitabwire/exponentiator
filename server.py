import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

from application import Exponentiator
from utility import get_service_name

hostName = "0.0.0.0"
serverPort = 8080

log = logging.getLogger(__name__)

exponentiator = Exponentiator()


class ExponentiatorRequestHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        results = exponentiator.execute_check()

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<html><head><title>Exponentiator</title></head>", "utf-8"))
        self.wfile.write(bytes("<body>", "utf-8"))
        self.wfile.write(bytes(f"<p>{get_service_name()} results : {results}</p>", "utf-8"))
        self.wfile.write(bytes("</body></html>", "utf-8"))


if __name__ == "__main__":

    webServer = HTTPServer((hostName, serverPort), ExponentiatorRequestHandler)
    log.info("Server started http://%s:%s" % (hostName, serverPort))

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    log.info("Server stopped.")