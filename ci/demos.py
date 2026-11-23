"""Compare the moving demo region against the two original video objects inside the PPTX."""
from pathlib import Path
from zipfile import ZipFile
import json
import os
import subprocess
from itertools import combinations
import numpy as np

FF=os.environ.get("STUDIO_FFMPEG","ffmpeg")
ROOT=Path(__file__).resolve().parents[1]
# Source-camera timings relative to the 3:41 presentation, in seconds.
DEMOS=[(3,"ruta.mp4",53,[1.25,3.75,6.5,9.75,13]),(5,"consulta.mp4",109,[1.5,5.5,10,15.5,20])]


def sample(video,time,crop):
    vf=(f"crop={crop}," if crop else "")+"scale=224:126:flags=area,format=gray"
    return subprocess.check_output([FF,"-hide_banner","-loglevel","error","-ss",str(time),"-i",str(video),
        "-an","-frames:v","1","-vf",vf,"-f","rawvideo","-pix_fmt","gray","pipe:1"])


def delta(a,b):
    assert len(a)==len(b)==224*126
    return sum(abs(x-y) for x,y in zip(a,b))/len(a)


def sequence(video, start, duration, crop=None):
    filters = ([f"crop={crop}"] if crop else []) + ["fps=24","scale=160:90:flags=area","format=gray"]
    raw = subprocess.check_output([FF,"-loglevel","error","-nostdin","-xerror","-ss",str(start),"-i",str(video),
        "-t",str(duration),"-an","-vf",",".join(filters),"-f","rawvideo","-pix_fmt","gray","pipe:1"],timeout=60)
    return np.frombuffer(raw,np.uint8).reshape(-1,90,160).astype(np.int16)


def verify_sequence(original, master, start, crop):
    ref=sequence(original,0,30)
    out=sequence(master,start,len(ref)/24,crop)
    if abs(len(ref)-len(out))>1:
        raise ValueError("La demostración está incompleta.")
    n=min(len(ref),len(out))
    ref,out=ref[:n],out[:n]
    # Check every interior frame, allowing a single-frame shift from AAC/MP4 timing.
    diff=np.minimum.reduce([np.abs(ref[1:-1]-other).mean(axis=(1,2))
                            for other in (out[:-2],out[1:-1],out[2:])])
    if diff.max()>5:
        raise ValueError(f"La demo difiere del original en {start+(int(diff.argmax())+1)/24:.2f} s.")
    # Require each substantial UI transition to survive even on mostly white slides.
    for i in range(0,n-12,6):
        original_change=np.abs(ref[i+12]-ref[i]).mean()
        if original_change>1.0:
            movement=np.max(np.abs(out[i:i+14]-out[i]).mean(axis=(1,2)))
            if movement<original_change*.55:
                raise ValueError(f"Falta una interacción de la demo en {start+i/24:.2f} s.")
    return n


def verify(master,work,composed=True):
    crop="1274:716:139:204" if composed else "1120:630:80:78"
    report=[]
    with ZipFile(ROOT/"site/assets/presentacion.pptx") as deck:
        for slide,name,start,samples in DEMOS:
            original=work/name;original.write_bytes(deck.read("ppt/media/"+name))
            frames_checked=verify_sequence(original,master,start,crop)
            ref=[sample(original,t,None) for t in samples]
            out=[sample(master,start+t,crop) for t in samples]
            distances=[delta(a,b) for a,b in zip(ref,out)]
            ref_motion=max(delta(a,b) for a,b in combinations(ref,2))
            out_motion=max(delta(a,b) for a,b in combinations(out,2))
            assert max(distances)<5, (name,"discrepancia entre master y demo",distances)
            assert ref_motion>1 and out_motion>=ref_motion*.7,(name,"falta movimiento",ref_motion,out_motion)
            report.append({"diapositiva":slide,"video":name,"inicio":start,"fotogramas_verificados":frames_checked,
                "error_medio_maximo_sobre_255":round(max(distances),3),"movimiento_referencia":round(ref_motion,3),
                "movimiento_observado":round(out_motion,3)})
    print(json.dumps(report,ensure_ascii=False))
    return report


def evidence(master,work,destination):
    destination.mkdir(parents=True,exist_ok=True)
    files=[]
    for i,(start,duration) in enumerate([(50,22),(106,30)],1):
        output=work/f"demo-evidencia-{i}.mp4"
        vf=("drawbox=x=0:y=960:w=1920:h=120:color=0x112f29:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='DEMO {i}   /   COMPROBACIÓN DEL MONTAJE':"
            "fontcolor=white:fontsize=28:x=48:y=991,"
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='CÁMARA SIMULADA':fontcolor=white:fontsize=22:x=1579:y=390")
        subprocess.run([FF,"-v","error","-y","-ss",str(start),"-i",str(master),"-t",str(duration),"-an","-vf",vf,
          "-c:v","libx264","-threads","3","-preset","veryfast","-crf","19","-pix_fmt","yuv420p",str(output)],check=True)
        files.append(output.name)
    listing=work/"evidencias.txt";listing.write_text("".join("file '"+f+"'\n" for f in files),encoding="ascii")
    subprocess.run([FF,"-v","error","-y","-f","concat","-safe","1","-i",str(listing),"-c","copy","-movflags","+faststart",
        str(destination/"Verificacion - Demo 1 y Demo 2.mp4")],check=True)
