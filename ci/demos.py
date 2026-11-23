"""Compare the moving demo region against the two original video objects inside the PPTX."""
from pathlib import Path
from zipfile import ZipFile
import json
import os
import subprocess
import numpy as np

FF=os.environ.get("STUDIO_FFMPEG","ffmpeg")
ROOT=Path(__file__).resolve().parents[1]
# Source-camera timings relative to the 3:41 presentation, in seconds.
DEMOS=[(3,"ruta.mp4",53),(5,"consulta.mp4",109)]


def sequence(video, start, duration, crop=None):
    filters = ([f"crop={crop}"] if crop else []) + ["fps=24","scale=160:90:flags=area:out_range=full","format=rgb24"]
    raw = subprocess.check_output([FF,"-loglevel","error","-nostdin","-xerror","-ss",str(start),"-i",str(video),
        "-t",str(duration),"-an","-vf",",".join(filters),"-f","rawvideo","-pix_fmt","rgb24","pipe:1"],timeout=60)
    rgb=np.frombuffer(raw,np.uint8).reshape(-1,90,160,3).astype(np.uint16)
    return ((54*rgb[...,0]+183*rgb[...,1]+19*rgb[...,2])>>8).astype(np.float32)


def verify_sequence(original, master, start, crop):
    ref=sequence(original,0,30)
    out=sequence(master,start,len(ref)/24,crop)
    if abs(len(ref)-len(out))>1:
        raise ValueError("La demostración está incompleta.")
    n=min(len(ref),len(out))
    ref,out=ref[:n],out[:n]
    # Distinguish a missing action from a conversion between full and limited range.
    lo,hi=np.percentile(ref[::12],[1,98])
    low,high=np.percentile(out[::12],[1,98])
    if max(abs(lo-low),abs(hi-high))>26 or high-low<50:
        raise ValueError(f"Contraste incorrecto en la demo de {start} s.")
    out=(out-low)*((hi-lo)/(high-low))+lo
    # Allow up to 125 ms for the different frame grids of screen capture, camera and mux.
    padded=np.pad(out,((3,3),(0,0),(0,0)),mode="edge")
    diff=np.minimum.reduce([np.abs(ref-padded[j:j+n]).mean(axis=(1,2)) for j in range(7)])
    if diff.max()>5:
        raise ValueError(f"Demo de {start} s: discrepancia {diff.max():.2f}/255 en {start+int(diff.argmax())/24:.2f} s.")
    # At each substantial UI change, the corresponding output must also move.
    windows=0
    for i in range(3,n-15,6):
        change=np.abs(ref[i+12]-ref[i]).mean()
        if change>1.0:
            windows+=1
            before=out[i-3:i+4]
            after=out[i+9:i+16]
            movement=max(np.abs(after-frame).mean(axis=(1,2)).max() for frame in before)
            if movement<change*.55:
                raise ValueError(f"Falta una interacción en {start+i/24:.2f} s.")
    if not windows:
        raise ValueError("No se reconoció ninguna interacción en el video de referencia.")
    return {"inicio":start,"fotogramas_verificados":n,"error_maximo_sobre_255":round(float(diff.max()),3),"ventanas_con_interaccion":windows}


def verify(master,work,composed=True):
    crop="1274:716:139:204" if composed else "1120:630:80:78"
    report=[]
    with ZipFile(ROOT/"site/assets/presentacion.pptx") as deck:
        for slide,name,start in DEMOS:
            original=work/name;original.write_bytes(deck.read("ppt/media/"+name))
            report.append({"diapositiva":slide,"video":name,**verify_sequence(original,master,start,crop)})
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
