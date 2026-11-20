"""Measure the two actual VLM pipelines on the same JPEG with user labels."""
import argparse
import base64
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
from ai import KitchenAI

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('photo', type=Path)
    parser.add_argument('--truth', required=True, help='실제 재료를 쉼표로 구분')
    args = parser.parse_args()
    expected = {s.strip() for s in args.truth.split(',') if s.strip()}
    image = 'data:image/jpeg;base64,' + base64.b64encode(args.photo.read_bytes()).decode()
    ai = KitchenAI()
    for mode in ('classic','multi'):
        result = ai.run('ingredients',dict(image=image,scan=mode))
        predicted = set(result['ingredients'])
        extra, missing = sorted(predicted-expected), sorted(expected-predicted)
        print(json.dumps(dict(mode=mode,ingredients=sorted(predicted),오인식=extra,누락=missing,
                              오인식수=len(extra),누락수=len(missing),확인필요=result['uncertain']),ensure_ascii=False))
if __name__ == '__main__':
    main()
