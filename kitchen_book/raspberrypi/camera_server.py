"""Kitchen camera and outputs. Run on a Raspberry Pi 5 on the kitchen LAN."""
import argparse
import base64
from PIL import Image
import io
import json
import zlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
from device import state

# Pre-rendered Korean stage headers for devices without Hangul fonts.
HEADERS = [Image.frombytes('1',(128,18),zlib.decompress(base64.b64decode(data))) for data in (
    'eJxjYCAI2A4wMPIwKEA4/GwMbMf/8L+xgfLl5zH+O/6Hsaf+AYQv2caQdoCH+VwylC8B5B//w/fOGape4hhD+jGgeekPkPn8b+wR/G/H/zDwSCjA9QP57H9gjpFsY5x3UICBRx6qnn9+IxuIL5EA5cs3sJ3/x/5HQAHh/vP/2BhkHiA8dICB/Q//AcIeBwEA9X0wFw==',
    'eJxjYMAAbAcYmHkYEiAcfn4GtuN/+N/YQPny8xv/Hf/DwFMH5UtObEg7wMN+JhnKl2hsSDv+h8cPzj/YkH6MgScPzj/MAOSzn6lD8L8d/8PMAzNfog3El/8Ds1+yh3HeQQEGHgmYe+YfZDsowP5HAupYfvkDbOf/AeWR3A/iy39ACBxgQOWTAgCCYjAk',
    'eJxjYCAI2A4wMByQUIBw+PkZ2I4h8eXnN347xsD+px7Kl2xs3IYsLwHhP5B9AOUfZ9x3/A/jB2T+AQZ+OzOY+oON2w4wsLAkI+k//4//nwPM/ImN3w5L8P+Du2d/A9thCaB9DAj3IfNB7gfx5T8gBND5+AAAmHIvbg==',
    'eJxjYCAC8ABxAoTJz9xgB+Tz1EP58u0N3/nPMPbA+JKtDQcbgHyJAghforehEcSXgfFPNhzsB/LNoOolbjYc7uFh7imH8f8fqOcB8pNh/P0Hknl42M7AnCLZ2JDM/4evxv4B1D1gPo8OnM/Y+P8A0H0w9zIwMKLxwf5B5eMBAMz5K9c=',
)]

class Outputs:
    def __init__(self, oled, running, done, draw):
        self.oled, self.running, self.done, self.draw = oled, running, done, draw
        self.lock = threading.Lock()
        self.previous = None

    def update(self, value):
        with self.lock:
            mode = value['mode']
            seconds = value['seconds']
            lines = [f"STEP {value['page']}/{value['total']}" if value['page'] else 'PREP']
            if mode in ('running', 'paused'):
                lines.append(f"{'TIMER' if mode == 'running' else 'PAUSE'} {seconds//60:02}:{seconds%60:02}")
            elif mode == 'finished':
                lines.append('TIME UP')
            elif mode == 'idle':
                lines = [] if 'stage' in value else ['KITCHEN READY']
            with self.draw(self.oled) as screen:
                if "bitmap" in value:
                    frame = Image.frombytes("1",(128,64),base64.b64decode(value["bitmap"]))
                    screen.bitmap((0,0),frame,fill="white")
                else:
                    for i, line in enumerate(lines):
                        screen.text((3, 4 + 19*i), line, fill='white')
                if 'stage' in value:
                    stage = value['stage']
                    screen.rectangle((0,0,127,17),fill='black')
                    screen.bitmap((0,0),HEADERS[stage-1],fill='white')
                    if stage == 4 and value['page']:
                        screen.rectangle((0,18,127,32),fill='black')
                        screen.text((3,18),f"{value['page']}/{value['total']}",fill='white')
            self.running.value = mode == 'running'
            if mode == 'finished' and self.previous != 'finished':
                self.done.blink(on_time=.3, off_time=.3, n=3, background=True)
            self.previous = mode

class Frames:
    def __init__(self, camera):
        self.camera = camera
        self.condition = threading.Condition()
        self.latest = None
        self.timestamp = 0

    def capture(self):
        while True:
            try:
                buf = io.BytesIO()
                self.camera.capture_file(buf, format='jpeg')
                with self.condition:
                    self.latest, self.timestamp = buf.getvalue(), time.monotonic()
                    self.condition.notify_all()
                time.sleep(.06)
            except Exception as exc:
                print('Camera:', exc, flush=True)
                time.sleep(1)

    def get(self, last=0):
        with self.condition:
            if not self.condition.wait_for(lambda: self.timestamp > last and time.monotonic()-self.timestamp < 2, timeout=2):
                raise TimeoutError('Camera unavailable')
            return self.timestamp, self.latest

