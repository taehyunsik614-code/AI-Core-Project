"""PC relay to one explicitly configured kitchen device."""
import base64
import http.client
import ipaddress
import json

def device_ip(value):
    return str(ipaddress.IPv4Address(value))

def state(data):
    page, total, seconds = (data.get(k) for k in ('page', 'total', 'seconds'))
    mode = data.get('mode')
    if (any(type(n) is not int for n in (page, total, seconds))
            or not 0 <= page <= total <= 16 or not 0 <= seconds <= 86400
            or mode not in ('step', 'running', 'finished', 'paused', 'idle')):
        raise ValueError('기기 상태 값 오류')
    value = dict(page=page, total=total, seconds=seconds, mode=mode)
    if 'stage' in data:
        if type(data['stage']) is not int or not 1 <= data['stage'] <= 4:
            raise ValueError('잘못된 화면 단계')
        value['stage'] = data['stage']
    if 'bitmap' in data:
        encoded = data['bitmap']
        if not isinstance(encoded,str) or len(encoded)!=1368 or len(base64.b64decode(encoded,validate=True))!=1024:
            raise ValueError('OLED 화면 크기 오류')
        value['bitmap'] = encoded
    return value

def relay(ip, path, payload=None, timeout=4):
    if not ip:
        raise ConnectionError('Pi 주소를 --device 옵션으로 지정하세요.')
    conn = http.client.HTTPConnection(ip, 8080, timeout=timeout)
    try:
        body = None if payload is None else json.dumps(payload).encode()
        conn.request('GET' if body is None else 'POST', path, body, {'Content-Type':'application/json'})
        response = conn.getresponse()
        if response.status != 200:
            try:
                message = json.loads(response.read(4096)).get('error')
            except (ValueError, AttributeError):
                message = None
            raise ConnectionError(message or 'Pi 장치 응답 오류')
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ConnectionError('Pi 응답 크기 초과')
        return raw
    finally:
        conn.close()
