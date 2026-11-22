"""Collect authenticated takes and publish an encrypted master for the team's invitations."""
import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from render import PROJECT, ROOT, check_take, render

LIMIT=23*1024*1024
REPO="danielmontoya00/video-joiner"
API="https://api.github.com/repos/"+REPO
ROLES=[r["id"] for r in PROJECT["roles"]]
KEYS={}
TOKEN=""
ATTACH=re.compile(r"https://github\.com/user-attachments/files/[0-9]+/[-A-Za-z0-9_.%]+\.zip\b",re.I)


def api(path):
    req=Request(API+path,headers={"Authorization":"Bearer "+TOKEN,"User-Agent":"estudio-equipo-10","Accept":"application/vnd.github+json"})
    with urlopen(req,timeout=35) as s:return json.load(s)


def packet(data,role):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        info=z.infolist()
        if len(info)!=1 or info[0].filename!="toma.bin" or info[0].file_size>LIMIT or info[0].compress_type!=zipfile.ZIP_STORED:
            raise ValueError("Paquete no válido.")
        raw=z.read(info[0])
    return AESGCM(KEYS[role]).decrypt(raw[:12],raw[12:],("studio-v1/"+role).encode())


def candidates():
    result={r:[] for r in ROLES}
    for page in range(1,5):
        issues=api(f"/issues?state=all&sort=updated&direction=desc&per_page=100&page={page}")
        for issue in issues:
            if "pull_request" in issue:continue
            role=next((r for r in ROLES if issue["title"]=="Toma / "+r),None)
            if not role:continue
            urls=ATTACH.findall(issue.get("body") or "")
            if urls:
                url=urls[-1];result[role].append((issue["updated_at"],url))
        if len(issues)<100:break
    for r in ROLES:
        directory=ROOT/"entradas"/r
        if not directory.is_dir():continue
        for f in directory.glob("*.zip"):
            if f.is_symlink() or not re.fullmatch(r"[0-9a-f-]{36}\.zip",f.name):continue
            stamp=subprocess.check_output(["git","log","-1","--format=%cI","--",f.relative_to(ROOT).as_posix()],cwd=ROOT,text=True).strip()
            if stamp:result[r].append((stamp.replace("+00:00","Z"),f))
    return result


def read_input(source):
    if isinstance(source,Path):
        if source.stat().st_size>LIMIT:raise ValueError("Archivo demasiado grande.")
        return source.read_bytes()
    if not ATTACH.fullmatch(source):raise ValueError("Dirección no válida.")
    with urlopen(Request(source,headers={"User-Agent":"estudio-equipo-10"}),timeout=50) as f:
        host=urlparse(f.geturl()).hostname or ""
        if host!="github.com" and not host.endswith((".githubusercontent.com",".amazonaws.com",".blob.core.windows.net")):
            raise ValueError("Destino no válido.")
        data=f.read(LIMIT+1)
    if len(data)>LIMIT:raise ValueError("Archivo demasiado grande.")
    return data


def digest(blob):return hashlib.sha256(blob).hexdigest()


def process(state,public,work):
    shutil.copytree(ROOT/"site",public,dirs_exist_ok=True)
    memo=state/"registro.json"
    record=json.loads(memo.read_text()) if memo.exists() else {"accepted":{},"final":None}
    available=candidates()
    for role in PROJECT["roles"]:
        rid=role["id"];old=record["accepted"].get(rid,{})
        options=sorted(available[rid],key=lambda c:(c[0],str(c[1])),reverse=True)
        for stamp,source in options:
            ref=str(source.relative_to(ROOT)) if isinstance(source,Path) else source
            if old and (stamp,ref)<=(old["time"],old["ref"]):break
            try:
                data=read_input(source);plain=packet(data,rid)
                tmp=work/(rid+".take");tmp.write_bytes(plain)
                check_take(tmp,role["duration"])
            except (ValueError,KeyError,zipfile.BadZipFile,subprocess.SubprocessError) as exc:
                print("Toma descartada:",rid,type(exc).__name__);continue
            except Exception as exc:
                from cryptography.exceptions import InvalidTag
                if isinstance(exc,InvalidTag):
                    print("Invitación incorrecta:",rid);continue
                if isinstance(exc,HTTPError) and exc.code in (403,404,410):
                    print("Adjunto no disponible:",rid);continue
                raise
            (state/(rid+".zip")).write_bytes(data)
            record["accepted"][rid]={"time":stamp,"ref":ref,"hash":digest(data)}
            break
    ready={r:r in record["accepted"] for r in ROLES}
    if all(ready.values()):
        version=digest("|".join(record["accepted"][r]["hash"] for r in ROLES).encode())
        if version!=record.get("final") or not (state/"resultado.bin").exists():
            takes={}
            for r in ROLES:
                p=work/(r+".take");p.write_bytes(packet((state/(r+".zip")).read_bytes(),r));takes[r]=p
            mp4=work/"master.mp4";render(takes,work,mp4)
            nonce=os.urandom(12)
            (state/"resultado.bin").write_bytes(nonce+AESGCM(KEYS["final"]).encrypt(nonce,mp4.read_bytes(),b"studio-v1/final"))
            record["final"]=version
        shutil.copyfile(state/"resultado.bin",public/"resultado.bin")
    status={"roles":ready,"final":record.get("final"),"message":"El montaje empieza al recibir las tres tomas."}
    (public/"estado.json").write_text(json.dumps(status),encoding="utf8")
    memo.write_text(json.dumps(record,sort_keys=True),encoding="utf8")
    print("Tomas verificadas:",sum(ready.values()),"/",len(ROLES))


if __name__=="__main__":
    import sys
    secrets=json.loads(os.environ.pop("STUDIO_KEYS"))
    KEYS={k:base64.urlsafe_b64decode(v+"=") for k,v in secrets.items()}
    for role in PROJECT["roles"]:
        assert digest(KEYS[role["id"]])==role["keyHash"]
    TOKEN=os.environ.pop("GH_TOKEN")
    with tempfile.TemporaryDirectory() as temp:
        process(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve(),Path(temp))