def handler(frames, outputs, voice=None, selector=None):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, raw, mime):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == '/voice-text':
                data = dict(voice.snapshot(), text_only=selector is None) if voice else {'error':'Pi 서버를 --voice 옵션으로 실행하세요.'}
                return self.reply(200 if voice else 503,json.dumps(data).encode(),'application/json')
            if self.path not in ('/frame.jpg','/stream.mjpg'):
                return self.send_error(404)
            try:
                stamp, frame = frames.get()
            except TimeoutError:
                return self.send_error(503)
            if self.path == '/frame.jpg':
                return self.reply(200,frame,'image/jpeg')
            self.send_response(200)
            self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(frame)).encode()+b'\r\n\r\n'+frame+b'\r\n')
                    stamp,frame = frames.get(stamp)
            except (OSError, TimeoutError):
                return

        def do_POST(self):
            if self.path == '/llm-infer' and selector:
                try:
                    size = int(self.headers.get('Content-Length', 0))
                    if not 0 < size <= 32768:
                        raise ValueError('요청 크기 오류')
                    data = json.loads(self.rfile.read(size))
                    answer = selector.infer(data)
                except Exception as exc:
                    return self.reply(503,json.dumps({'error':'Pi 명령 해석 실패 · '+str(exc)}).encode(),'application/json')
                return self.reply(200,json.dumps(answer).encode(),'application/json')
            if self.path != '/state':
                return self.send_error(404)
            try:
                n = int(self.headers.get('Content-Length', 0))
                if not 0 < n <= 2048:
                    raise ValueError()
                payload = json.loads(self.rfile.read(n))
                if not isinstance(payload, dict):
                    raise ValueError()
                value = state(payload)
                outputs.update(value)
            except (ValueError, TypeError):
                return self.send_error(400)
            self.reply(200,json.dumps(dict(ok=True,stage=value.get('stage'),page=value['page'])).encode(),'application/json')
    return Handler

def main():
    from picamera2 import Picamera2
    from gpiozero import LED
    from luma.core.interface.serial import spi
    from luma.core.render import canvas
    from luma.oled import device
    parser = argparse.ArgumentParser()
    parser.add_argument('--oled', choices=['ssd1306','sh1106'],default='ssd1306')
    root = Path(__file__).resolve().parents[1]
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--voice', action='store_true')
    modes.add_argument('--voice-text-only', action='store_true')
    parser.add_argument('--alsa', default='plughw:0,0')
    parser.add_argument('--whisper', default=str(Path.home()/'whisper.cpp/build/bin/whisper-cli'))
    parser.add_argument('--stt-model', default=str(Path.home()/'whisper.cpp/models/ggml-base.bin'))
    parser.add_argument('--tool-model', default=str(root/'models/Qwen3-1.7B-Q4_K_M.gguf'))
    args = parser.parse_args()
    voice = selector = None
    if args.voice or args.voice_text_only:
        from voice_input import VoiceInput
        paths = [args.whisper, args.stt_model]
        if args.voice:
            paths.append(args.tool_model)
        for path in paths:
            if not Path(path).is_file():
                parser.error('파일을 찾을 수 없습니다 · ' + path)
        voice = VoiceInput(args.alsa, args.whisper, args.stt_model)
        if args.voice:
            from voice_llm import ToolSelector
            selector = ToolSelector(args.tool_model)
    oled = getattr(device,args.oled)(spi(port=0,device=0,gpio_DC=25,gpio_RST=22))
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={'size':(1280,720),'format':'RGB888'}))
    camera.start()
    frames = Frames(camera)
    outputs = Outputs(oled,LED(17),LED(27),canvas)
    outputs.update(state(dict(mode='idle',stage=1,page=0,total=0,seconds=0)))
    threading.Thread(target=frames.capture,daemon=True).start()
    with ThreadingHTTPServer(('',8080),handler(frames,outputs,voice,selector)) as server:
        try:
            server.serve_forever()
        finally:
            if voice:
                voice.close()
            camera.stop()
            outputs.running.close()
            outputs.done.close()
            oled.cleanup()

if __name__ == '__main__':
    main()
