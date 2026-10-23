"""One inference worker with a bounded observable job registry."""
import secrets, threading, time, logging
from concurrent.futures import ThreadPoolExecutor
LOG = logging.getLogger("kitchen.jobs")

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
            record = {'status': 'done', 'kind': kind, 'result': result, 'metrics': getattr(self.ai, 'last_metrics', {})}
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

