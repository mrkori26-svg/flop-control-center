import json, os, sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

from adapters.filesystem import open_repo
from adapters.tasks import control as task_control
from core.config import load_config, root_path
from core.demo import snapshot as demo_snapshot
from core.jobs import start as start_job
from core.public_snapshot import build
from core.empires_journeys import find_journey

HERE = Path(__file__).resolve().parent
DEMO = '--demo' in sys.argv
CFG = None if DEMO else load_config()
UI = HERE / 'ui' / 'public'


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        rel = urlparse(path).path.lstrip('/') or 'index.html'
        return str(UI / rel)

    def send_json(self, obj, code=200):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        if self.path.startswith('/api/health'):
            return self.send_json({'ok': True, 'service': 'flop-control-center', 'mode': 'public-safe'})
        if self.path.startswith('/api/status'):
            return self.send_json(demo_snapshot() if DEMO else build(CFG))
        if self.path.startswith('/api/empires/journey/'):
            if DEMO:
                return self.send_json({'ok':False,'error':'DEMO_NO_JOURNEY_EVIDENCE'}, 404)
            journey_id = unquote(urlparse(self.path).path.removeprefix('/api/empires/journey/'))
            cfg = CFG.get('empires_journeys', {})
            source = cfg.get('path')
            if source and not Path(source).is_absolute():
                source = str(root_path(CFG) / source)
            value = find_journey(source, journey_id)
            return self.send_json(value if value else {'error':'JOURNEY_NOT_FOUND'}, 200 if value else 404)
        if self.path.startswith('/api/evidence'):
            snap = demo_snapshot() if DEMO else build(CFG)
            return self.send_json(snap.get('evidence_registry', {'schema':'flop.evidence-registry.v1','records':[],'rejected':[]}))
        return super().do_GET()

    def do_POST(self):
        if DEMO:
            return self.send_json({'ok': False, 'error': 'DEMO_READ_ONLY'}, 403)
        size = int(self.headers.get('Content-Length', '0'))
        try:
            body = json.loads(self.rfile.read(size) or b'{}')
        except Exception:
            return self.send_json({'ok': False, 'error': 'invalid json'}, 400)
        path = urlparse(self.path).path
        repos = CFG.get('repositories', [])
        tasks = CFG.get('tasks', [])
        if path == '/api/check':
            try:
                job = start_job(root_path(CFG), body.get('repo'), repos)
            except ValueError as exc:
                return self.send_json({'ok': False, 'error': str(exc)}, 400)
            return self.send_json({'ok': True, 'job': job})
        if path == '/api/task':
            task, action = body.get('task'), body.get('action')
            if task not in tasks or action not in {'start', 'stop'}:
                return self.send_json({'ok': False, 'error': 'invalid action'}, 400)
            result = task_control(task, action)
            return self.send_json(result, 200 if result.get('ok') else 500)
        if path == '/api/open':
            result = open_repo(root_path(CFG), body.get('repo'), repos)
            return self.send_json(result, 200 if result.get('ok') else 400)
        return self.send_json({'ok': False, 'error': 'not found'}, 404)


if __name__ == '__main__':
    os.chdir(HERE)
    port = int(os.environ.get('FLOP_CONTROL_CENTER_PORT', '8765'))
    mode = 'demo/read-only' if DEMO else 'public-safe'
    print(f'FLOP Control Center ({mode}): http://127.0.0.1:{port}')
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
