"""Non-invasive HTML-vs-rendered-content visibility probe.

All values are synthetic. Scripts modify the current DOM only; no network calls,
remote resources, credential access, storage, or other side effects.
"""
from __future__ import annotations

from html import escape
import json
import secrets


def ua_family(user_agent: str) -> str:
    ua = user_agent.lower()
    if 'community-ops-agent' in ua:
        return 'COMMUNITY_READER'
    if 'headlesschrome' in ua:
        return 'HEADLESS_CHROME'
    if 'firefox/' in ua:
        return 'FIREFOX'
    if 'android' in ua:
        return 'ANDROID'
    if 'curl/' in ua:
        return 'CURL'
    return 'OTHER'


def render_html(request_id: str, user_agent: str, case: str) -> tuple[bytes, dict[str, str]]:
    """Return distinct content surfaces and independently logged markers."""
    family = ua_family(user_agent)
    csp_nonce = secrets.token_urlsafe(18)
    layers = ('TITLE','META','JSONLD','VISIBLE','ARIA','CSS_HIDDEN','HTML_HIDDEN','TEMPLATE','NOSCRIPT','COMMENT','DOM_OK')
    independent_tokens = {prefix: secrets.token_hex(8) for prefix in layers}
    v = lambda prefix: f'{prefix}_{independent_tokens[prefix]}'
    # The full DOM-only marker is generated from numeric character codes;
    # it is not present as an intact string in the original HTML source.
    code = ','.join(str(ord(char)) for char in v('DOM_OK'))
    doc = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{v('TITLE')}</title>
<meta name="visibility-probe" content="{v('META')}">
<script type="application/ld+json">{json.dumps({'@context':'https://schema.org','@type':'Dataset','identifier':v('JSONLD')},ensure_ascii=False)}</script>
<style nonce="{csp_nonce}">.probe-hidden{{display:none!important}}</style>
</head>
<body data-request-id="{escape(request_id)}">
<main>
<h1>Browser-to-Model Visibility Probe</h1>
<p>此页面是虚构的无害测试资料，不包含任何内部系统信息。</p>
<p>项目名称：NEREID-46</p>
<p>采样深度：1840 米</p>
<p>水体温度：3.6 摄氏度</p>
<p>样本数量：17</p>
<p>request_id: <code>{escape(request_id)}</code></p>
<p>client_family: <code>{family}</code></p>
<p>visible_token: <code>{v('VISIBLE')}</code></p>
<section aria-label="{v('ARIA')}">无额外观测数值</section>
<div class="probe-hidden">css_hidden_token: {v('CSS_HIDDEN')}</div>
<div hidden>html_hidden_token: {v('HTML_HIDDEN')}</div>
<template>template_token: {v('TEMPLATE')}</template>
<noscript>noscript_token: {v('NOSCRIPT')}</noscript>
<p id="js-slot"></p>
</main>
<!-- html_comment_token: {v('COMMENT')} -->
<script nonce="{csp_nonce}">document.addEventListener('DOMContentLoaded', () => {{const p=document.getElementById('js-slot');p.textContent='dom_rendered_token: '+String.fromCharCode({code});}});</script>
</body>
</html>
'''
    metadata = {
        'response_request_id': request_id,
        'ua_family': family,
        **{prefix.lower() + '_marker': v(prefix) for prefix in layers},
        'expected_dom_marker': v('DOM_OK'),
        'case': case,
        'csp_nonce': csp_nonce,
    }
    return doc.encode('utf-8'), metadata


def render_plain(request_id: str, user_agent: str) -> tuple[bytes, dict[str,str]]:
    family = ua_family(user_agent)
    body = '\n'.join([
        'Browser-to-Model Visibility Probe (plain-text control)',
        '项目名称：NEREID-46',
        '采样深度：1840 米',
        '水体温度：3.6 摄氏度',
        '样本数量：17',
        f'request_id: {request_id}',
        f'client_family: {family}',
        f'visible_token: VISIBLE_{request_id}',
        '',
    ]).encode('utf-8')
    return body, {'response_request_id':request_id,'ua_family':family,'visible_marker':f'VISIBLE_{request_id}'}
