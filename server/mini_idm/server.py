"""
Yerel HTTP API. Chrome uzantisi ve web arayuzu buraya konusur.

Sadece 127.0.0.1'e baglanir. Basit bir token ile korunur (config'de tutulur),
boylece rastgele bir web sayfasi localhost'a POST atip dosya indiremez.

Uc noktalar:
  GET  /api/ping                 -> {"ok": true, "version": ...}
  GET  /api/status               -> tum isler + ayarlar
  POST /api/add                  -> {url, filename?, headers?, connections?}
  POST /api/pause    {id}
  POST /api/resume   {id}
  POST /api/cancel   {id}
  POST /api/remove   {id}
  POST /api/clear
  POST /api/config   {out_dir?, connections?, max_concurrent?, speed_limit?}
"""

import json
import os
import secrets
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .manager import CONFIG_DIR, Manager

VERSION = "0.1.0"
HOST, PORT = "127.0.0.1", 9614
UI_DIR = os.path.join(os.path.dirname(__file__), "ui")
TOKEN_PATH = os.path.join(CONFIG_DIR, "token")

manager = Manager()


def get_token():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            tok = f.read().strip()
            if tok:
                return tok
    tok = secrets.token_urlsafe(24)
    with open(TOKEN_PATH, "w") as f:
        f.write(tok)
    os.chmod(TOKEN_PATH, 0o600)
    return tok


TOKEN = get_token()

# app.py (native pencere) burayi doldurur; extension'dan/UI'dan yeni is
# eklendiginde pencereyi one getirmek icin kullanilir. Duz "python run.py"
# ile calisirken None kalir, sorun olmaz.
_focus_cb = None


def set_focus_callback(fn):
    global _focus_cb
    _focus_cb = fn


def pick_folder(initial=""):
    """
    Native "klasor sec" penceresi acar (Windows: WinForms FolderBrowserDialog).
    Masaustu programlarindaki gibi hissettirmesi icin - web sayfasi disk uzerinde
    dolasamayacagi icin secimi sunucu (bu process) tarafinda yapiyoruz.
    """
    if sys.platform != "win32":
        return None
    safe_initial = initial.replace('"', "").replace("`", "") if initial else ""
    script = (
        "Add-Type -AssemblyName System.Windows.Forms\n"
        "$f = New-Object System.Windows.Forms.FolderBrowserDialog\n"
        "$f.Description = 'Kayit klasorunu sec'\n"
        "$f.ShowNewFolderButton = $true\n"
        f"if (\"{safe_initial}\" -ne \"\" -and (Test-Path \"{safe_initial}\")) "
        f"{{ $f.SelectedPath = \"{safe_initial}\" }}\n"
        "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
        "{ Write-Output $f.SelectedPath }\n"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=120,
        )
        return r.stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = f"mini-idm/{VERSION}"

    # ------------------------------------------------------------- yardimcilar

    def log_message(self, *args):
        pass                                   # konsolu kirletme

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except ValueError:
            return {}

    def _authorized(self):
        return self.headers.get("X-Token") == TOKEN

    # ------------------------------------------------------------- metodlar

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/ping":
            return self._json({"ok": True, "version": VERSION})

        if path.startswith("/api/"):
            if not self._authorized():
                return self._json({"error": "unauthorized"}, 401)
            if path == "/api/status":
                return self._json(manager.snapshot())
            if path == "/api/browse-folder":
                start = parse_qs(parsed.query).get("start", [""])[0]
                folder = pick_folder(start)
                return self._json({"ok": bool(folder), "path": folder or ""})
            return self._json({"error": "not found"}, 404)

        return self._serve_ui(path)

    def do_POST(self):
        path = self.path.split("?")[0]
        if not self._authorized():
            return self._json({"error": "unauthorized"}, 401)

        data = self._body()
        jid = data.get("id")

        if path == "/api/add":
            url = (data.get("url") or "").strip()
            if not url.lower().startswith(("http://", "https://")):
                return self._json({"error": "gecersiz url"}, 400)
            job = manager.add(
                url=url,
                filename=data.get("filename"),
                headers=data.get("headers"),
                connections=data.get("connections"),
                out_dir=(data.get("out_dir") or "").strip() or None,
            )
            if _focus_cb:
                try:
                    _focus_cb()
                except Exception:
                    pass
            return self._json({"ok": True, "id": job.id})

        actions = {
            "/api/pause": manager.pause,
            "/api/resume": manager.resume,
            "/api/cancel": manager.cancel,
            "/api/remove": manager.remove,
        }
        if path in actions:
            if not jid:
                return self._json({"error": "id gerekli"}, 400)
            actions[path](jid)
            return self._json({"ok": True})

        if path == "/api/clear":
            manager.clear_finished()
            return self._json({"ok": True})

        if path == "/api/config":
            return self._json({"ok": True, "config": manager.update_config(data)})

        return self._json({"error": "not found"}, 404)

    # ------------------------------------------------------------- statik ui

    def _serve_ui(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(UI_DIR, rel))
        if not full.startswith(UI_DIR) or not os.path.isfile(full):
            return self._json({"error": "not found"}, 404)

        ctype = {".html": "text/html", ".js": "text/javascript",
                 ".css": "text/css"}.get(os.path.splitext(full)[1],
                                         "application/octet-stream")
        with open(full, "rb") as f:
            body = f.read()
        if rel == "index.html":
            body = body.replace(b"__TOKEN__", TOKEN.encode())
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"  mini-IDM v{VERSION}")
    print(f"  Arayuz : http://{HOST}:{PORT}/")
    print(f"  Klasor : {manager.config['out_dir']}")
    print(f"  Token  : {TOKEN}")
    print("  (Bu token'i Chrome uzantisinin ayarlarina yapistir)\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatiliyor...")
        httpd.shutdown()
