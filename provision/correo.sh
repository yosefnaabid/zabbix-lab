#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
command -v curl >/dev/null 2>&1 || apt-get install -y curl >/dev/null

if ! command -v mailpit >/dev/null 2>&1; then
  echo "[mailpit] instalando Mailpit (binario estable)..."
  curl -fsSL https://raw.githubusercontent.com/axllent/mailpit/develop/install.sh | bash
fi
echo -n "[mailpit] version: "; mailpit version

id mailpit >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin mailpit

cat >/etc/systemd/system/mailpit.service <<'UNIT'
[Unit]
Description=Mailpit (buzon de pruebas del lab)
After=network.target

[Service]
ExecStart=/usr/local/bin/mailpit --smtp 0.0.0.0:1025 --listen 0.0.0.0:8025
Restart=on-failure
User=mailpit

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now mailpit

if systemctl is-active --quiet mailpit; then
  echo "[mailpit] activo  ·  SMTP 127.0.0.1:1025  ·  UI http://localhost:8025 (desde el host)"
else
  echo "[mailpit] ERROR: el servicio no arranco" >&2
  systemctl status mailpit --no-pager || true
  exit 1
fi
