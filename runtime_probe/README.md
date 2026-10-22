# Runtime fingerprint endpoint (read-only)

A bounded, synthetic, local HTTP server for measuring how an external Agent
fetches a public URL. **No shell execution, proxy, filesystem-serving,
request-body uploads, or credential-handling routes are exposed.**

Run locally:

```sh
python3 runtime_probe/server.py --port 18768
```

The server binds **127.0.0.1** only. A 128-bit random access token is generated
locally into `.local/probe-secret.txt` (never commit it). With an intentionally
created temporary HTTPS tunnel, the remote Agent can be asked to open an exact
URL in the following pattern (replace BASE and TOKEN yourself):

```text
BASE/TOKEN/health
BASE/TOKEN/echo?case=echo_a
BASE/TOKEN/redirect?case=redirect_a
BASE/TOKEN/flaky?case=retry_a&fails=1&code=503
BASE/TOKEN/status?case=error_a&code=429
BASE/TOKEN/delay?case=delay_a&seconds=3
BASE/TOKEN/cache?case=cache_a&policy=no-store
BASE/TOKEN/cache?case=cache_b&policy=public
```

`/redirect` uses a same-origin **relative** `Location` target that was not
explicitly provided in the user's prompt, allowing redirect-chain checks.
`/flaky` fails a bounded number of times before succeeding; `/delay` is capped
at six seconds. All routes log only request timing, basic routing/status and a
small set of allowlisted headers. No unbounded remote endpoints exist.

Local-only audit (never exposed over HTTP):

```sh
python3 runtime_probe/report.py --last 30
python3 runtime_probe/report.py --case retry_a
```

Request records live in `.local/probe-events.jsonl` (gitignored). Since tunnel
services and intermediary HTTP clients may cache, rewrite or replay requests,
results are **behavioral evidence, not proof of a particular framework**.

To stop access, terminate the tunnel and the Python server processes.

## HTML visibility checks

`/visibility?case=...` returns synthetic HTML with distinct request-specific
markers in visible text, title, metadata, comments, hidden elements, accessibility
attributes, JSON-LD, and a text node created by JavaScript. The JavaScript only
changes its own page; it does not fetch or send data. Each HTTP response contains
a new request ID. Match external observations to the local event log by ID.

`/visibility-text?case=...` provides a plain-text control response.

Do not manually open the sky-specific test link before capturing service logs.

## Dynamic DOM fetch challenge

`/visibility-live?case=sky_live_trial_a` returns safe HTML with the
`live_dom_token: PENDING` placeholder. After loading, inline JavaScript uses
`fetch()` to retrieve a random, non-sensitive marker from a same-origin
`/visibility-live-token` endpoint and inserts it into a DOM text node. The
final `LIVE_...` marker is generated **only** by the second HTTP request and
cannot be recovered from the initial HTML response. Each HTML request carries
its own ephemeral challenge ID and proof. Challenges expire after five minutes.

Server logs correlate both requests using `response_request_id` and
`linked_html_request_id`, and record synthetic `live_token` values. Response
headers include `Content-Security-Policy` restricting script execution to the
per-response nonce and restricting fetches to the same origin. The script has
no external dependencies, writes no files or storage, sends no credentials,
and performs no off-origin access.

**Interpretation:** Matching a `LIVE_...` marker plus a linked token endpoint
request proves that the second HTTP request happened. Distinguishing true
in-browser JavaScript execution from a tool explicitly following the URL also
requires reviewing `Sec-Fetch-*`, User-Agent and request timing. Even this
is not proof of a particular browser executable or internal Agent framework.
