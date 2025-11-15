from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import json

class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/restart-chromium':
            try:
                # Supervisorを使ってChromiumを再起動
                result = subprocess.run(['supervisorctl', '-c', '/config/supervisord.conf', 'restart', 'Chromium'], check=True, capture_output=True, text=True)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"message": "Chromium restart initiated.", "details": result.stdout}
                self.wfile.write(json.dumps(response).encode())
            except subprocess.CalledProcessError as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"message": "Failed to restart Chromium.", "error": e.stderr}
                self.wfile.write(json.dumps(response).encode())
            except FileNotFoundError:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"message": "supervisorctl command not found."}
                self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"message": "Endpoint not found. Use POST /restart-chromium."}
            self.wfile.write(json.dumps(response).encode())

    def do_GET(self):
        self.send_response(405)
        self.send_header('Content-type', 'application/json')
        self.send_header('Allow', 'POST')
        self.end_headers()
        response = {"message": "Method Not Allowed. Use POST."}
        self.wfile.write(json.dumps(response).encode())

def run(server_class=HTTPServer, handler_class=RequestHandler, port=9221):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting httpd on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
