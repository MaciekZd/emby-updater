#!/usr/bin/env python3
"""EmbyUpdater - HTTP server with session auth, scheduler, i18n."""
import http.server, json, os, hashlib, secrets, subprocess, urllib.parse, time, re
from pathlib import Path

QPKG_ROOT  = os.environ.get('QPKG_ROOT', os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(QPKG_ROOT, 'config.json')
RESET_FILE  = os.path.join(QPKG_ROOT, 'reset_credentials')
SCRIPT      = os.path.join(QPKG_ROOT, 'emby-updater.sh')
PORT        = int(os.environ.get('HTTP_PORT', 9876))
CRONTAB     = '/etc/config/crontab'
CRON_MARKER = '# EmbyUpdater-auto'
SESSION_TTL = 28800  # 8h

sessions = {}  # token -> expiry

def sha(s): return hashlib.sha256(s.encode()).hexdigest()

DEFAULT_CFG = {
    "username": "admin",
    "password_hash": sha("admin"),
    "language": "pl",
    "schedule": {"enabled": False, "channel": "stable", "frequency": "weekly", "day": 0, "hour": 3}
}

def load_cfg():
    if os.path.exists(RESET_FILE):
        os.remove(RESET_FILE)
        save_cfg(DEFAULT_CFG.copy())
        return DEFAULT_CFG.copy()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CFG.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULT_CFG.copy()

def save_cfg(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

def new_session():
    t = secrets.token_hex(32)
    sessions[t] = time.time() + SESSION_TTL
    return t

def valid_session(token):
    if not token: return False
    exp = sessions.get(token)
    if exp and time.time() < exp:
        sessions[token] = time.time() + SESSION_TTL
        return True
    sessions.pop(token, None)
    return False

def get_cookie(headers, name):
    for part in headers.get('Cookie', '').split(';'):
        part = part.strip()
        if part.startswith(name + '='):
            return part[len(name)+1:]
    return None

def run_script(action, timeout=300):
    r = subprocess.run(['sh', SCRIPT, action], capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()

def apply_schedule(sched):
    lines = []
    if os.path.exists(CRONTAB):
        with open(CRONTAB) as f:
            lines = [l for l in f if CRON_MARKER not in l]
    if sched.get('enabled'):
        ch  = sched.get('channel', 'stable')
        act = 'update' if ch == 'stable' else 'update-beta'
        h   = int(sched.get('hour', 3))
        if sched.get('frequency') == 'daily':
            expr = f'0 {h} * * *'
        else:
            d    = int(sched.get('day', 0))
            expr = f'0 {h} * * {d}'
        lines.append(f'{expr} sh {SCRIPT} {act} {CRON_MARKER}\n')
    with open(CRONTAB, 'w') as f:
        f.writelines(lines)
    subprocess.run(['crontab', CRONTAB], capture_output=True)

def read_cron_line():
    if not os.path.exists(CRONTAB): return None
    with open(CRONTAB) as f:
        for l in f:
            if CRON_MARKER in l: return l.strip()
    return None

MIME = {'.html':'text/html;charset=utf-8', '.js':'application/javascript',
        '.css':'text/css', '.gif':'image/gif', '.ico':'image/x-icon'}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def auth(self): return valid_session(get_cookie(self.headers, 'eu_sess'))

    def body(self):
        n = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(n).decode()

    def send_json(self, data, code=200):
        b = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(b)

    def send_file(self, rel):
        path = os.path.join(QPKG_ROOT, rel)
        if not os.path.exists(path):
            self.send_response(404); self.end_headers(); return
        ext  = os.path.splitext(path)[1]
        mime = MIME.get(ext, 'application/octet-stream')
        with open(path, 'rb') as f: b = f.read()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def redir(self, loc, cookie=None):
        self.send_response(302)
        if cookie: self.send_header('Set-Cookie', cookie)
        self.send_header('Location', loc)
        self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ('/', '/index.html'):
            if not self.auth(): self.redir('/login'); return
            self.send_file('index.html')
        elif p == '/login':
            self.send_file('login.html')
        elif p == '/logout':
            t = get_cookie(self.headers, 'eu_sess')
            sessions.pop(t, None)
            self.redir('/login', 'eu_sess=; Path=/; Max-Age=0')
        elif p.startswith('/api/'):
            if not self.auth(): self.send_json({'error':'unauthorized'}, 401); return
            self._api_get(p)
        else:
            self.send_file(p.lstrip('/'))

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p == '/api/login':
            self._login()
        elif p.startswith('/api/'):
            if not self.auth(): self.send_json({'error':'unauthorized'}, 401); return
            self._api_post(p)
        else:
            self.send_response(404); self.end_headers()

    def _login(self):
        params = urllib.parse.parse_qs(self.body())
        user = params.get('username', [''])[0]
        pw   = params.get('password',  [''])[0]
        cfg  = load_cfg()
        if user == cfg['username'] and sha(pw) == cfg['password_hash']:
            tok = new_session()
            self.redir('/', f'eu_sess={tok}; Path=/; HttpOnly; Max-Age={SESSION_TTL}')
        else:
            self.redir('/login?error=1')

    def _api_get(self, p):
        if p == '/api/status':
            out = run_script('status')
            cfg = load_cfg()
            self.send_json({'output': out, 'schedule': cfg.get('schedule', {}),
                            'cron': read_cron_line(), 'language': cfg.get('language','pl')})
        elif p == '/api/check':
            self.send_json({'output': run_script('check')})
        elif p == '/api/config':
            cfg = load_cfg()
            self.send_json({k: v for k, v in cfg.items() if k != 'password_hash'})
        else:
            self.send_json({'error':'not found'}, 404)

    def _api_post(self, p):
        raw = self.body()
        try:    data = json.loads(raw) if raw else {}
        except: data = {}

        if p == '/api/update':
            ch  = data.get('channel', 'stable')
            act = 'update' if ch == 'stable' else 'update-beta'
            self.send_json({'output': run_script(act)})

        elif p == '/api/settings':
            cfg = load_cfg()
            if 'language' in data:  cfg['language']  = data['language']
            if data.get('username'): cfg['username']  = data['username']
            if data.get('password'): cfg['password_hash'] = sha(data['password'])
            if data.get('logout_all'): sessions.clear()
            save_cfg(cfg)
            self.send_json({'ok': True})

        elif p == '/api/schedule':
            cfg = load_cfg()
            cfg['schedule'] = data
            save_cfg(cfg)
            try:
                apply_schedule(data)
                self.send_json({'ok': True, 'cron': read_cron_line()})
            except Exception as e:
                self.send_json({'ok': False, 'error': str(e)})

        else:
            self.send_json({'error':'not found'}, 404)

if __name__ == '__main__':
    load_cfg()  # handle reset on startup
    srv = http.server.HTTPServer(('', PORT), H)
    print(f'EmbyUpdater listening on :{PORT}')
    srv.serve_forever()
