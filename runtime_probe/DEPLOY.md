# `babelbeast.com` deployment (local workstation)

The probe is a read-only Python stdlib service binding only
`127.0.0.1:18768`. An Nginx location under an existing HTTPS site proxies
`https://babelbeast.com/agent-harness-probe/` to that localhost port.

Source and local runtime state: `~/Downloads/agent-harness-probe/`.

- Public route source: `runtime_probe/nginx-location.conf`.
- Current live Nginx server config:
  `/home/Akira/Work/PeTalk-renew/infra/gateway/sites/main.conf`.
  Its **only change for this probe** is one marker comment plus one `include`
  placed immediately above the preexisting `# 主应用代理` anchor; existing
  changes in that file are preserved.
- The exact pre-probe version of the config is backed up locally at
  `.local/nginx-main.conf.before`; this directory is gitignored.
- Random 128-bit path token: `.local/probe-secret.txt` (`0600`).
- HTTP timing/header audit log: `.local/probe-events.jsonl` (`0600`).

## Start or resume

The HTTP process is currently a **transient systemd user unit** named
`agent-harness-probe.service`. It is not enabled for boot. It is intentionally
not an always-on production application.

```sh
systemctl --user status agent-harness-probe.service
systemctl --user restart agent-harness-probe.service
sudo nginx -t
sudo systemctl reload nginx
```

If the transient user unit no longer exists after a reboot, recreate it:

```sh
systemd-run --user --unit=agent-harness-probe \
  --description='Controlled Agent Harness HTTP Fingerprint Test' \
  --property=WorkingDirectory="$HOME/Downloads/agent-harness-probe" \
  --property=Restart=on-failure --property=RestartSec=2 \
  /usr/bin/python3 "$HOME/Downloads/agent-harness-probe/runtime_probe/server.py" --port 18768
```

## Client tests

Obtain the unique endpoint path locally (do not commit or publicly publish
this token; the remote Agent needs only selected test URLs):

```sh
TOKEN=$(cat .local/probe-secret.txt)
BASE="https://babelbeast.com/agent-harness-probe/$TOKEN"
curl -fsS "$BASE/health"
curl -fsSL "$BASE/redirect?case=manual_redirect_a"
curl -fsS "$BASE/echo?case=manual_echo_a"
```

To report accesses from the external Agent:

```sh
python3 runtime_probe/report.py --last 40
python3 runtime_probe/report.py --case sky_redirect_a
```

Endpoints: `health`, `echo`, `redirect`, `flaky`, `status`, `delay`, `cache`.
All are GET/HEAD only. All test responses are synthetic. `flaky` fails at most
three times, `delay` is capped at six seconds, and `redirect` points only to
a same-origin relative `echo` path. HTTP/JSON result status is always
observable independently of the remote Agent's report.

## Rollback safely

1. Stop the test service: `systemctl --user stop agent-harness-probe.service`.
2. In the **existing** Nginx `main.conf`, delete **only** the probe marker
   comment and its following `include` line (plus one blank line). Do not
   overwrite the file with the backup if other agents may have edited it.
3. Run `sudo nginx -t` and **only if it succeeds**, run
   `sudo systemctl reload nginx`.
4. Optionally archive or delete the local `.local` logs and secret after all
   testing. Do not delete them while still evaluating a running test.

Do not use `git restore` on PeTalk's `main.conf`: that file already contained
uncommitted changes before this probe was added.
