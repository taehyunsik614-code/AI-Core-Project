"""Read explicit durations only; never invent a cooking time."""
import re
import math

_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*(?:[~～〜–-]\s*(\d+(?:\.\d+)?))?\s*(시간|hours?|hrs?|분|minutes?|mins?|초|seconds?|secs?)(?:\s*(반))?', re.I)

def duration_from_text(text):
    matches = list(_PATTERN.finditer(text))
    if not matches:
        return 0
    total, previous, scale_before = 0, None, 0
    for match in matches:
        unit = match[3].lower()
        scale = 3600 if unit == '시간' or unit.startswith(('hour', 'hr')) else 60 if unit == '분' or unit.startswith('min') else 1
        value = float(match[2] or match[1]) * scale + (scale / 2 if match[4] else 0)
        if previous is None:
            total = value
        else:
            gap = text[previous.end():match.start()].strip()
            if gap in ('~', '～', '〜', '–', '-'):
                total = max(total, value)
            elif not gap and scale < scale_before:
                total += value
            else:
                break  # Distinct actions/alternatives are not summed.
        previous, scale_before = match, scale
    return min(86400, max(0, math.floor(total + 0.5)))
