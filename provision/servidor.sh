#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

ZBX_MAJOR="6.0"
ZBX_RELEASE_DEB="zabbix-release_6.0-10+debian12_all.deb"
ZBX_RELEASE_URL="https://repo.zabbix.com/zabbix/${ZBX_MAJOR}/debian/pool/main/z/zabbix-release/${ZBX_RELEASE_DEB}"

DB_NAME="zabbix"
DB_USER="zabbix"
DB_PASS="zabbix"

echo "[zbx] 1/6 · repositorio oficial de Zabbix"
if ! dpkg -l | grep -q '^ii  zabbix-release'; then
  if ! curl -fsSL -o "/tmp/${ZBX_RELEASE_DEB}" "${ZBX_RELEASE_URL}"; then
    echo "AVISO: No se pudo descargar ${ZBX_RELEASE_DEB}."
    echo "    Mira el nombre actual en:"
    echo "    https://repo.zabbix.com/zabbix/6.0/debian/pool/main/z/zabbix-release/"
    echo "    y actualiza ZBX_RELEASE_DEB en provision/servidor.sh y agente.sh."
    exit 1
  fi
  dpkg -i "/tmp/${ZBX_RELEASE_DEB}"
  apt-get update -qq
fi

echo "[zbx] 2/6 · instalando paquetes (puede tardar)"
apt-get install -y -qq postgresql php8.2-pgsql \
  zabbix-server-pgsql zabbix-frontend-php zabbix-nginx-conf \
  zabbix-sql-scripts zabbix-agent2 zabbix-get >/dev/null

echo "[zbx] 3/6 · base de datos PostgreSQL"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';"
fi
if ! sudo -u postgres psql -lqt | cut -d'|' -f1 | grep -qw "${DB_NAME}"; then
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
  echo "[zbx]   importando el esquema inicial (~1 min)…"
  zcat /usr/share/zabbix-sql-scripts/postgresql/server.sql.gz \
    | sudo -u "${DB_USER}" psql "${DB_NAME}" >/dev/null
fi

echo "[zbx] 4/6 · zabbix_server.conf"
sed -i "s/^# DBPassword=.*/DBPassword=${DB_PASS}/" /etc/zabbix/zabbix_server.conf

echo "[zbx] 5/6 · frontend nginx + php-fpm"
PHP_POOL="$(find /etc/php -path '*/fpm/pool.d/*zabbix*' 2>/dev/null | head -n1 || true)"
if [ -n "${PHP_POOL}" ] && ! grep -q '^php_value\[date.timezone\]' "${PHP_POOL}"; then
  echo 'php_value[date.timezone] = Europe/Madrid' >> "${PHP_POOL}"
fi
sed -i -E 's|^#\s*listen\s+8080;|        listen 80;|'                        /etc/zabbix/nginx.conf
sed -i -E 's|^#\s*server_name\s+example\.com;|        server_name zbx-server;|' /etc/zabbix/nginx.conf
rm -f /etc/nginx/sites-enabled/default

ZBX_WEB_CONF="/etc/zabbix/web/zabbix.conf.php"
mkdir -p /etc/zabbix/web
if [ ! -f "${ZBX_WEB_CONF}" ]; then
  cat > "${ZBX_WEB_CONF}" <<PHP
<?php
// Configuración del frontend generada por provisioning (sin asistente web).
\$DB['TYPE']            = 'POSTGRESQL';
\$DB['SERVER']          = '127.0.0.1';
\$DB['PORT']            = '5432';
\$DB['DATABASE']        = '${DB_NAME}';
\$DB['USER']            = '${DB_USER}';
\$DB['PASSWORD']        = '${DB_PASS}';
\$DB['SCHEMA']          = '';
\$DB['ENCRYPTION']      = false;
\$DB['KEY_FILE']        = '';
\$DB['CERT_FILE']       = '';
\$DB['CA_FILE']         = '';
\$DB['VERIFY_HOST']     = false;
\$DB['CIPHER_LIST']     = '';
\$DB['VAULT_URL']       = '';
\$DB['VAULT_DB_PATH']   = '';
\$DB['VAULT_TOKEN']     = '';
\$DB['DOUBLE_IEEE754']  = true;
\$ZBX_SERVER            = '127.0.0.1';
\$ZBX_SERVER_PORT       = '10051';
\$ZBX_SERVER_NAME       = 'zabbix-lab';
\$IMAGE_FORMAT_DEFAULT  = IMAGE_FORMAT_PNG;
PHP
  chown www-data:www-data "${ZBX_WEB_CONF}"
  chmod 640 "${ZBX_WEB_CONF}"
fi

echo "[zbx] 6/6 · arrancando servicios"
systemctl restart zabbix-server zabbix-agent2 nginx php8.2-fpm
systemctl enable  zabbix-server zabbix-agent2 nginx php8.2-fpm >/dev/null 2>&1

echo ""
echo "[zbx] Zabbix desplegado y frontend configurado (sin asistente web)."
echo "       Frontend:  http://localhost:8080"
echo "       Login:     Admin / zabbix"
