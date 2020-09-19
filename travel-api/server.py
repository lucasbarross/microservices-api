import http.server
import socketserver
import json 

class Server(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        print(path, flush = True)
        if path.startswith("/api/travels/1"):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(bytes(json.dumps({ 'id': 1, 'price': '3200' }).encode('utf-8')))
        else:
            self.send_response(404)
            self.end_headers()

            
def serve_forever(port):
    print("Listening on " + str(port), flush = True)
    socketserver.TCPServer(('', port), Server).serve_forever()

if __name__ == "__main__":
    serve_forever(8080)
