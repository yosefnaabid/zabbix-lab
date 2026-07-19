#!/usr/bin/env python3

import json
import os
import sys
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ZBX_URL  = os.environ.get("ZBX_URL",  "http://localhost:8080")
ZBX_USER = os.environ.get("ZBX_USER", "Admin")
ZBX_PASS = os.environ.get("ZBX_PASS", "zabbix")
API = ZBX_URL.rstrip("/") + "/api_jsonrpc.php"

SERVER_HOST = os.environ.get("ZBX_SERVER_HOST", "Zabbix server")

def _check(key, item, value_type, delay, desc, expr, priority):
    return {"key": key, "item": item, "value_type": value_type, "delay": delay,
            "desc": desc, "expr": expr, "priority": priority}

PING = _check(
    "agent.ping", "Disponibilidad del agente (ping)", 3, "30s",
    "El agente de {HOST.NAME} no responde",
    "nodata(/{H}/agent.ping,90s)=1", 4)

RESOURCES = [
    _check("vfs.fs.size[/,pused]", "Uso del disco / (%)", 0, "1m",
           "Disco / por encima del 85% en {HOST.NAME}",
           "last(/{H}/vfs.fs.size[/,pused])>85", 2),
    _check("system.cpu.load[percpu,avg1]", "Carga de CPU por nucleo (avg1)", 0, "1m",
           "Carga de CPU sostenida (>2 por nucleo, 5 min) en {HOST.NAME}",
           "avg(/{H}/system.cpu.load[percpu,avg1],5m)>2", 3),
    _check("vm.memory.size[pavailable]", "Memoria disponible (%)", 0, "1m",
           "Memoria disponible por debajo del 10% en {HOST.NAME}",
           "last(/{H}/vm.memory.size[pavailable])<10", 3),
]

POSTGRES = _check(
    "net.tcp.service[tcp,127.0.0.1,5432]", "PostgreSQL escuchando (5432)", 3, "30s",
    "PostgreSQL no responde en el puerto 5432 en {HOST.NAME}",
    "max(/{H}/net.tcp.service[tcp,127.0.0.1,5432],#3)=0", 4)

_req_id = 0
_auth = None

def call(method, params, needs_auth=True):
    global _req_id
    _req_id += 1
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": _req_id}
    if needs_auth and _auth:
        payload["auth"] = _auth
    resp = requests.post(
        API, json=payload,
        headers={"Content-Type": "application/json-rpc"}, timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"{method}: {data['error'].get('data', data['error']['message'])}")
    return data["result"]

def login():
    global _auth
    _auth = call("user.login", {"username": ZBX_USER, "password": ZBX_PASS}, needs_auth=False)

def host_info(name):
    got = call("host.get", {
        "filter": {"host": [name]},
        "selectInterfaces": ["interfaceid", "ip"],
    })
    return got[0] if got else None

def ensure_item(host, chk):
    found = call("item.get", {"hostids": host["hostid"], "filter": {"key_": chk["key"]}})
    if found:
        return False
    call("item.create", {
        "name": chk["item"],
        "key_": chk["key"],
        "hostid": host["hostid"],
        "type": 0,
        "value_type": chk["value_type"],
        "delay": chk["delay"],
        "interfaceid": host["interfaces"][0]["interfaceid"],
    })
    return True

def ensure_trigger(hostname, chk):
    found = call("trigger.get", {"host": hostname, "filter": {"description": chk["desc"]}})
    if found:
        return False
    call("trigger.create", {
        "description": chk["desc"],
        "expression": chk["expr"].replace("{H}", hostname),
        "priority": chk["priority"],
        "comments": "Definido por codigo (monitorizacion.py).",
    })
    return True

def apply_checks(name, checks):
    info = host_info(name)
    if not info:
        print(f"  !  {name:<16} no está dado de alta (ejecuta alta_hosts.py antes)")
        return
    items = triggers = 0
    for chk in checks:
        if ensure_item(info, chk):
            items += 1
        if ensure_trigger(name, chk):
            triggers += 1
    print(f"  ·  {name:<16} {len(checks)} checks  (items nuevos: {items}, triggers nuevos: {triggers})")

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "hosts.json"), encoding="utf-8") as f:
        wanted = json.load(f)

    login()
    print(f"Conectado a {API} como {ZBX_USER}\n")

    for h in wanted:
        checks = [PING] + RESOURCES if h.get("os", "linux") == "linux" else [PING]
        apply_checks(h["name"], checks)

    apply_checks(SERVER_HOST, [POSTGRES])

    print("\nMonitorización definida por código. Para verla saltar, para un agente:")
    print("  vagrant ssh zbx-agent01 -c 'sudo systemctl stop zabbix-agent2'")
    print("y en ~2 min el problema aparece en Monitoring -> Problems (y llega el correo).")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        sys.exit(f"error: no puedo conectar a {API}. ¿VM levantada y Zabbix operativo?")
    except Exception as exc:
        sys.exit(f"error: {exc}")
