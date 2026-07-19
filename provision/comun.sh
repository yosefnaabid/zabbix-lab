#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "[common] zona horaria y paquetes base"
timedatectl set-timezone Europe/Madrid || true

apt-get update -qq
apt-get install -y -qq curl gnupg ca-certificates locales >/dev/null

sed -i 's/^# *en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/; s/^# *es_ES.UTF-8 UTF-8/es_ES.UTF-8 UTF-8/' /etc/locale.gen
locale-gen >/dev/null

echo "[common] listo"
