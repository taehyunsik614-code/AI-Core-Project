"""Run model-free regression/API tests; optional functional DOM tests require Node + jsdom."""
import argparse,os,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dom',action='store_true');a=parser.parse_args()
    commands=[[sys.executable,'-m','unittest','discover','-s',str(ROOT/'source/tests'),'-p','test*.py'],['node',str(ROOT/'source/tests/test_core.cjs')]]
    for cmd in commands:
        code=subprocess.call(cmd)
        if code:return code
    with (ROOT/'docs/demo_server.log').open('w',encoding='utf-8') as log:
        server=subprocess.Popen([sys.executable,str(ROOT/'source/app.py'),'--demo','--port','8765'],stdout=log,stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if server.poll() is not None:raise RuntimeError('8765 서버 시작 실패; docs/demo_server.log 확인')
                try:urlopen('http://127.0.0.1:8765/api/health',timeout=1);break
                except OSError:time.sleep(.1)
            else:raise TimeoutError('서버 준비 시간 초과')
            code=subprocess.call([sys.executable,str(ROOT/'scripts/verify_api.py'),'--url','http://127.0.0.1:8765','--mode','demo','--output',str(ROOT/'docs/api_validation_demo.json')])
            if code:return code
            if a.dom:return subprocess.call(['node',str(ROOT/'source/tests/test_dom.cjs')])
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
    return 0
if __name__=='__main__':raise SystemExit(main())
