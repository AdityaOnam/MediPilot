#!/bin/bash
# MediPilot backend bootstrap — runs once, as root, on first boot.
# Log: /var/log/medipilot-setup.log
set -euxo pipefail
exec > >(tee -a /var/log/medipilot-setup.log) 2>&1

APP_DIR=/opt/medipilot
REPO=https://github.com/AdityaOnam/MediPilot.git

# --- swap ------------------------------------------------------------------
# t3.micro is 1 GB and two Python processes each hold numpy/scipy/sklearn.
# Swap is the difference between a tight box and an OOM-killed orchestrator.
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- packages --------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv python3-pip git nginx curl ffmpeg libsndfile1

# --- code ------------------------------------------------------------------
# GIT_LFS_SKIP_SMUDGE: backend/data/train_set_100k.zip is a 190 MB LFS object
# used for training only. The service never reads it; leave the pointer.
if [ ! -d "$APP_DIR/.git" ]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 "$REPO" "$APP_DIR"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

# --- runtime env -----------------------------------------------------------
# Secrets are NOT baked into user-data (user-data is readable via IMDS and
# ec2:DescribeInstanceAttribute). This file is written out-of-band over SSH.
if [ ! -f /etc/medipilot.env ]; then
  cat > /etc/medipilot.env <<'ENVEOF'
# GROQ_API_KEY=            # set out-of-band; absent => RuleBasedStructurer floor
MEDIPILOT_STRUCTURER=groq,rules
MEDIPILOT_ASR_BACKEND=groq,off
ENVEOF
  chmod 600 /etc/medipilot.env
fi

chown -R ubuntu:ubuntu "$APP_DIR"

# --- services --------------------------------------------------------------
# Both apps run. Booting only the orchestrator and calling the backend verified
# is a mistake this project has already made once.
#
# WorkingDirectory is backend/, not the repo root: intake/, model/, triage/ are
# top-level import roots, and ~20 modules resolve config/*.yaml relative to
# __file__ with hardcoded parent counts.
write_unit () {
  cat > "/etc/systemd/system/$1.service" <<UNITEOF
[Unit]
Description=$2
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=/etc/medipilot.env
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn $3 --host 0.0.0.0 --port $4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNITEOF
}

write_unit medipilot-orchestrator "MediPilot orchestrator (/v1/*)" "triage.orchestrator.app:app" 8000
write_unit medipilot-contract     "MediPilot Track A/B contract API" "triage.api:app" 8001

systemctl daemon-reload
systemctl enable --now medipilot-orchestrator medipilot-contract

# --- nginx -----------------------------------------------------------------
# One origin serves both apps. Their paths do not collide: the orchestrator is
# entirely under /v1/*, the contract app owns seven fixed top-level paths.
cat > /etc/nginx/conf.d/proxy_common.conf <<'NGXEOF'
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
NGXEOF

cat > /etc/nginx/sites-available/medipilot <<'NGXEOF'
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 32m;

    # --- orchestrator (what the Next.js app calls) ---
    location /v1/stream {
        proxy_pass http://127.0.0.1:8000;
        include /etc/nginx/conf.d/proxy_common.conf;
        # SSE: no buffering, no early close.
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 24h;
    }
    location /v1/ {
        proxy_pass http://127.0.0.1:8000;
        include /etc/nginx/conf.d/proxy_common.conf;
        proxy_read_timeout 120s;
    }

    # --- Track A/B contract app ---
    location /score        { proxy_pass http://127.0.0.1:8001; include /etc/nginx/conf.d/proxy_common.conf; }
    location /override     { proxy_pass http://127.0.0.1:8001; include /etc/nginx/conf.d/proxy_common.conf; }
    location /queue        { proxy_pass http://127.0.0.1:8001; include /etc/nginx/conf.d/proxy_common.conf; }
    location /recheck/     { proxy_pass http://127.0.0.1:8001; include /etc/nginx/conf.d/proxy_common.conf; }
    location /surge-status { proxy_pass http://127.0.0.1:8001; include /etc/nginx/conf.d/proxy_common.conf; }
    location /audit/       { proxy_pass http://127.0.0.1:8001; include /etc/nginx/conf.d/proxy_common.conf; }
    location /demo/        { proxy_pass http://127.0.0.1:8001; include /etc/nginx/conf.d/proxy_common.conf; }

    # --- everything else (/, /docs, /openapi.json) -> orchestrator ---
    location / {
        proxy_pass http://127.0.0.1:8000;
        include /etc/nginx/conf.d/proxy_common.conf;
    }
}
NGXEOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/medipilot /etc/nginx/sites-enabled/medipilot
nginx -t
systemctl restart nginx

touch /var/lib/medipilot-bootstrap-done
echo "MEDIPILOT BOOTSTRAP COMPLETE"
