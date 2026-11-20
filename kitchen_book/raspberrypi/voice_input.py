"""Local push-to-talk capture and Korean transcription."""
from array import array
import math
import re
import signal
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path


class VoiceInput:
    def __init__(self, alsa, whisper, model):
        from gpiozero import Button
        self.alsa, self.whisper, self.model = alsa, whisper, model
        self.folder = tempfile.TemporaryDirectory(prefix='kitchen-voice-')
        self.wav = Path(self.folder.name) / 'speech.wav'
        self.lock = threading.Lock()
        self.recording = self.worker = None
        self.closed = False
        self.result = dict(session=uuid.uuid4().hex, seq=0, text='', status='준비')
        self.button = Button(23, pull_up=True, bounce_time=.04)
        self.button.when_pressed = self.press
        self.button.when_released = self.release

    def snapshot(self):
        with self.lock:
            return dict(self.result)

    def press(self):
        with self.lock:
            if self.closed or self.recording or self.worker:
                return
            try:
                self.wav.unlink(missing_ok=True)
                self.recording = subprocess.Popen([
                    'arecord', '-q', '-D', self.alsa, '-t', 'wav', '-f', 'S16_LE',
                    '-r', '16000', '-c', '1', '-d', '30', str(self.wav)])
                self.result['status'] = '녹음 중 · 버튼을 떼면 인식합니다'
            except OSError as exc:
                self.result['status'] = '녹음 시작 실패 · ' + str(exc)

    def release(self):
        with self.lock:
            proc = self.recording
            if not proc:
                return
            self.recording = None
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
            self.result['status'] = '한국어 인식 중'
            self.worker = threading.Thread(target=self.transcribe, args=(proc,), daemon=True)
            self.worker.start()

    def transcribe(self, proc):
        text, status = '', '준비'
        try:
            code = proc.wait(timeout=4)
            if code not in (0, 1, -signal.SIGINT) or not self.wav.exists():
                raise RuntimeError('arecord 장치와 마이크 설정을 확인하세요.')
            import wave
            with wave.open(str(self.wav)) as audio:
                samples = audio.readframes(480000)
            pcm = array('h', samples)
            mean = sum(pcm) / max(len(pcm), 1)
            rms = math.sqrt(sum((v - mean) ** 2 for v in pcm) / max(len(pcm), 1))
            if len(pcm) >= 3200 and rms >= 6:
                out = self.wav.with_suffix('.txt')
                out.unlink(missing_ok=True)
                subprocess.run([self.whisper, '-m', self.model, '-l', 'ko', '-f', str(self.wav),
                                '-nt', '-otxt', '-of', str(out.with_suffix(''))],
                               check=True, timeout=120, stdout=subprocess.DEVNULL)
                text = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', out.read_text(encoding='utf-8')).strip()
            if not text:
                status = '말소리가 짧거나 비어 있습니다. 다시 말해 주세요.'
        except Exception as exc:
            status = '음성 인식 실패 · ' + str(exc)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            with self.lock:
                self.result.update(seq=self.result['seq'] + 1, text=text[:300], status=status)
                self.worker = None

    def close(self):
        self.button.close()
        with self.lock:
            self.closed = True
        self.release()
        with self.lock:
            worker = self.worker
        if worker:
            worker.join()
        self.folder.cleanup()
