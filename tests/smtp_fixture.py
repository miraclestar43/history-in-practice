"""Minimal local SMTP(S) server for tests. Binds 127.0.0.1 only.

Behaviour per recipient (set on the server object):
  refuse_rcpt: set of addresses answered 550 at RCPT
  drop_in_data: set of addresses for which the connection is closed after the
                message body arrives but before the final reply (-> unknown)
Received messages are stored in .messages as (rcpt, bytes)."""
import socket, socketserver, ssl, subprocess, tempfile, threading
from pathlib import Path


class _H(socketserver.StreamRequestHandler):
    def _w(self, line):
        self.wfile.write((line + "\r\n").encode()); self.wfile.flush()

    def handle(self):
        srv = self.server; rcpt = None
        self._w("220 localhost test SMTP")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            cmd = line.decode(errors="replace").strip(); up = cmd.upper()
            if up.startswith(("EHLO", "HELO")):
                self._w("250-localhost"); self._w("250 AUTH PLAIN LOGIN")
            elif up.startswith("AUTH"):
                self._w("235 ok")
            elif up.startswith("MAIL FROM"):
                self._w("250 ok")
            elif up.startswith("RCPT TO"):
                rcpt = cmd.split(":", 1)[1].strip().strip("<>")
                self._w("550 no such user" if rcpt in srv.refuse_rcpt else "250 ok")
            elif up == "DATA":
                self._w("354 go")
                body = b""
                while True:
                    l = self.rfile.readline()
                    if not l or l in (b".\r\n", b".\n"):
                        break
                    body += l
                if rcpt in srv.drop_in_data:
                    srv.messages.append((rcpt, body)); self.connection.shutdown(socket.SHUT_RDWR); return
                srv.messages.append((rcpt, body)); self._w("250 queued")
            elif up == "QUIT":
                self._w("221 bye"); return
            elif up in ("RSET", "NOOP"):
                self._w("250 ok")
            else:
                self._w("502 unknown")


class _TLSServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True; daemon_threads = True

    def __init__(self, ctx):
        self.ctx = ctx
        super().__init__(("127.0.0.1", 0), _H)

    def get_request(self):
        sock, addr = super().get_request()
        return (self.ctx.wrap_socket(sock, server_side=True) if self.ctx else sock), addr


def start(tls=True):
    ctx = None
    if tls:
        d = Path(tempfile.mkdtemp(prefix="hip-smtp-"))
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
                        "-keyout", str(d / "k.pem"), "-out", str(d / "c.pem")], check=True, capture_output=True)
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH); ctx.load_cert_chain(d / "c.pem", d / "k.pem")
    s = _TLSServer(ctx); s.refuse_rcpt = set(); s.drop_in_data = set(); s.messages = []
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s
