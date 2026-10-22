#!/usr/bin/env python3
"""Single-device local appliance server. No cloud/API keys/CDN required."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import logging
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import config
from ai import KitchenAI
from gestures import GestureEngine
import schema

LOG = logging.getLogger('kitchen')

class Jobs:
    def __init__(self, ai):
        self.ai = ai
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.lock = threading.Lock()
        self.records = {}
        self.active = None

    def submit(self, kind, payload):
        with self.lock:
            if self.active:
                raise BlockingIOError('AI 작업 중입니다. 완료 후 다시 시도하세요.')
            job_id = secrets.token_hex(12)
            self.records[job_id] = {'status': 'running', 'kind': kind, 'started': time.time()}
            # Retain only the most recent 30 jobs.
            for key in list(self.records)[:-30]:
                self.records.pop(key)
            self.active = job_id
        self.pool.submit(self._work, job_id, kind, payload)
        return job_id

    def _work(self, job_id, kind, payload):
        try:
            result = self.ai.run(kind, payload)
            record = {'status': 'done', 'kind': kind, 'result': result}
        except Exception as exc:
            LOG.exception('AI job failed')
            record = {'status': 'error', 'kind': kind, 'error': str(exc)}
        with self.lock:
            record['elapsed_seconds'] = round(time.time() - self.records[job_id]['started'], 2)
            self.records[job_id].update(record)
            self.active = None

    def get(self, job_id):
        with self.lock:
            return dict(self.records[job_id]) if job_id in self.records else None


def make_handler(demo=False):
    jobs = Jobs(KitchenAI(demo))
    gesture = GestureEngine()
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            LOG.info(fmt, *args)

        def send(self, status, data, content_type='application/json; charset=utf-8'):
            raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def valid_host(self):
            host = self.headers.get('Host', '')
            return host in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {'error': 'localhost에서 접속하세요.'})
            path = urlparse(self.path).path
            if path == '/api/health':
                return self.send(200, {'version': '1.2.0', 'demo': demo, 'models': config.model_status(), 'csrf': token})
            if path.startswith('/api/jobs/'):
                record = jobs.get(path.rsplit('/', 1)[-1])
                return self.send(200 if record else 404, record or {'error': '작업 없음'})
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/core.js': ('core.js', 'text/javascript; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path not in files:
                return self.send(404, {'error': '경로 없음'})
            filename, mime = files[path]
            return self.send(200, (config.SOURCE / 'static' / filename).read_bytes(), mime)

        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-Kitchen-Token') != token:
                return self.send(403, {'error': '페이지를 새로고침하세요.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4_200_000:
                    return self.send(413, {'error': '요청 크기 초과 또는 빈 요청'})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError('JSON 객체가 필요합니다.')
                path = urlparse(self.path).path
                if path == '/api/gesture':
                    return self.send(200, gesture.recognize(payload.get('image')))
                kind = {'/api/ingredients': 'ingredients', '/api/menus': 'menus', '/api/recipe': 'recipe'}.get(path)
                if not kind:
                    return self.send(404, {'error': '경로 없음'})
                if kind == 'ingredients':
                    from ai import decode_image
                    decode_image(payload.get('image'))
                else:
                    payload['ingredients'] = schema.strings(payload.get('ingredients'), '확인 재료', 1, 30)
                    request = payload.get('request', '')
                    if not isinstance(request, str) or len(request) > 600:
                        raise ValueError('요청은 600자 이하로 입력하세요.')
                if kind == 'recipe':
                    menu = payload.get('menu')
                    if not isinstance(menu, dict):
                        raise ValueError('메뉴를 선택하세요.')
                    payload['menu'] = {'name': schema.string(menu.get('name'), '메뉴명', 80),
                                       'missing': schema.strings(menu.get('missing', []), '추가 재료', 0, 20)}
                return self.send(202, {'job_id': jobs.submit(kind, payload)})
            except BlockingIOError as exc:
                return self.send(409, {'error': str(exc)})
            except (ValueError, TypeError, KeyError) as exc:
                return self.send(400, {'error': str(exc)})
            except Exception as exc:
                LOG.exception('Request failed')
                return self.send(500, {'error': str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description='비접촉 AI 레시피북')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--demo', action='store_true', help='LLM/VLM 없이 고정 예시로 UI 확인. 제스처는 실제 모델 필요.')
    parser.add_argument('--check', action='store_true', help='모델 파일과 패키지 설치 검사')
    args = parser.parse_args()
    if args.check:
        modules = {m: importlib.util.find_spec(m) is not None for m in ['PIL', 'numpy', 'mediapipe', 'llama_cpp']}
        status = {'models_dir': str(config.MODELS), 'models': config.model_status(), 'packages': modules}
        print(json.dumps(status, ensure_ascii=False, indent=2))
        raise SystemExit(0 if all(modules.values()) and all(x['exists'] for x in status['models'].values()) else 1)
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(args.demo))
    server.daemon_threads = True
    print(f'비접촉 AI 레시피북: http://127.0.0.1:{args.port}  |  ' + ('DEMO 예시 모드' if args.demo else '로컬 AI 모드'), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n서버 종료')
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
