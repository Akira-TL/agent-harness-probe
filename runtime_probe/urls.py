#!/usr/bin/env python3
"""Print preauthorized public test URLs without committing the local token."""
from __future__ import annotations
import argparse
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--case', default='sky_probe_a')
a = parser.parse_args()
if not all(c.isascii() and (c.isalnum() or c in '-_') for c in a.case) or len(a.case) > 64:
    raise SystemExit('invalid case label')
secret = (root / '.local' / 'probe-secret.txt').read_text(encoding='utf-8').strip()
base = f'https://babelbeast.com/agent-harness-probe/{secret}'
print('Echo:     ', f'{base}/echo?case={a.case}_echo')
print('Redirect: ', f'{base}/redirect?case={a.case}_redirect')
print('Retry:    ', f'{base}/flaky?case={a.case}_retry&fails=1&code=503')
print('Delay A:  ', f'{base}/delay?case={a.case}_delayA&seconds=3')
print('Delay B:  ', f'{base}/delay?case={a.case}_delayB&seconds=3')
print('Delay C:  ', f'{base}/delay?case={a.case}_delayC&seconds=3')
print('Cache:    ', f'{base}/cache?case={a.case}_cache&policy=public')
