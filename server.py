import json
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
        content_len = int(self.headers.get('Content-Length'))
        post_body = self.rfile.read(content_len)

        body_json = json.loads(post_body)
        compound_pct = 100
        if 'compound_pct' in body_json:
            compound_pct = int(body_json['compound_pct'])

        results = exponentiator.execute_check(compound_pct=compound_pct)

        withdraw_results = "Not applicable"
        if self.path == '/withdraw':

            if 'withdraw_interval_in_hours' in body_json:
                withdraw_interval = int(body_json['withdraw_interval_in_hours'])
                withdraw_results = exponentiator.execute_withdraw(
                    compound_pct=compound_pct,
                    interval_in_hours=withdraw_interval
                )

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<html><head><title>Exponentiator</title></head>", "utf-8"))
        self.wfile.write(bytes("<body>", "utf-8"))
        self.wfile.write(bytes(f"""
            <p>
                {get_service_name()} 
                <br/>
                <br/>
                    check results : {results}
                 <br/>
                    withdraw results: {withdraw_results}
            </p>
            """, "utf-8"))
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
