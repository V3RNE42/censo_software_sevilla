#!/usr/bin/env python3
"""Crea el repo privado en GitHub y hace el push inicial. Idempotente."""
import json, re, subprocess, urllib.request, urllib.error

cred = open('/root/.git-credentials').read().strip()
tok = re.match(r'https://([^:]+):([^@]+)@(.+)', cred).group(2)
REPO = "censo_software_sevilla"
OWNER = "V3RNE42"


def gh(method, path, payload=None):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": "Bearer " + tok,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "hermes"},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


st, d = gh("GET", f"/repos/{OWNER}/{REPO}")
if st == 200:
    print(f"repo ya existe: {d['full_name']} | privado: {d['private']}")
else:
    st, d = gh("POST", "/user/repos", {
        "name": REPO,
        "description": "Censo OSINT de empresas de desarrollo de software en las provincias de Sevilla (INE 41) y Malaga (INE 29)",
        "private": True, "has_issues": True, "has_wiki": False,
    })
    print(f"POST /user/repos -> {st}")
    if st == 201:
        print(f"  creado: {d['full_name']} | privado: {d['private']}")
        print(f"  url: {d['html_url']}")
    else:
        raise SystemExit(f"  error: {d.get('message')} {d.get('errors')}")

# push
subprocess.run(["git", "remote", "remove", "origin"], cwd="/root/censo_software_sevilla",
               capture_output=True)
subprocess.run(["git", "remote", "add", "origin",
                f"https://github.com/{OWNER}/{REPO}.git"],
               cwd="/root/censo_software_sevilla", check=True)
print("remoto añadido")
