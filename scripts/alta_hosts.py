#!/usr/bin/env python3

import json
import os
import sys
import requests

ZBX_URL  = os.environ.get("ZBX_URL",  "http://localhost:8080")
ZBX_USER = os.environ.get("ZBX_USER", "Admin")
ZBX_PASS = os.environ.get("ZBX_PASS", "zabbix")
API = ZBX_URL.rstrip("/") + "/api_jsonrpc.php"

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

def group_id(name):
    found = call("hostgroup.get", {"filter": {"name": [name]}})
    if found:
        return found[0]["groupid"]
    return call("hostgroup.create", {"name": name})["groupids"][0]

def template_id(name):
    found = call("template.get", {"filter": {"host": [name]}})
    if not found:
        raise RuntimeError(
            f"plantilla no encontrada: {name!r}. "
            f"Revisa el nombre EXACTO en Zabbix › Data collection › Templates."
        )
    return found[0]["templateid"]

def host_exists(name):
    return bool(call("host.get", {"filter": {"host": [name]}}))

def create_host(h):
    params = {
        "host": h["name"],
        "interfaces": [{
            "type": 1,
            "main": 1, "useip": 1,
            "ip": h["ip"], "dns": "",
            "port": str(h.get("port", 10050)),
        }],
        "groups": [{"groupid": group_id(h["group"])}],
        "templates": [{"templateid": template_id(t)} for t in h.get("templates", [])],
    }
    call("host.create", params)

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "hosts.json"), encoding="utf-8") as f:
        hosts = json.load(f)

    login()
    print(f"Conectado a {API} como {ZBX_USER}\n")

    created = skipped = 0
    for h in hosts:
        if host_exists(h["name"]):
            print(f"  =  {h['name']:<16} ya existe, lo dejo")
            skipped += 1
            continue
        create_host(h)
        print(f"  +  {h['name']:<16} creado ({h['ip']})")
        created += 1

    print(f"\nHecho: {created} creado(s), {skipped} sin cambios.")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        sys.exit(f"error: no puedo conectar a {API}. ¿Está la VM levantada y "
                 f"Zabbix operativo?")
    except Exception as exc:
        sys.exit(f"error: {exc}")
