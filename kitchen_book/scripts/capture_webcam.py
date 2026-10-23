"""Windows physical camera capture for live API smoke test (q cancels, space saves)."""
import argparse
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--camera',type=int,default=0);p.add_argument('--output',default='webcam.jpg');a=p.parse_args()
    import cv2
    cap=cv2.VideoCapture(a.camera)
    if not cap.isOpened():raise RuntimeError('카메라를 열지 못했습니다. 브라우저 카메라를 끄거나 --camera 1을 확인하세요.')
    try:
        while True:
            ok,frame=cap.read()
            if not ok:raise RuntimeError('카메라 프레임 수신 실패')
            cv2.imshow('Ingredients: SPACE save / Q cancel',frame)
            key=cv2.waitKey(30)&255
            if key==ord('q'):break
            if key==32:
                # imencode/tofile supports non-ASCII Windows paths.
                ok,buffer=cv2.imencode('.jpg',frame)
                if not ok:raise RuntimeError('JPEG 인코딩 실패')
                Path(a.output).write_bytes(buffer.tobytes());print(a.output);break
    finally:cap.release();cv2.destroyAllWindows()
if __name__=='__main__':main()
