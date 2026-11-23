"""Validate camera takes, compose a presentation master, and encode a mobile-compatible MP4."""
import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FFMPEG = os.environ.get("STUDIO_FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("STUDIO_FFPROBE", "ffprobe")
SAFE = ["-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,matroska,webm"]
ROOT = Path(__file__).resolve().parents[1]
PROJECT = json.loads((ROOT/"site/proyecto.json").read_text(encoding="utf8"))


def check_take(path, expected):
    args = [FFPROBE, "-v","error", *SAFE, "-show_streams","-show_packets","-show_entries",
            "stream=index,codec_type,width,height:packet=stream_index,pts_time,duration_time","-of","json",str(path)]
    result = subprocess.run(args, capture_output=True, timeout=35, check=True)
    data = json.loads(result.stdout)
    streams = data["streams"]
    videos = [s for s in streams if s["codec_type"] == "video"]
    audio = [s for s in streams if s["codec_type"] == "audio"]
    if len(videos)!=1 or len(audio)!=1 or videos[0]["width"]*videos[0]["height"]>4096*4096:
        raise ValueError("Se requiere una pista de cámara y una de audio.")
    for stream in [videos[0], audio[0]]:
        intervals = [(float(p["pts_time"]),float(p.get("duration_time",0))) for p in data["packets"]
                     if p["stream_index"]==stream["index"] and p.get("pts_time","N/A")!="N/A"]
        if not intervals: raise ValueError("Una pista está vacía.")
        length=max(t+d for t,d in intervals)-min(t for t,d in intervals)
        if abs(length-expected)>3.1:
            raise ValueError(f"La toma debe durar {expected} segundos, con un margen de tres segundos.")


def font(size, serif=False, bold=False):
    name = ("DejaVuSerif" if serif else "DejaVuSans") + ("-Bold" if bold else "") + ".ttf"
    default = "/usr/share/fonts/truetype/dejavu/" + name
    windows = "C:/Windows/Fonts/" + ("georgia.ttf" if serif else "segoeuib.ttf" if bold else "segoeui.ttf")
    return ImageFont.truetype(default if Path(default).is_file() else windows,size)


def frame(path, role, index):
    im=Image.new("RGB",(1920,1080),"#112f29")
    d=ImageDraw.Draw(im)
    d.text((48,32),"LLEGADAS SIN FRICCIÓN",font=font(28,bold=True),fill="#eff4df")
    d.text((1874,38),"TEC  /  EQUIPO 10",anchor="ra",font=font(23),fill="#ccd9c4")
    d.rounded_rectangle((40,107,1511,942),radius=15,fill="#39584c")
    d.rounded_rectangle((1531,107,1878,942),radius=14,fill="#204639")
    d.text((1554,151),f"PRESENTADOR   {index+1} / 3",font=font(18,bold=True),fill="#d4e8b5")
    y=623
    name=role["name"].split(" ",1)
    for line in name:
        d.text((1554,y),line,font=font(31,serif=True),fill="#f6f8ea");y+=44
    d.line((1555,y+12,1848,y+12),fill="#739180",width=2)
    line="";y+=36
    for w in role["theme"].split():
        if d.textlength((line+" "+w).strip(),font=font(21))>288:
            d.text((1555,y),line,font=font(21),fill="#d2e2d0");y+=31;line=w
        else:line=(line+" "+w).strip()
    d.text((1555,y),line,font=font(21),fill="#d2e2d0")
    d.text((49,992),"MAR­RIOTT SINGAPORE  /  CASO ACADÉMICO".replace("\u00ad",""),font=font(19),fill="#b8ccb9")
    d.text((1872,992),"PROTOTIPO Y PRUEBA",anchor="ra",font=font(19),fill="#b8ccb9")
    im.save(path)


def render(takes, work, output):
    # A pixel-format or range change mid-roll reinitializes FFmpeg's composition
    # graph and can reset both camera and audio. The distributed slide track is
    # normalized before encoding; verify its full timeline, not only its header.
    slides = ROOT / "site/assets/presentacion.mp4"
    fields = ("width","height","pix_fmt","color_range","color_space","color_primaries","color_transfer")
    frames = json.loads(subprocess.check_output([FFPROBE,"-v","error","-select_streams","v:0",
        "-show_frames","-show_entries","frame="+",".join(fields),"-of","json",str(slides)],timeout=120))["frames"]
    formats = {tuple(f.get(k) for k in fields) for f in frames}
    if len(formats)!=1 or len(frames)!=24*PROJECT["duration"]:
        raise ValueError("La pista de diapositivas debe mantener formato, rango de color y 24 fps durante todo el pitch.")
    segments=[]
    voices=[]
    for ix,role in enumerate(PROJECT["roles"]):
        duration=role["duration"];base=work/f"frame-{ix}.png";frame(base,role,ix)
        target=work/f"part-{ix}.mp4"
        graph=("[0:v]fps=24,setsar=1[canvas];[1:v]scale=1456:819,setsar=1,format=yuv444p[slide];"
               "[2:v]setpts=PTS-STARTPTS,fps=24,scale=300:372:force_original_aspect_ratio=increase,"
               "crop=300:372,setsar=1,tpad=stop_mode=clone:stop_duration=3.2[cam];"
               "[canvas][slide]overlay=48:115[base];[base][cam]overlay=1555:212,format=yuv420p[v]")
        subprocess.run([FFMPEG,"-hide_banner","-loglevel","error","-nostdin","-y","-loop","1","-framerate","24","-i",str(base),
          "-ss",str(role["start"]),"-i",str(slides),*SAFE,"-i",str(takes[role["id"]]),
          "-filter_complex_threads","2","-filter_complex",graph,"-map","[v]","-an","-t",str(duration),
          "-c:v","libx264","-preset","veryfast","-threads","3","-crf","20","-maxrate","2200k","-bufsize","4400k",
          "-profile:v","high","-level","4.0","-g","48","-pix_fmt","yuv420p",
          "-movflags","+faststart",str(target)],timeout=520,check=True)
        segments.append(target)
        # Keep speech on its own sample clock and encode AAC only once, so
        # individual AAC encoder delays do not accumulate at presenter cuts.
        voice=work/f"voice-{ix}.wav"
        af=("asetpts=N/SR/TB,highpass=f=65,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
            f"apad,atrim=end_sample={duration*48000},afade=t=in:d=0.035,"
            f"afade=t=out:st={duration-.065}:d=0.065,asettb=1/48000,asetpts=N")
        subprocess.run([FFMPEG,"-v","error","-nostdin","-y",*SAFE,"-i",str(takes[role["id"]]),
            "-map","0:a:0","-vn","-af",af,"-ac","2","-ar","48000","-c:a","pcm_s24le",str(voice)],
            check=True,timeout=120)
        voices.append(voice)
    listing=work/"partes.txt"
    listing.write_text("".join("file '"+p.name+"'\n" for p in segments),encoding="ascii")
    audio_listing=work/"voces.txt"
    audio_listing.write_text("".join("file '"+p.name+"'\n" for p in voices),encoding="ascii")
    subprocess.run([FFMPEG,"-loglevel","error","-nostdin","-y","-f","concat","-safe","1","-i",str(listing),
      "-f","concat","-safe","1","-i",str(audio_listing),"-map","0:v:0","-map","1:a:0","-c:v","copy",
      "-af","asettb=1/48000,asetpts=N","-enc_time_base:a","1:48000","-c:a","aac","-ar","48000","-ac","2","-b:a","160k",
      "-movflags","+faststart",str(output)],timeout=90,check=True)
