import http.server
import subprocess
import os
import hmac
import hashlib

PORT = 5001
SECRET = os.getenv('WEBHOOK_SECRET', '') # Optional: to verify GitHub payload signature

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # Signature verification if SECRET is set
        if SECRET:
            signature = self.headers.get('X-Hub-Signature-256', '')
            if not signature:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Missing signature")
                return
            
            try:
                # Signature format is sha256=xxxx
                sha_name, signature_val = signature.split('=', 1)
                mac = hmac.new(SECRET.encode(), post_data, hashlib.sha256)
                if not hmac.compare_digest(mac.hexdigest(), signature_val):
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b"Invalid signature")
                    return
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Signature parsing error: {e}".encode())
                return

        # Execute update.sh
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
        
        # Run update.sh in a background process using absolute paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        update_script = os.path.join(script_dir, "update.sh")
        print(f"🔔 Webhook received! Running {update_script} in {script_dir}...")
        subprocess.Popen([update_script], cwd=script_dir)

def run():
    server_address = ('', PORT)
    httpd = http.server.HTTPServer(server_address, WebhookHandler)
    print(f"📡 Webhook listener running on port {PORT}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
