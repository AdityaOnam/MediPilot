# MediPilot backend on AWS

The Python service — **both** FastAPI apps — running on one EC2 instance in
`ap-south-1` (Mumbai). Account `869079195218`.

This is the *serving* deployment. It says nothing about which perception tier is
active; that is `docs/notes/DEPLOYMENT.md`, and it is a separate question.

## What is running

| | |
|---|---|
| Public IP | **13.200.213.243** (Elastic — survives stop/start) |
| Instance | `i-01b91f2b3cdd4aebc`, `t3.micro`, Ubuntu 24.04, 16 GB gp3 |
| Security group | `medipilot-sg` (`sg-02101d20186907a47`) |
| Key pair | `medipilot-key` → `~/.ssh/medipilot-key.pem` |
| Code | `/opt/medipilot`, shallow clone of `origin/main` |
| Venv | `/opt/medipilot/.venv` |

### Both apps are live

The project has two FastAPI apps and booting only one has been mistaken for a
verified backend before. Both run, under systemd, and both are reachable:

| App | Unit | Port | Paths |
|---|---|---|---|
| Orchestrator (what the web app calls) | `medipilot-orchestrator` | 8000 | `/v1/*` — 21 routes |
| Track A/B contract | `medipilot-contract` | 8001 | `/score` `/override` `/queue` `/recheck/{id}` `/surge-status` `/audit/{id}` `/demo/arrival` |

Their paths do not collide, so **nginx on port 80 serves both** with paths
intact. Ports 8000 and 8001 are also open directly, so a URL that worked
against `localhost:8000` works against this host unchanged.

```
http://13.200.213.243/v1/census        →  8000
http://13.200.213.243/queue            →  8001
http://13.200.213.243:8000/v1/census   →  8000  (direct)
```

`/v1/stream` is SSE and is proxied with buffering off and a 24 h read timeout.

## Pointing the web app at it

In `web/.env.local`:

```
NEXT_PUBLIC_MP_SOURCE=live
NEXT_PUBLIC_API_BASE=http://13.200.213.243:8000
```

⚠️ **CORS is hardcoded.** `triage/orchestrator/app.py:53` allows only
`http://localhost:3000` and `http://127.0.0.1:3000`. A frontend served from
anywhere else — Vercel, Amplify, a LAN IP — is refused by the browser until
that list is made configurable. A frontend on **https** additionally cannot
call this **http** backend at all (mixed content); that needs TLS here first.

## Operating it

```bash
ssh -i ~/.ssh/medipilot-key.pem ubuntu@13.200.213.243
```

```bash
sudo systemctl status medipilot-orchestrator medipilot-contract
```

```bash
sudo journalctl -u medipilot-orchestrator -f
```

Deploy a new revision (the instance tracks `origin/main`, not your working tree
— push first):

```bash
cd /opt/medipilot && git pull && .venv/bin/pip install -r backend/requirements.txt && sudo systemctl restart medipilot-orchestrator medipilot-contract
```

## Decisions worth knowing

**t3.micro, not larger.** Two Python processes holding numpy/scipy/sklearn sit
at ~145 MB and ~120 MB RSS; 504 MB of 909 MB used, swap untouched. A 2 GB
swapfile is configured as insurance, not as working memory.

**One instance, never an autoscaling group.** The orchestrator's lifespan hook
bootstraps a `World` and starts a tick loop, and that state is in process
memory. A second instance would be a second, divergent department.

**Not Lambda.** Same reason — plus the sklearn/scipy layer against the 250 MB
unzipped limit.

**`GIT_LFS_SKIP_SMUDGE=1` on clone.** `backend/data/train_set_100k.zip` is a
190 MB LFS object used for training only; the service never opens it.

**`WorkingDirectory` is `backend/`, not the repo root.** `intake`, `model`,
`triage`, `rules` are top-level import roots, and ~20 modules resolve
`config/*.yaml` relative to `__file__` with hardcoded parent counts.

**The Groq key is not in user-data.** User-data is readable from IMDS and via
`ec2:DescribeInstanceAttribute`. The key is written out-of-band over SSH to
`/etc/medipilot.env` (mode 600, read by both units via `EnvironmentFile`).

**SSH is restricted to `14.139.194.115/32`.** If your address changes, the SG
rule has to change with it.

## Rebuilding from scratch

`user-data.sh` is the whole build and is idempotent. To replace the instance,
launch a new one with it as user-data, then move the Elastic IP
(`eipalloc-0dc3e306e429ba287`) across and re-write `/etc/medipilot.env`.

## Cost

t3.micro on-demand ≈ $8/mo, 16 GB gp3 ≈ $1.3/mo, public IPv4 ≈ $3.6/mo — call
it **$13/mo**, less if the account is still inside the 12-month free tier
(t3.micro 750 h/mo and 30 GB EBS are covered; the IPv4 charge is not).

Stop the instance when it is not being demonstrated — compute stops billing,
the Elastic IP does not.

```bash
aws ec2 stop-instances --region ap-south-1 --instance-ids i-01b91f2b3cdd4aebc
```
