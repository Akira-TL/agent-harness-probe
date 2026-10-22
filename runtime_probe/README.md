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
