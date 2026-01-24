# Cold-Start Bootstrap — WHO_AM_I.md

## Identity

**You are Claude Code running on Air** (MacBook Air M3).

| Agent | Role | Capabilities |
|-------|------|--------------|
| Claude Code (you) | Executor | Filesystem, bash, git, Playwright, SSH to Pro |
| Claude Chat | Planner/Reviewer | Browser GUI (Claude in Chrome), Desktop Commander, visual verification |
| Pro | Remote executor | Chrome with CDP, GPU, heavier compute |

**Anti-amnesia:** After `/clear`, you forget everything. Run this bootstrap FIRST.

---

## Environment

| Item | Value |
|------|-------|
| Shell | zsh |
| Python | `python3` (use `./tools/py` wrapper) |
| Package manager | brew |
| Brain repo | `$HOME/projects/todo-exec` |
| Tooling repo | `$HOME/projects/eval-ops-platform` |
| Registry | `$HOME/projects/todo-exec/config/repo_registry.env` |

---

## Bootstrap Sequence

Run each step, paste output to confirm pass.

### Step A: Local Environment Sanity

```bash
echo "=== A: Environment ===" && \
python3 --version && \
which git && \
echo "PASS: local env"
```

### Step B: Network Check

```bash
echo "=== B: Network ===" && \
networksetup -getairportnetwork en0 2>/dev/null || echo "No WiFi adapter" && \
curl -s --max-time 3 https://api.ipify.org && echo && \
echo "PASS: network"
```

### Step C: Tailscale Check

```bash
echo "=== C: Tailscale ===" && \
tailscale status --peers=false 2>/dev/null || echo "Tailscale not running" && \
echo "PASS: tailscale"
```

### Step D: Pro Reachability

```bash
echo "=== D: Pro Reachability ===" && \
source "$HOME/projects/todo-exec/config/repo_registry.env" && \
ssh -o ConnectTimeout=3 "$PRO_HOST" 'echo "Pro reached: $(hostname)"' && \
echo "PASS: pro reachable"
```

### Step E: Pro State (Chrome, CDP)

```bash
echo "=== E: Pro Chrome/CDP ===" && \
source "$HOME/projects/todo-exec/config/repo_registry.env" && \
ssh "$PRO_HOST" 'lsof -nP -iTCP:9222 -sTCP:LISTEN 2>/dev/null | head -2 || echo "CDP not listening"' && \
ssh "$PRO_HOST" 'curl -s --max-time 2 http://127.0.0.1:9222/json/version | head -1 || echo "CDP not responding"' && \
echo "PASS: pro chrome state checked"
```

### Step F: Local Tunnel Check

```bash
echo "=== F: Local Tunnel ===" && \
lsof -nP -iTCP:9222 -sTCP:LISTEN 2>/dev/null && echo "Local 9222 listening" || echo "No local tunnel" && \
echo "PASS: tunnel checked"
```

### Step G: Repo State Check

```bash
echo "=== G: Repo State ===" && \
"$HOME/projects/eval-ops-platform/tools/repo_state.sh" && \
echo "PASS: repo state"
```

---

## After Bootstrap

Print:
```
BOOTSTRAP COMPLETE
- Local: <hostname>
- Pro: <reachable|unreachable>
- CDP: <listening|not listening>
- Repos: <clean|dirty>
```

Then proceed with handoff execution.

---

## Quick Reference

| Task | Command |
|------|---------|
| SSH to Pro | `ssh hidemiasakura@hidemis-macbook-pro-2` |
| Check CDP | `curl -s http://127.0.0.1:9222/json/version` |
| Run Python | `./tools/py script.py` |
| Repo state | `./tools/repo_state.sh` |
