"""Synthetic browser rendering challenge with no private information.

The final token is created only when a browser requests the same-origin JSON
endpoint. It does not occur in source HTML or deterministic page JavaScript.
"""
from __future__ import annotations

from html import escape
import secrets
import threading
import time

LOCK = threading.RLock()
CHALLENGES: dict[str, dict[str, str | float]] = {}
TTL_SECONDS = 300


def make_page(request_id: str, user_agent_class: str, case: str) -> tuple[bytes, dict[str, str], str]:
    proof = secrets.token_hex(12)
    nonce = secrets.token_urlsafe(18)
    with LOCK:
        now = time.monotonic()
        for key, entry in list(CHALLENGES.items()):
            if now - float(entry['created']) > TTL_SECONDS:
                del CHALLENGES[key]
        CHALLENGES[request_id] = {'proof': proof, 'created': now, 'case': case}
        if len(CHALLENGES) > 256:
            first = next(iter(CHALLENGES))
            CHALLENGES.pop(first, None)

    # Relative URL stays on the same origin; no external resources are used.
    route = f'visibility-live-token?rid={request_id}&proof={proof}'
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Live Rendering Probe</title></head><body>
<h1>Live Rendering Probe</h1>
<p>此页为合成测试数据。样本数量：17。</p>
<p>request_id: <code>{escape(request_id)}</code></p>
<p>client_family: <code>{escape(user_agent_class)}</code></p>
<p id="probe-target">live_dom_token: PENDING</p>
<script nonce="{nonce}">
(async function() {{
  const target = document.getElementById('probe-target');
  try {{
    const response = await fetch('{route}', {{cache: 'no-store', credentials: 'omit'}});
    if (!response.ok) throw Error('HTTP ' + response.status);
    const result = await response.json();
    target.textContent = 'live_dom_token: ' + result.live_dom_token;
  }} catch (error) {{
    target.textContent = 'live_dom_token: UNAVAILABLE';
  }}
}})();
</script>
</body></html>'''
    return page.encode('utf-8'), {'response_request_id': request_id, 'ua_family': user_agent_class,
                                  'live_state': 'page_sent', 'case': case}, nonce


def read_token(rid: str, proof: str) -> tuple[int, dict, dict[str, str]]:
    """Return a fresh test marker for a valid page load, never a credential."""
    with LOCK:
        record = CHALLENGES.get(rid)
        if not record or not secrets.compare_digest(str(record['proof']), proof):
            return 404, {'error': 'invalid challenge'}, {'challenge_state': 'missing'}
        if time.monotonic() - float(record['created']) > TTL_SECONDS:
            CHALLENGES.pop(rid, None)
            return 410, {'error': 'expired challenge'}, {'challenge_state': 'expired'}
        case = str(record['case'])
    marker = 'LIVE_' + secrets.token_hex(12)
    return 200, {'live_dom_token': marker, 'request_id': rid, 'case': case}, {
        'challenge_state': 'issued', 'linked_html_request_id': rid,
        'live_token': marker, 'source_case': case,
    }
