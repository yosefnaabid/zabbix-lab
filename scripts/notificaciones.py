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

SMTP_SERVER = os.environ.get("LAB_SMTP_SERVER", "127.0.0.1")
SMTP_PORT   = int(os.environ.get("LAB_SMTP_PORT", "1025"))
MAIL_FROM   = os.environ.get("LAB_MAIL_FROM", "zabbix@lab.local")
MAIL_TO     = os.environ.get("LAB_MAIL_TO",   "admin@lab.local")

EMAIL_MT    = "Email (Mailpit lab)"
TELEGRAM_MT = "Telegram"
ACTION_NAME = "Notificar problemas (lab)"

SUBJ_PROBLEM = "PROBLEMA: {EVENT.NAME}"
MSG_PROBLEM  = ("Problema: {EVENT.NAME}\n"
               "Host: {HOST.NAME}\n"
               "Gravedad: {EVENT.SEVERITY}\n"
               "Hora: {EVENT.DATE} {EVENT.TIME}\n")
SUBJ_RECOVER = "RESUELTO: {EVENT.NAME}"
MSG_RECOVER  = ("Resuelto: {EVENT.NAME}\n"
               "Host: {HOST.NAME}\n"
               "Hora: {EVENT.RECOVERY.DATE} {EVENT.RECOVERY.TIME}\n")

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

def admin_userid():
    got = call("user.get", {"filter": {"username": [ZBX_USER]}})
    if not got:
        raise RuntimeError(f"usuario {ZBX_USER!r} no encontrado")
    return got[0]["userid"]

def telegram_creds():
    tok  = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    here = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(here, "notify.local.json")
    if (not tok or not chat) and os.path.exists(local):
        with open(local, encoding="utf-8") as f:
            d = json.load(f)
        tok  = tok  or d.get("telegram_bot_token")
        chat = chat or d.get("telegram_chat_id")
    return tok, chat

def ensure_email_mediatype():
    found = call("mediatype.get", {"filter": {"name": [EMAIL_MT]}})
    params = {
        "type": 0,
        "name": EMAIL_MT,
        "smtp_server": SMTP_SERVER,
        "smtp_port": SMTP_PORT,
        "smtp_helo": "lab.local",
        "smtp_email": MAIL_FROM,
        "smtp_security": 0,
        "smtp_verify_peer": 0,
        "smtp_verify_host": 0,
        "smtp_authentication": 0,
        "content_type": 1,
        "status": 0,
    }
    if found:
        params["mediatypeid"] = found[0]["mediatypeid"]
        call("mediatype.update", params)
        return found[0]["mediatypeid"], False
    mtid = call("mediatype.create", params)["mediatypeids"][0]
    return mtid, True

def ensure_telegram_mediatype(token):
    got = call("mediatype.get", {"output": "extend", "selectMessageTemplates": "extend",
                                 "filter": {"name": [TELEGRAM_MT]}})
    if not got:
        return None
    mt = got[0]
    params = mt.get("parameters", []) or []
    seen = False
    for p in params:
        if p.get("name") == "Token":
            p["value"] = token
            seen = True
    if not seen:
        params.append({"name": "Token", "value": token})
    call("mediatype.update", {"mediatypeid": mt["mediatypeid"], "status": 0, "parameters": params})
    return mt["mediatypeid"]

def set_user_media(userid, medias):
    call("user.update", {"userid": userid, "medias": medias})

def ensure_action(userid):
    found = call("action.get", {"filter": {"name": [ACTION_NAME]}, "selectOperations": "extend"})
    common = {
        "name": ACTION_NAME,
        "eventsource": 0,
        "status": 0,
        "esc_period": "1h",
        "pause_suppressed": 1,
        "filter": {"evaltype": 0, "conditions": []},
        "operations": [{
            "operationtype": 0,
            "opmessage": {"default_msg": 0, "subject": SUBJ_PROBLEM,
                          "message": MSG_PROBLEM, "mediatypeid": "0"},
            "opmessage_usr": [{"userid": userid}],
        }],
        "recovery_operations": [{
            "operationtype": 0,
            "opmessage": {"default_msg": 0, "subject": SUBJ_RECOVER,
                          "message": MSG_RECOVER, "mediatypeid": "0"},
            "opmessage_usr": [{"userid": userid}],
        }],
    }
    if found:
        common["actionid"] = found[0]["actionid"]
        call("action.update", common)
        return False
    call("action.create", common)
    return True

def main():
    login()
    print(f"Conectado a {API} como {ZBX_USER}\n")
    uid = admin_userid()

    email_id, email_new = ensure_email_mediatype()
    print(f"  ·  media Email     {'creado' if email_new else 'actualizado':<11} "
          f"-> {SMTP_SERVER}:{SMTP_PORT}")

    medias = [{
        "mediatypeid": email_id, "sendto": MAIL_TO,
        "active": 0, "severity": 63, "period": "1-7,00:00-24:00",
    }]

    tok, chat = telegram_creds()
    if tok and chat:
        tg_id = ensure_telegram_mediatype(tok)
        if tg_id:
            medias.append({
                "mediatypeid": tg_id, "sendto": chat,
                "active": 0, "severity": 63, "period": "1-7,00:00-24:00",
            })
            print(f"  ·  media Telegram  activado    -> chat {chat}")
        else:
            print("  !  media Telegram  no existe en este Zabbix; lo salto")
    else:
        print("  -  media Telegram  sin credenciales (opcional); ver README para activarlo")

    set_user_media(uid, medias)
    print(f"  ·  usuario {ZBX_USER:<8} medios asignados ({len(medias)})")

    act_new = ensure_action(uid)
    print(f"  ·  accion '{ACTION_NAME}' {'creada' if act_new else 'actualizada'}")

    print("\nNotificaciones configuradas por codigo. Para verlo end-to-end:")
    print("  vagrant ssh zbx-agent01 -c 'sudo systemctl stop zabbix-agent2'")
    print("  ...y en ~2 min el correo aparece en Mailpit: http://localhost:8025")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        sys.exit(f"error: no puedo conectar a {API}. Esta la VM levantada y Zabbix operativo?")
    except Exception as exc:
        sys.exit(f"error: {exc}")
