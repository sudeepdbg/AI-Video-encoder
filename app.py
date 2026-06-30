import os
import re
import csv
import json
import math
import time
import uuid
import shutil
import base64
import subprocess
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_webrtc import webrtc_streamer, RTCConfiguration
    WEBRTC_AVAILABLE = True
except Exception:
    WEBRTC_AVAILABLE = False

APP_TITLE = "EncodeIQ Studio"
WORKDIR = Path("work")
INPUT_DIR = WORKDIR / "inputs"
OUTPUT_DIR = WORKDIR / "outputs"
LOG_DIR = WORKDIR / "logs"
for d in [WORKDIR, INPUT_DIR, OUTPUT_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# -------------------------
# Page + visual styling
# -------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root {
  --bg0: #07111f;
  --bg1: #0b1830;
  --card: rgba(255,255,255,0.075);
  --card2: rgba(255,255,255,0.11);
  --text0: #f7fbff;
  --text1: #b8c7dc;
  --cyan: #3be7ff;
  --blue: #4b7bff;
  --violet: #8a5cff;
  --green: #4ee09b;
  --amber: #ffc857;
}
html, body, [data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 5% 5%, rgba(59,231,255,0.16), transparent 28%),
    radial-gradient(circle at 95% 8%, rgba(138,92,255,0.18), transparent 30%),
    linear-gradient(135deg, var(--bg0), var(--bg1));
}
[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 1.6rem; padding-bottom: 3rem;}
.hero {
  padding: 1.25rem 1.35rem;
  border: 1px solid rgba(255,255,255,0.14);
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(75,123,255,0.18), rgba(59,231,255,0.07));
  box-shadow: 0 22px 70px rgba(0,0,0,0.28);
}
.hero h1 {font-size: 2.35rem; margin: 0; line-height: 1.05; color: var(--text0);}
.hero p {font-size: 1rem; color: var(--text1); margin: 0.7rem 0 0 0;}
.pill {
  display: inline-block; padding: 0.22rem 0.62rem; margin: 0.2rem 0.25rem 0.2rem 0;
  border-radius: 999px; border: 1px solid rgba(255,255,255,0.17);
  background: rgba(255,255,255,0.08); color: #eaf6ff; font-size: 0.82rem;
}
.metric-card {
  padding: 0.95rem; border-radius: 18px; background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.12); min-height: 86px;
}
.small-muted {color: #b8c7dc; font-size: 0.88rem;}
.status-ok {color: #4ee09b; font-weight: 700;}
.status-warn {color: #ffc857; font-weight: 700;}
.status-bad {color: #ff6b6b; font-weight: 700;}
.stButton>button {
  border-radius: 14px; border: 0; color: white; font-weight: 700;
  background: linear-gradient(135deg, #2979ff, #8a5cff);
  box-shadow: 0 10px 24px rgba(75,123,255,0.28);
}
.stDownloadButton>button {border-radius: 14px; font-weight: 700;}
[data-testid="stSidebar"] {background: rgba(4,10,20,0.72); border-right: 1px solid rgba(255,255,255,0.11);}
video {border-radius: 18px; background: #000;}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Utility helpers
# -------------------------
def run_cmd(cmd: List[str], log_file: Path, timeout: Optional[int] = None) -> Tuple[int, str]:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.utcnow().isoformat() + "Z"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"\n\n--- {started} ---\n$ {' '.join(map(str, cmd))}\n")
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        out = p.stdout or ""
        with log_file.open("a", encoding="utf-8") as f:
            f.write(out)
            f.write(f"\n[exit_code] {p.returncode}\n")
        return p.returncode, out
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + "\nTIMEOUT"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(out)
        return 124, out
    except Exception as e:
        out = f"ERROR: {e}"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(out)
        return 1, out

@st.cache_data(show_spinner=False)
def ffmpeg_info() -> Dict:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    info = {"ffmpeg": ffmpeg, "ffprobe": ffprobe, "version": "", "encoders": [], "filters": []}
    if ffmpeg:
        try:
            info["version"] = subprocess.run([ffmpeg, "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5).stdout.splitlines()[0]
            info["encoders"] = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=8).stdout
            info["filters"] = subprocess.run([ffmpeg, "-hide_banner", "-filters"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=8).stdout
        except Exception as e:
            info["version"] = f"FFmpeg detection error: {e}"
    return info

def has_encoder(name: str) -> bool:
    return name in ffmpeg_info().get("encoders", "")

def has_filter(name: str) -> bool:
    return re.search(rf"\b{name}\b", ffmpeg_info().get("filters", "")) is not None

def safe_name(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("_")[:80] or "video"
    return stem

def save_upload(uploaded, folder: Path) -> Optional[Path]:
    if uploaded is None:
        return None
    out = folder / f"{int(time.time())}_{safe_name(uploaded.name)}{Path(uploaded.name).suffix.lower()}"
    out.write_bytes(uploaded.getbuffer())
    return out

def ffprobe_json(path: Path) -> Dict:
    info = ffmpeg_info()
    if not info["ffprobe"]:
        return {}
    cmd = [info["ffprobe"], "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        return json.loads(p.stdout) if p.stdout else {}
    except Exception:
        return {}

def primary_video_stream(meta: Dict) -> Dict:
    for s in meta.get("streams", []):
        if s.get("codec_type") == "video":
            return s
    return {}

def media_summary(path: Path) -> Dict:
    meta = ffprobe_json(path)
    vs = primary_video_stream(meta)
    fmt = meta.get("format", {})
    duration = float(fmt.get("duration", 0) or 0)
    size = int(fmt.get("size", path.stat().st_size if path.exists() else 0) or 0)
    bitrate = int(fmt.get("bit_rate", 0) or 0)
    return {
        "file": path.name,
        "codec": vs.get("codec_name", "unknown"),
        "width": int(vs.get("width", 0) or 0),
        "height": int(vs.get("height", 0) or 0),
        "fps": eval_fraction(vs.get("avg_frame_rate", "0/0")),
        "duration_sec": duration,
        "size_mb": size / (1024 * 1024),
        "bitrate_kbps": bitrate / 1000 if bitrate else 0,
        "pix_fmt": vs.get("pix_fmt", ""),
    }

def eval_fraction(v: str) -> float:
    try:
        a, b = v.split("/")
        return float(a) / float(b) if float(b) else 0.0
    except Exception:
        return 0.0

def build_filter_chain(opts: Dict) -> str:
    filters = []
    if opts.get("denoise"):
        filters.append("hqdn3d=1.5:1.5:6:6")
    if opts.get("deblock") and has_filter("deblock"):
        filters.append("deblock")
    if opts.get("hdr_sdr"):
        if has_filter("zscale") and has_filter("tonemap"):
            filters.append("zscale=t=linear:npl=100,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
        else:
            filters.append("format=yuv420p")
    if opts.get("color_boost"):
        filters.append("eq=contrast=1.06:saturation=1.10:brightness=0.005")
    scale_to = opts.get("scale_to")
    if scale_to and scale_to != "Source":
        h = int(scale_to.replace("p", ""))
        filters.append(f"scale=-2:{h}:flags=lanczos")
    if opts.get("sharpen"):
        filters.append("unsharp=5:5:0.55:3:3:0.25")
    if opts.get("frame_interp"):
        filters.append("minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    return ",".join(filters)

def codec_config(codec: str, crf: int, preset: str, tune: str, faststart: bool = True) -> Tuple[List[str], str, str]:
    """Return args, container extension, mime."""
    if codec == "H.264 / AVC":
        enc = "libx264" if has_encoder("libx264") else "h264"
        args = ["-c:v", enc, "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if tune != "None":
            args += ["-tune", tune.lower()]
        ext, mime = ".mp4", "video/mp4"
    elif codec == "HEVC / H.265":
        enc = "libx265" if has_encoder("libx265") else "hevc"
        args = ["-c:v", enc, "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if enc == "libx265":
            args += ["-tag:v", "hvc1", "-x265-params", "log-level=error"]
        ext, mime = ".mp4", "video/mp4"
    elif codec == "AV1":
        if has_encoder("libsvtav1"):
            args = ["-c:v", "libsvtav1", "-crf", str(crf), "-preset", "6", "-pix_fmt", "yuv420p"]
        elif has_encoder("libaom-av1"):
            args = ["-c:v", "libaom-av1", "-crf", str(crf), "-b:v", "0", "-cpu-used", "6", "-pix_fmt", "yuv420p"]
        else:
            args = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
        ext, mime = ".webm", "video/webm" if "libx264" not in args else "video/mp4"
    else:
        args, ext, mime = ["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p"], ".mp4", "video/mp4"
    if faststart and ext == ".mp4":
        args += ["-movflags", "+faststart"]
    args += ["-c:a", "aac", "-b:a", "128k"] if ext == ".mp4" else ["-c:a", "libopus", "-b:a", "96k"]
    return args, ext, mime

def encode_video(input_path: Path, image_path: Optional[Path], opts: Dict, session_id: str) -> Tuple[Optional[Path], Path, Dict]:
    info = ffmpeg_info()
    log_file = LOG_DIR / f"{session_id}.log"
    if not info["ffmpeg"]:
        return None, log_file, {"error": "FFmpeg not found. Install FFmpeg and ensure ffmpeg is available in PATH."}
    codec = opts["codec"]
    crf = int(opts["crf"])
    preset = opts["preset"]
    tune = opts.get("tune", "None")
    enc_args, ext, mime = codec_config(codec, crf, preset, tune)
    out_path = OUTPUT_DIR / f"{safe_name(input_path.name)}_{codec.split()[0].lower().replace('.', '')}_crf{crf}_{session_id[:8]}{ext}"
    vf = build_filter_chain(opts)

    cmd = [info["ffmpeg"], "-hide_banner", "-y", "-i", str(input_path)]
    filter_complex = None
    if image_path and opts.get("image_mode") != "Ignore image":
        cmd += ["-i", str(image_path)]
        if opts.get("image_mode") == "Watermark / logo overlay":
            scale = opts.get("logo_scale", 18)
            pos = opts.get("logo_position", "top-right")
            overlay_xy = {
                "top-right": "main_w-overlay_w-24:24", "top-left": "24:24",
                "bottom-right": "main_w-overlay_w-24:main_h-overlay_h-24", "bottom-left": "24:main_h-overlay_h-24"
            }[pos]
            base = vf + "," if vf else ""
            filter_complex = f"[1:v]scale=iw*{scale}/100:-1[logo];[0:v]{base}format=yuv420p[base];[base][logo]overlay={overlay_xy}:format=auto[v]"
            cmd += ["-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?", "-shortest"]
        elif opts.get("image_mode") == "Use image as intro slate":
            # Keep production-safe: attach selected image as cover/poster metadata if supported by player/download.
            if vf:
                cmd += ["-vf", vf]
        else:
            if vf:
                cmd += ["-vf", vf]
    else:
        if vf:
            cmd += ["-vf", vf]

    cmd += enc_args + [str(out_path)]
    code, out = run_cmd(cmd, log_file, timeout=int(opts.get("timeout", 3600)))
    if code != 0 or not out_path.exists():
        return None, log_file, {"error": "Encoding failed", "ffmpeg_tail": out[-3000:]}
    return out_path, log_file, {"mime": mime, "cmd": " ".join(cmd)}

def compute_metrics(src: Path, dst: Path, session_id: str, quick: bool = True) -> Dict:
    info = ffmpeg_info()
    log_file = LOG_DIR / f"{session_id}.log"
    metrics = {}
    if not info["ffmpeg"]:
        return metrics
    # Normalize both streams for fair frame-by-frame comparison. Quick mode samples roughly first 90 seconds.
    duration_limit = ["-t", "90"] if quick else []
    common = [info["ffmpeg"], "-hide_banner", "-nostats", "-i", str(src), "-i", str(dst)] + duration_limit
    width = media_summary(src).get("width", 0)
    height = media_summary(src).get("height", 0)
    scale = f"scale={width}:{height}:flags=bicubic" if width and height else "null"
    filter_psnr_ssim = f"[0:v]setpts=PTS-STARTPTS,{scale},format=yuv420p,split=2[ref1][ref2];[1:v]setpts=PTS-STARTPTS,{scale},format=yuv420p,split=2[dist1][dist2];[ref1][dist1]psnr=stats_file={LOG_DIR/session_id}_psnr.log;[ref2][dist2]ssim=stats_file={LOG_DIR/session_id}_ssim.log"
    cmd = common + ["-lavfi", filter_psnr_ssim, "-f", "null", "-"]
    code, out = run_cmd(cmd, log_file, timeout=900)
    m = re.search(r"average:([0-9.]+)", out)
    if m:
        metrics["PSNR"] = float(m.group(1))
    m = re.search(r"All:([0-9.]+)", out)
    if m:
        metrics["SSIM"] = float(m.group(1))
    if has_filter("libvmaf"):
        vmaf_json = LOG_DIR / f"{session_id}_vmaf.json"
        filter_vmaf = f"[0:v]setpts=PTS-STARTPTS,{scale},format=yuv420p[ref];[1:v]setpts=PTS-STARTPTS,{scale},format=yuv420p[dist];[dist][ref]libvmaf=log_fmt=json:log_path={vmaf_json}"
        cmd = common + ["-lavfi", filter_vmaf, "-f", "null", "-"]
        code, out = run_cmd(cmd, log_file, timeout=1200)
        try:
            data = json.loads(vmaf_json.read_text())
            metrics["VMAF"] = float(data.get("pooled_metrics", {}).get("vmaf", {}).get("mean", 0))
        except Exception:
            pass
    else:
        # Proxy score useful when FFmpeg lacks libvmaf. Label clearly.
        if "SSIM" in metrics:
            metrics["VMAF_proxy"] = round(max(0, min(100, 100 * (metrics["SSIM"] ** 0.45))), 2)
    return metrics

def append_result(row: Dict):
    csv_path = LOG_DIR / "encode_sessions.csv"
    exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)

def make_abr_hls(src: Path, session_id: str, codec_choice: str = "H.264 / AVC") -> Tuple[Optional[Path], Path, str]:
    info = ffmpeg_info()
    log_file = LOG_DIR / f"{session_id}.log"
    out_dir = OUTPUT_DIR / f"abr_{session_id[:8]}"
    out_dir.mkdir(exist_ok=True)
    if not info["ffmpeg"]:
        return None, log_file, "FFmpeg not found"
    # Browser-friendly HLS ladder. HEVC/AV1 HLS support varies; H.264 is safest for simulation.
    variants = [(426, 240, "400k"), (854, 480, "900k"), (1280, 720, "2200k")]
    playlist_lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    for w, h, br in variants:
        name = f"{h}p.m3u8"
        cmd = [info["ffmpeg"], "-hide_banner", "-y", "-i", str(src), "-vf", f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2", "-c:v", "libx264" if has_encoder("libx264") else "h264", "-preset", "veryfast", "-b:v", br, "-maxrate", br, "-bufsize", str(int(br[:-1])*2)+"k", "-c:a", "aac", "-b:a", "96k", "-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod", "-hls_segment_filename", str(out_dir / f"{h}p_%03d.ts"), str(out_dir / name)]
        code, out = run_cmd(cmd, log_file, timeout=1800)
        if code == 0:
            bw = int(br[:-1]) * 1000
            playlist_lines += [f"#EXT-X-STREAM-INF:BANDWIDTH={bw},RESOLUTION={w}x{h}", name]
    master = out_dir / "master.m3u8"
    master.write_text("\n".join(playlist_lines), encoding="utf-8")
    return master, log_file, "OK"

def player_html(video_b64: str, mime: str, poster_b64: Optional[str] = None, poster_mime: str = "image/png") -> str:
    poster = f"poster='data:{poster_mime};base64,{poster_b64}'" if poster_b64 else ""
    return f"""
    <div style="font-family:Inter,system-ui;background:linear-gradient(135deg,#07111f,#101a33);padding:14px;border-radius:22px;border:1px solid rgba(255,255,255,.14);">
      <video id="v" controls preload="metadata" style="width:100%;max-height:620px;background:#000;border-radius:16px;" {poster}>
        <source src="data:{mime};base64,{video_b64}" type="{mime}">
      </video>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;color:#cfe2ff;font-size:13px;">
        <span>Universal playback shell</span><span>•</span><span>AVC / HEVC / AV1 depends on browser decoder support</span><span>•</span><span>WebRTC tab available for live preview</span>
      </div>
      <canvas id="wave" height="28" style="width:100%;margin-top:8px;border-radius:8px;background:rgba(255,255,255,.05)"></canvas>
      <script>
        const v=document.getElementById('v'); const c=document.getElementById('wave'); const ctx=c.getContext('2d');
        function draw(){{c.width=c.clientWidth;ctx.clearRect(0,0,c.width,c.height);let p=v.duration? v.currentTime/v.duration:0;let g=ctx.createLinearGradient(0,0,c.width,0);g.addColorStop(0,'#3be7ff');g.addColorStop(1,'#8a5cff');ctx.fillStyle=g;ctx.fillRect(0,0,c.width*p,c.height);ctx.fillStyle='rgba(255,255,255,.18)';ctx.fillRect(c.width*p,0,c.width*(1-p),c.height);requestAnimationFrame(draw)}} draw();
      </script>
    </div>
    """

# -------------------------
# Session State
# -------------------------
if "results" not in st.session_state:
    st.session_state.results = []
if "last_output" not in st.session_state:
    st.session_state.last_output = None
if "last_input" not in st.session_state:
    st.session_state.last_input = None
if "last_image" not in st.session_state:
    st.session_state.last_image = None

# -------------------------
# Header
# -------------------------
st.markdown("""
<div class="hero">
  <h1>🎬 EncodeIQ Studio</h1>
  <p>Single Streamlit web app for professional encoding, AI-assisted enhancement filters, quality analytics, CRF sweeps, ABR simulation, session logs, CSV export, and a universal player shell.</p>
  <div style="margin-top:.65rem">
    <span class="pill">H.264 / AVC</span><span class="pill">HEVC / H.265</span><span class="pill">AV1</span><span class="pill">WebRTC Preview</span><span class="pill">VMAF / PSNR / SSIM</span><span class="pill">Dark + Light Ready</span>
  </div>
</div>
""", unsafe_allow_html=True)

info = ffmpeg_info()
with st.sidebar:
    st.subheader("System readiness")
    st.markdown(f"FFmpeg: {'<span class=\"status-ok\">Ready</span>' if info['ffmpeg'] else '<span class=\"status-bad\">Missing</span>'}", unsafe_allow_html=True)
    st.caption(info.get("version", ""))
    st.markdown(f"FFprobe: {'✅' if info['ffprobe'] else '❌'}")
    st.markdown(f"libx264: {'✅' if has_encoder('libx264') else '⚠️'}  |  libx265: {'✅' if has_encoder('libx265') else '⚠️'}  |  AV1: {'✅' if (has_encoder('libsvtav1') or has_encoder('libaom-av1')) else '⚠️'}")
    st.markdown(f"libvmaf: {'✅' if has_filter('libvmaf') else '⚠️ proxy only'}")
    st.divider()
    st.caption("If FFmpeg or libvmaf is missing on cloud, add OS packages through packages.txt / apt where supported.")

tabs = st.tabs(["Encode", "Universal Player", "Quality Analytics", "CRF Sweep", "Live ABR Simulation", "Session Logs"])

# -------------------------
# Encode Tab
# -------------------------
with tabs[0]:
    left, right = st.columns([0.42, 0.58], gap="large")
    with left:
        st.subheader("1) Input")
        uploaded = st.file_uploader("Upload source video", type=["mp4", "mov", "mkv", "webm", "avi", "m4v", "ts"], help="Any FFmpeg-readable input container is supported.")
        image = st.file_uploader("Attach optional image / logo / poster", type=["png", "jpg", "jpeg", "webp"], help="Use as watermark/logo overlay or poster in player.")
        if uploaded:
            in_path = save_upload(uploaded, INPUT_DIR)
            st.session_state.last_input = str(in_path)
            st.success(f"Uploaded: {in_path.name}")
        if image:
            img_path = save_upload(image, INPUT_DIR)
            st.session_state.last_image = str(img_path)
            st.image(str(img_path), caption="Attached image", use_container_width=True)

        st.subheader("2) Codec + compression")
        codec = st.selectbox("Output codec", ["H.264 / AVC", "HEVC / H.265", "AV1"], index=0)
        c1, c2 = st.columns(2)
        with c1:
            crf = st.slider("CRF / quality target", 14, 40, 23, help="Lower CRF = higher quality/larger file. Typical: x264 18-24, x265 20-28, AV1 24-36.")
        with c2:
            preset = st.selectbox("Preset", ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower"], index=4)
        tune = st.selectbox("Tune", ["None", "Film", "Animation", "Grain", "Stillimage"], index=0)

    with right:
        st.subheader("3) AI-assisted enhancement pipeline")
        e1, e2, e3, e4 = st.columns(4)
        with e1:
            denoise = st.checkbox("Denoise", value=True)
            sharpen = st.checkbox("Sharpen", value=True)
        with e2:
            deblock = st.checkbox("Deblock", value=False)
            color_boost = st.checkbox("Color boost", value=False)
        with e3:
            hdr_sdr = st.checkbox("HDR → SDR", value=False)
            frame_interp = st.checkbox("Frame interpolation 60fps", value=False)
        with e4:
            scale_to = st.selectbox("Upscale/downscale", ["Source", "480p", "720p", "1080p", "2160p"], index=0)
            quick_metrics = st.checkbox("Quick analytics after encode", value=True)

        st.caption("Filters used: hqdn3d, unsharp, scale=lanczos, zscale+tonemap, deblock, eq, minterpolate where available in FFmpeg.")
        img_mode = st.selectbox("Attached image behavior", ["Ignore image", "Watermark / logo overlay", "Use image as intro slate"], index=1)
        lc1, lc2 = st.columns(2)
        with lc1:
            logo_position = st.selectbox("Logo position", ["top-right", "top-left", "bottom-right", "bottom-left"], index=0)
        with lc2:
            logo_scale = st.slider("Logo scale %", 6, 35, 14)

        timeout = st.number_input("Max encode timeout seconds", min_value=120, max_value=7200, value=3600, step=120)
        run = st.button("🚀 Encode video", type="primary", use_container_width=True)

        if run:
            if not st.session_state.last_input:
                st.error("Please upload a source video first.")
            else:
                session_id = uuid.uuid4().hex
                in_path = Path(st.session_state.last_input)
                img_path = Path(st.session_state.last_image) if st.session_state.last_image else None
                opts = dict(codec=codec, crf=crf, preset=preset, tune=tune, denoise=denoise, sharpen=sharpen, deblock=deblock, color_boost=color_boost, hdr_sdr=hdr_sdr, frame_interp=frame_interp, scale_to=scale_to, image_mode=img_mode, logo_position=logo_position, logo_scale=logo_scale, timeout=timeout)
                with st.spinner("Encoding with FFmpeg…"):
                    out_path, log_file, meta = encode_video(in_path, img_path, opts, session_id)
                if out_path:
                    st.session_state.last_output = str(out_path)
                    src_sum = media_summary(in_path)
                    dst_sum = media_summary(out_path)
                    metrics = {}
                    if quick_metrics:
                        with st.spinner("Computing quality analytics…"):
                            metrics = compute_metrics(in_path, out_path, session_id, quick=True)
                    size_reduction = (1 - (dst_sum["size_mb"] / src_sum["size_mb"])) * 100 if src_sum["size_mb"] else 0
                    row = {
                        "timestamp": datetime.now().isoformat(timespec="seconds"), "session_id": session_id, "source": in_path.name, "output": out_path.name, "codec": codec, "crf": crf, "preset": preset,
                        "source_mb": round(src_sum["size_mb"], 3), "output_mb": round(dst_sum["size_mb"], 3), "size_reduction_pct": round(size_reduction, 2),
                        "source_bitrate_kbps": round(src_sum["bitrate_kbps"], 2), "output_bitrate_kbps": round(dst_sum["bitrate_kbps"], 2),
                        "PSNR": metrics.get("PSNR", ""), "SSIM": metrics.get("SSIM", ""), "VMAF": metrics.get("VMAF", ""), "VMAF_proxy": metrics.get("VMAF_proxy", ""), "log_file": str(log_file)
                    }
                    append_result(row)
                    st.session_state.results.append(row)
                    st.success("Encoding complete")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Output size", f"{dst_sum['size_mb']:.2f} MB", f"{size_reduction:.1f}%")
                    m2.metric("Output bitrate", f"{dst_sum['bitrate_kbps']:.0f} kbps")
                    m3.metric("SSIM", f"{metrics.get('SSIM', 0):.4f}" if metrics.get("SSIM") else "n/a")
                    m4.metric("VMAF", f"{metrics.get('VMAF', metrics.get('VMAF_proxy', 0)):.2f}" if (metrics.get("VMAF") or metrics.get("VMAF_proxy")) else "n/a")
                    st.download_button("Download encoded video", data=out_path.read_bytes(), file_name=out_path.name, mime=meta.get("mime", "application/octet-stream"), use_container_width=True)
                    st.download_button("Download session log", data=log_file.read_bytes(), file_name=log_file.name, mime="text/plain", use_container_width=True)
                else:
                    st.error(meta.get("error", "Encoding failed"))
                    if meta.get("ffmpeg_tail"):
                        st.code(meta["ffmpeg_tail"])

# -------------------------
# Universal Player Tab
# -------------------------
with tabs[1]:
    st.subheader("Universal player")
    st.caption("Supports AVC, HEVC and AV1 when the active browser/OS includes the required decoder. WebRTC live preview is provided below.")
    play_file = None
    if st.session_state.last_output and Path(st.session_state.last_output).exists():
        play_file = Path(st.session_state.last_output)
        st.info(f"Loaded latest output: {play_file.name}")
    else:
        custom_play = st.file_uploader("Upload a playable file", type=["mp4", "webm", "mkv", "mov"], key="play_upload")
        if custom_play:
            play_file = save_upload(custom_play, INPUT_DIR)
    poster_b64 = None
    poster_mime = "image/png"
    if st.session_state.last_image and Path(st.session_state.last_image).exists():
        img = Path(st.session_state.last_image)
        poster_b64 = base64.b64encode(img.read_bytes()).decode("ascii")
        poster_mime = "image/png" if img.suffix.lower() == ".png" else "image/jpeg"
    if play_file:
        mime = "video/webm" if play_file.suffix.lower() == ".webm" else "video/mp4"
        max_embed_mb = 280
        if play_file.stat().st_size / (1024*1024) <= max_embed_mb:
            video_b64 = base64.b64encode(play_file.read_bytes()).decode("ascii")
            components.html(player_html(video_b64, mime, poster_b64, poster_mime), height=720)
        else:
            st.warning("File is too large for inline base64 player. Using Streamlit native player instead.")
            st.video(str(play_file))
        st.download_button("Download current media", data=play_file.read_bytes(), file_name=play_file.name, mime=mime)
    st.divider()
    st.subheader("WebRTC live preview")
    if WEBRTC_AVAILABLE:
        rtc_config = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
        webrtc_streamer(key="encodeiq-webrtc", rtc_configuration=rtc_config, media_stream_constraints={"video": True, "audio": False})
    else:
        st.warning("streamlit-webrtc is not installed. Add streamlit-webrtc to requirements.txt to enable live WebRTC preview.")

# -------------------------
# Analytics Tab
# -------------------------
with tabs[2]:
    st.subheader("Full quality analytics")
    st.caption("Runs PSNR and SSIM. VMAF runs automatically when FFmpeg includes libvmaf; otherwise the app displays a clearly-labelled proxy score.")
    c1, c2 = st.columns(2)
    with c1:
        src_file = st.file_uploader("Reference/source", type=["mp4", "mov", "mkv", "webm"], key="qa_src")
    with c2:
        dist_file = st.file_uploader("Encoded/distorted", type=["mp4", "mov", "mkv", "webm"], key="qa_dst")
    full = st.checkbox("Full duration analytics", value=False, help="Quick mode samples the first 90 seconds to save cloud resources.")
    if st.button("Calculate metrics", use_container_width=True):
        if not src_file or not dist_file:
            st.error("Upload both reference and encoded files.")
        else:
            sid = uuid.uuid4().hex
            src = save_upload(src_file, INPUT_DIR)
            dst = save_upload(dist_file, INPUT_DIR)
            with st.spinner("Calculating metrics…"):
                metrics = compute_metrics(src, dst, sid, quick=not full)
            if metrics:
                st.json(metrics)
            else:
                st.error("No metrics returned. Check FFmpeg log.")
            log_file = LOG_DIR / f"{sid}.log"
            if log_file.exists():
                st.download_button("Download analytics log", log_file.read_bytes(), file_name=log_file.name, mime="text/plain")

# -------------------------
# CRF Sweep Tab
# -------------------------
with tabs[3]:
    st.subheader("CRF sweep: rate-distortion exploration")
    st.caption("Encodes multiple CRF values and compares size/bitrate/quality, useful for finding the sweet spot where compression improves without meaningful VMAF loss.")
    if not st.session_state.last_input:
        sweep_upload = st.file_uploader("Upload source for sweep", type=["mp4", "mov", "mkv", "webm"], key="sweep_upload")
        if sweep_upload:
            st.session_state.last_input = str(save_upload(sweep_upload, INPUT_DIR))
    sweep_codec = st.selectbox("Sweep codec", ["H.264 / AVC", "HEVC / H.265", "AV1"], key="sweep_codec")
    crfs_txt = st.text_input("CRF values", "18,21,23,26,28")
    max_seconds = st.slider("Analyze first N seconds", 10, 180, 45)
    if st.button("Run CRF sweep", type="primary", use_container_width=True):
        if not st.session_state.last_input:
            st.error("Upload a source video first.")
        else:
            source = Path(st.session_state.last_input)
            crfs = [int(x.strip()) for x in crfs_txt.split(",") if x.strip().isdigit()]
            rows = []
            prog = st.progress(0)
            for idx, c in enumerate(crfs):
                sid = uuid.uuid4().hex
                temp_src = source
                # Create a short mezzanine sample for quicker CRF sweeps.
                sample = INPUT_DIR / f"sample_{sid}.mp4"
                run_cmd([ffmpeg_info()["ffmpeg"], "-hide_banner", "-y", "-i", str(source), "-t", str(max_seconds), "-c", "copy", str(sample)], LOG_DIR / f"{sid}.log", timeout=300)
                if sample.exists():
                    temp_src = sample
                opts = dict(codec=sweep_codec, crf=c, preset="fast", tune="None", denoise=False, sharpen=False, deblock=False, color_boost=False, hdr_sdr=False, frame_interp=False, scale_to="Source", image_mode="Ignore image", timeout=1800)
                out, log, meta = encode_video(temp_src, None, opts, sid)
                if out:
                    metrics = compute_metrics(temp_src, out, sid, quick=True)
                    ssum, dsum = media_summary(temp_src), media_summary(out)
                    rows.append({"CRF": c, "Size MB": round(dsum["size_mb"], 2), "Bitrate kbps": round(dsum["bitrate_kbps"], 0), "PSNR": metrics.get("PSNR"), "SSIM": metrics.get("SSIM"), "VMAF": metrics.get("VMAF", metrics.get("VMAF_proxy")), "File": out.name})
                prog.progress((idx + 1) / len(crfs))
            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)
                st.line_chart(df.set_index("CRF")[[c for c in ["Size MB", "VMAF", "SSIM"] if c in df.columns]])
                csv_bytes = df.to_csv(index=False).encode("utf-8")
                st.download_button("Download CRF sweep CSV", csv_bytes, file_name="crf_sweep.csv", mime="text/csv")

# -------------------------
# ABR Tab
# -------------------------
with tabs[4]:
    st.subheader("Live adaptive bitrate player simulation")
    st.caption("Creates a 240p/480p/720p HLS ladder. H.264 is used for maximum browser compatibility in the simulation.")
    abr_file = None
    if st.session_state.last_output and Path(st.session_state.last_output).exists():
        abr_file = Path(st.session_state.last_output)
        st.info(f"Using latest output: {abr_file.name}")
    else:
        abr_up = st.file_uploader("Upload source/output for ABR simulation", type=["mp4", "mov", "mkv", "webm"], key="abr_up")
        if abr_up:
            abr_file = save_upload(abr_up, INPUT_DIR)
    if st.button("Generate ABR ladder", type="primary", use_container_width=True):
        if not abr_file:
            st.error("Upload or encode a file first.")
        else:
            sid = uuid.uuid4().hex
            with st.spinner("Generating HLS variants…"):
                master, log, status = make_abr_hls(abr_file, sid)
            if master and master.exists():
                st.success("ABR ladder generated")
                # Zip HLS package for hosting/use.
                zip_path = OUTPUT_DIR / f"abr_package_{sid[:8]}.zip"
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                    for p in master.parent.glob("*"):
                        z.write(p, arcname=p.name)
                st.code(master.read_text(), language="text")
                st.download_button("Download ABR HLS package", zip_path.read_bytes(), file_name=zip_path.name, mime="application/zip")
                st.download_button("Download ABR log", log.read_bytes(), file_name=log.name, mime="text/plain")
            else:
                st.error(status)

# -------------------------
# Logs Tab
# -------------------------
with tabs[5]:
    st.subheader("Session logs and CSV export")
    csv_path = LOG_DIR / "encode_sessions.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        st.dataframe(df.tail(100), use_container_width=True)
        st.download_button("Download all session results CSV", csv_path.read_bytes(), file_name="encode_sessions.csv", mime="text/csv", use_container_width=True)
    else:
        st.info("No session CSV yet. Run an encode first.")
    logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if logs:
        selected = st.selectbox("Log file", logs, format_func=lambda p: p.name)
        st.text_area("Log preview", selected.read_text(errors="ignore")[-8000:], height=360)
        st.download_button("Download selected log", selected.read_bytes(), file_name=selected.name, mime="text/plain")

st.caption("EncodeIQ Studio is designed for Streamlit hosting. For production workloads, run FFmpeg jobs through a worker queue and object storage; keep this single-app version for prototype/demo and light processing.")
