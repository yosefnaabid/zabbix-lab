#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

ZBX_SERVER_IP="${1:-192.168.56.30}"
ZBX_MAJOR="6.0"
ZBX_RELEASE_DEB="zabbix-release_6.0-10+debian12_all.deb"
ZBX_RELEASE_URL="https://repo.zabbix.com/zabbix/${ZBX_MAJOR}/debian/pool/main/z/zabbix-release/${ZBX_RELEASE_DEB}"

echo "[agent] repositorio + zabbix-agent2 (server = ${ZBX_SERVER_IP})"
if ! dpkg -l | grep -q '^ii  zabbix-release'; then
  if ! curl -fsSL -o "/tmp/${ZBX_RELEASE_DEB}" "${ZBX_RELEASE_URL}"; then
    echo "AVISO: No se pudo descargar ${ZBX_RELEASE_DEB} - mira el nombre actual en"
    echo "    https://repo.zabbix.com/zabbix/6.0/debian/pool/main/z/zabbix-release/"
    exit 1
  fi
  dpkg -i "/tmp/${ZBX_RELEASE_DEB}"
  apt-get update -qq
fi

apt-get install -y -qq zabbix-agent2 >/dev/null

sed -i "s/^Server=.*/Server=${ZBX_SERVER_IP}/"             /etc/zabbix/zabbix_agent2.conf
sed -i "s/^ServerActive=.*/ServerActive=${ZBX_SERVER_IP}/" /etc/zabbix/zabbix_agent2.conf
sed -i "s/^Hostname=.*/Hostname=zbx-agent01/"              /etc/zabbix/zabbix_agent2.conf

systemctl restart zabbix-agent2
systemctl enable  zabbix-agent2 >/dev/null 2>&1

echo "[agent] zabbix-agent2 activo, apuntando a ${ZBX_SERVER_IP}"
