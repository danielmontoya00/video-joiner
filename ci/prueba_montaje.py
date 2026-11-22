"""Exercise the production path with generated cameras and temporary, unrelated keys."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
from io import BytesIO
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import studio
from demos import evidence


def run():
    with tempfile.TemporaryDirectory() as td:
        t=Path(td);vault=t/"vault";vault.mkdir();public=t/"public";clips=t/"clips";clips.mkdir()
        studio.KEYS={r:os.urandom(32) for r in [*studio.ROLES,"final"]}
        candidates={r:[] for r in studio.ROLES}
        studio.candidates=lambda:candidates
        packets={}
        for i,(role,codec,container,size,color) in enumerate(zip(studio.PROJECT["roles"],["libx264","libvpx","libx264"],
                 ["mp4","webm","mov"],["320x180","180x320","240x240"],["green","navy","maroon"])):
            path=t/("sample."+container)
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","lavfi","-i",f"color={color}:s={size}:r=12",
                "-f","lavfi","-i",f"sine=frequency={330+110*i}:sample_rate=44100","-t",str(role["duration"]),
                "-c:v",codec,"-c:a","libopus" if container=="webm" else "aac",str(path)],check=True)
            studio.check_take(path,role["duration"])
            rid=role["id"];iv=os.urandom(12)
            sealed=iv+AESGCM(studio.KEYS[rid]).encrypt(iv,path.read_bytes(),("studio-v1/"+rid).encode())
            out=BytesIO()
            with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_STORED) as z:z.writestr("toma.bin",sealed)
            ref="https://github.com/user-attachments/files/100/"+rid+".zip";packets[ref]=out.getvalue()
            candidates[rid]=[("2026-01-01T00:00:00Z",ref)]
            studio.read_input=lambda src:packets[src]
            studio.process(vault,public,clips)
            state=json.loads((public/"estado.json").read_text())
            assert sum(state["roles"].values())==i+1
            assert bool(state["final"])==(i==2)
        data=(public/"resultado.bin").read_bytes()
        raw=AESGCM(studio.KEYS["final"]).decrypt(data[:12],data[12:],b"studio-v1/final")
        master=t/"validate.mp4";master.write_bytes(raw)
        if os.environ.get("EVIDENCIA_DIR"):
            evidence(master,t,Path(os.environ["EVIDENCIA_DIR"]))
        result=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_format","-show_streams","-of","json",master]))
        v,a=result["streams"];assert (v["width"],v["height"],v["codec_name"],v["pix_fmt"])==(1920,1080,"h264","yuv420p")
        assert a["codec_name"]=="aac" and a["channels"]==2 and abs(float(result["format"]["duration"])-221)<0.15
        assert v["avg_frame_rate"]=="24/1" or abs(eval_fraction(v["avg_frame_rate"])-24)<.01
        initial=state["final"]
        candidates["josue"].insert(0,("2026-01-02T00:00:00Z","https://github.com/user-attachments/files/100/falsa.zip"))
        packets[candidates["josue"][0][1]]=packets[candidates["daniel"][0][1]]
        studio.process(vault,public,clips)
        assert json.loads((public/"estado.json").read_text())["final"]==initial and (public/"resultado.bin").read_bytes()==data
        assert not list(public.glob("*.take")) and not list(public.glob("*.mp4"))
        print("OK: recepción gradual, tres formatos, tres orientaciones, vídeo de 221 s, H.264/AAC, idempotencia y rechazo de clave incorrecta.")


def eval_fraction(rate):
    n,d=map(int,rate.split("/"))
    return n/d


if __name__=="__main__":run()
