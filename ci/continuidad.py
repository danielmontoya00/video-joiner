"""Check each camera and voice against the take, including during the two demos."""
import subprocess
import json
import numpy as np
from render import FFMPEG, FFPROBE, PROJECT

FPS = 8
WIDTH, HEIGHT = 64, 80


def read_stream(path, start, duration, options):
    return subprocess.check_output([FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-xerror",
        "-threads", "3", "-ss", str(start), "-i", str(path), "-t", str(duration), *options, "pipe:1"], timeout=120)


def camera(path, start, duration, region):
    vf = f"setpts=PTS-STARTPTS,fps={FPS},{region},scale={WIDTH}:{HEIGHT}:flags=area,format=gray"
    raw = read_stream(path, start, duration, ["-map","0:v:0","-an","-vf",vf,"-f","rawvideo","-pix_fmt","gray"])
    return np.frombuffer(raw, np.uint8).reshape(-1,HEIGHT,WIDTH).astype(np.int16)


def audio_levels(path, start, duration):
    raw = read_stream(path, start, duration, ["-map","0:a:0","-vn","-af","highpass=f=65","-ar","8000","-ac","1","-f","s16le"])
    samples = np.frombuffer(raw, "<i2").astype(np.float32)
    # One independent level per tenth of a second, ignoring partial final windows.
    blocks = samples[:len(samples)//800*800].reshape(-1,800)
    return np.sqrt(np.mean(blocks**2, axis=1))


def check_camera(source, rendered):
    n = min(len(source),len(rendered))
    src, dst = source[:n], rendered[:n]
    if n<2*FPS:
        raise ValueError("La cámara no tiene suficientes fotogramas.")
    step_src=np.abs(np.diff(src,axis=0)).mean(axis=(1,2))
    step_dst=np.abs(np.diff(dst,axis=0)).mean(axis=(1,2))
    # Nearest sample within 125 ms accounts for rounding from VFR to 24 fps.
    distance=np.minimum.reduce([np.abs(src[1:-1]-other).mean(axis=(1,2))
                                for other in (dst[:-2],dst[1:-1],dst[2:])])
    for i in range(0,len(step_src)-FPS+1,FPS):
        region=slice(i,i+2*FPS)
        motion=step_src[region].mean()
        if motion>0.6 and step_dst[region].mean()<motion*.18:
            raise ValueError(f"La cámara se congela cerca del segundo {i/FPS:.1f} de la toma.")
        if distance[region].size and np.median(distance[region])>13:
            raise ValueError(f"La imagen difiere de la toma cerca del segundo {i/FPS:.1f}.")


def check_audio(source, rendered):
    n=min(len(source),len(rendered))
    if n<20:
        raise ValueError("Falta la pista de voz.")
    src, dst=source[:n],rendered[:n]
    active=max(32,float(np.percentile(src,90))*.07)
    quiet=max(8,float(np.percentile(dst,90))*.02)
    for i in range(0,n-9,5):
        if np.count_nonzero(src[i:i+10]>active)>=5 and dst[max(i-1,0):min(i+11,n)].max()<quiet:
            raise ValueError(f"Se pierde voz cerca del segundo {i/10:.1f} de la toma.")


def verify_presenters(master,takes):
    packets=json.loads(subprocess.check_output([FFPROBE,"-v","error","-select_streams","a:0",
        "-show_packets","-show_entries","packet=duration_time","-of","json",str(master)],timeout=60))["packets"]
    # Exclude the final partial AAC packet. Every other packet is exactly 1024 samples.
    if not packets or any(abs(float(p["duration_time"])*48000-1024)>.1 for p in packets[:-1]):
        raise ValueError("Las marcas de tiempo del audio no siguen el reloj AAC de 48 kHz.")
    for role in PROJECT["roles"]:
        rid,start,duration=role["id"],role["start"],role["duration"]
        take=takes[rid]
        expected=camera(take,0,duration,"scale=300:372:force_original_aspect_ratio=increase,crop=300:372,setsar=1")
        actual=camera(master,start,duration,"crop=300:372:1554:212")
        if len(actual)<duration*FPS-1:
            raise ValueError(f"Tramo incompleto en el montaje: {rid}")
        try:
            check_camera(expected,actual)
            check_audio(audio_levels(take,0,duration),audio_levels(master,start,duration))
        except ValueError as exc:
            raise ValueError(f"{rid}: {exc}") from exc
        print(f"{rid}: cámara y voz contrastadas a lo largo de {duration} s.")
