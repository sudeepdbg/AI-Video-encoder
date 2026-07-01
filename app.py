"""
VideoForge Studio V3.1
Professional Video Optimization Platform
Streamlit single-file app
"""

import os
import re
import json
import time
import uuid
import shutil
import subprocess
import zipfile
import base64
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_webrtc import webrtc_streamer, RTCConfiguration
    WEBRTC_AVAILABLE = True
except Exception:
    WEBRTC_AVAILABLE = False


# ============================================================
# Paths + cleanup
# ============================================================

WORK = Path("work")
IN_DIR = WORK / "inputs"
OUT_DIR = WORK / "outputs"
LOG_DIR = WORK / "logs"

for d in (IN_DIR, OUT_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)


def cleanup_old_files(folder: Path, max_age_hours: int = 12):
    cutoff = time.time() - max_age_hours * 3600
    for p in folder.glob("*"):
        try:
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink()
            elif p.is_dir() and p.stat().st_mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass


cleanup_old_files(IN_DIR, max_age_hours=12)
cleanup_old_files(OUT_DIR, max_age_hours=12)
cleanup_old_files(LOG_DIR, max_age_hours=48)

TARGET_PROFILE = "🎯 Target Size (2-pass)"


# ============================================================
# Page config + light UI
# ============================================================

st.set_page_config(
    page_title="VideoForge Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">

<style>
html, body, [data-testid="stAppViewContainer"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: linear-gradient(180deg, #f7faff 0%, #eef4fb 100%) !important;
    color: #0f172a !important;
}

[data-testid="stHeader"] {
    background: rgba(247,250,255,.9) !important;
    backdrop-filter: blur(10px);
}

[data-testid="stSidebar"] {
    display: none !important;
}

.block-container {
    padding-top: 1.4rem;
    padding-bottom: 3rem;
    max-width: 1440px;
}

* {
    font-family: 'Inter', -apple-system, sans-serif !important;
}

h1, h2, h3, h4 {
    letter-spacing: -0.02em;
    color: #0f172a;
    font-weight: 800;
}

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {
    visibility: hidden !important;
    height: 0 !important;
}

.hero {
    background: linear-gradient(135deg, #ffffff 0%, #f0f6ff 100%);
    border: 1px solid #dbeafe;
    border-radius: 24px;
    padding: 26px 30px;
    box-shadow: 0 12px 36px rgba(59,130,246,.10);
    margin-bottom: 22px;
}

.hero h1 {
    font-size: 2.2rem;
    margin: 0;
    font-weight: 900;
}

.hero p {
    color: #475569;
    margin: 8px 0 0;
    font-size: 1rem;
    line-height: 1.55;
}

.badge {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    margin: 6px 6px 0 0;
    border-radius: 999px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1d4ed8;
    font-weight: 600;
    font-size: .8rem;
}

.section-title {
    font-size: .72rem;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: #64748b;
    font-weight: 800;
    margin: 24px 0 12px;
}

.metric-card {
    background: #fff;
    border: 1px solid #e5edf5;
    border-radius: 16px;
    padding: 16px;
    box-shadow: 0 4px 14px rgba(15,23,42,.04);
}

.metric-label {
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .12em;
    color: #64748b;
    font-weight: 700;
}

.metric-value {
    font-size: 1.5rem;
    font-weight: 800;
    color: #0f172a;
    margin-top: 4px;
}

.metric-sub {
    font-size: .8rem;
    color: #64748b;
    margin-top: 2px;
}

.info-strip {
    background: #dbeafe;
    color: #1e3a8a;
    border: 1px solid #bfdbfe;
    border-radius: 12px;
    padding: 12px 16px;
    font-weight: 600;
    margin: 10px 0;
    font-size: .9rem;
}

.warn-strip {
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #fde68a;
    border-radius: 12px;
    padding: 12px 16px;
    font-weight: 600;
    margin: 10px 0;
    font-size: .9rem;
}

.ok-strip {
    background: #d1fae5;
    color: #065f46;
    border: 1px solid #a7f3d0;
    border-radius: 12px;
    padding: 12px 16px;
    font-weight: 600;
    margin: 10px 0;
    font-size: .9rem;
}

.compare-input {
    background: linear-gradient(135deg,#f1f5f9,#e2e8f0);
    border: 1px solid #cbd5e1;
    border-radius: 16px;
    padding: 18px;
}

.compare-output {
    background: linear-gradient(135deg,#dbeafe,#bfdbfe);
    border: 1px solid #93c5fd;
    border-radius: 16px;
    padding: 18px;
}

.compare-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid rgba(0,0,0,.06);
    font-size: .9rem;
}

.compare-row:last-child {
    border-bottom: 0;
}

.compare-label {
    color: #64748b;
    font-weight: 600;
}

.compare-val {
    color: #0f172a;
    font-weight: 700;
}

.savings-card {
    background: linear-gradient(135deg, #059669, #10b981);
    color: white;
    border-radius: 18px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 10px 26px rgba(5,150,105,.25);
}

.savings-value {
    font-size: 2.4rem;
    font-weight: 900;
    line-height: 1;
}

.savings-label {
    font-size: .8rem;
    opacity: .9;
    text-transform: uppercase;
    letter-spacing: .14em;
    margin-top: 6px;
}

.stButton>button {
    border-radius: 12px !important;
    border: 0 !important;
    background: linear-gradient(135deg,#2563eb,#3b82f6) !important;
    color: #fff !important;
    font-weight: 700 !important;
    box-shadow: 0 8px 18px rgba(37,99,235,.22);
    padding: 10px 18px !important;
}

.stDownloadButton>button {
    border-radius: 12px !important;
    font-weight: 700 !important;
}

[data-testid="stMetric"] {
    background: #fff;
    border: 1px solid #e5edf5;
    border-radius: 14px;
    padding: 14px;
}

[data-testid="stMetricValue"],
[data-testid="stMetricLabel"],
[data-testid="stMetricDelta"] {
    color: #0f172a !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    background: #fff;
    border: 1px solid #e5edf5;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 600;
    color: #0f172a;
}

.stTabs [aria-selected="true"] {
    background: #eff6ff !important;
    color: #1d4ed8 !important;
    border-color: #93c5fd !important;
}

video {
    border-radius: 14px;
    background: #000;
}

hr {
    border-color: #e5edf5;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff !important;
    border: 1px solid #e5edf5 !important;
    border-radius: 18px !important;
    box-shadow: 0 8px 22px rgba(15,23,42,.04);
}

label,
[data-testid="stWidgetLabel"] p,
.stCheckbox p,
.stRadio p {
    color: #1e293b !important;
    font-weight: 600 !important;
}

[data-testid="stMarkdownContainer"] p {
    color: inherit;
}

.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    background: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 10px !important;
}

.stSelectbox div[data-baseweb="select"] > div {
    background: #ffffff !important;
    color: #0f172a !important;
    border-radius: 10px !important;
}

div[data-baseweb="popover"] div[data-baseweb="menu"],
ul[role="listbox"],
li[role="option"] {
    background: #ffffff !important;
    color: #0f172a !important;
}

li[role="option"]:hover,
li[aria-selected="true"] {
    background: #eff6ff !important;
}

[data-baseweb="tooltip"] {
    background: #0f172a !important;
    color: #ffffff !important;
}

[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e5edf5 !important;
    border-radius: 16px !important;
    overflow: hidden;
}

[data-testid="stExpander"] summary {
    color: #0f172a !important;
    font-weight: 700 !important;
}

[data-testid="stFileUploaderDropzone"] {
    background: #f8fafc !important;
    border: 1.5px dashed #cbd5e1 !important;
    border-radius: 14px !important;
}

[data-testid="stFileUploaderDropzone"] * {
    color: #475569 !important;
}

[data-testid="stDataFrame"],
[data-testid="stTable"] {
    background: #ffffff !important;
    border-radius: 12px;
    overflow: hidden;
}

[data-testid="stAlert"] {
    border-radius: 12px !important;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# FFmpeg detection
# ============================================================

@st.cache_resource(show_spinner=False)
def ffinfo() -> Dict[str, str]:
    ff = shutil.which("ffmpeg")
    fp = shutil.which("ffprobe")

    d = {
        "ffmpeg": ff or "",
        "ffprobe": fp or "",
        "version": "",
        "encoders": "",
        "filters": "",
    }

    if ff:
        try:
            d["version"] = subprocess.check_output(
                [ff, "-version"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=5,
            ).splitlines()[0]

            d["encoders"] = subprocess.check_output(
                [ff, "-hide_banner", "-encoders"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=8,
            )

            d["filters"] = subprocess.check_output(
                [ff, "-hide_banner", "-filters"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=8,
            )

        except Exception as e:
            d["version"] = f"detection error: {e}"

    return d


def has_encoder(name: str) -> bool:
    encoders = ffinfo().get("encoders", "") or ""
    return bool(name) and bool(re.search(rf"\b{re.escape(name)}\b", encoders))


def has_filter(name: str) -> bool:
    filters = ffinfo().get("filters", "") or ""
    return bool(name) and bool(re.search(rf"\b{re.escape(name)}\b", filters))


# ============================================================
# File utilities
# ============================================================

def clean(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(name).stem)[:70] or "video"


def save_upload(uploaded, folder: Path) -> Optional[Path]:
    if not uploaded:
        return None

    ext = Path(uploaded.name).suffix.lower()
    p = folder / f"{int(time.time())}_{clean(uploaded.name)}{ext}"
    p.write_bytes(uploaded.getbuffer())
    return p


def upload_identity(uploaded) -> Optional[str]:
    if not uploaded:
        return None
    return f"{uploaded.name}:{uploaded.size}"


@st.cache_data(show_spinner=False)
def probe_cached(path_str: str, mtime: float, size: int) -> Dict[str, Any]:
    if not ffinfo()["ffprobe"]:
        return {}

    try:
        out = subprocess.check_output(
            [
                ffinfo()["ffprobe"],
                "-v", "error",
                "-show_streams",
                "-show_format",
                "-print_format", "json",
                path_str,
            ],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=25,
        )
        return json.loads(out)
    except Exception:
        return {}


def probe(p: Path) -> Dict[str, Any]:
    try:
        st_info = p.stat()
        return probe_cached(str(p), st_info.st_mtime, st_info.st_size)
    except Exception:
        return {}


def frac(v: str) -> float:
    try:
        a, b = v.split("/")
        return round(float(a) / float(b), 3) if float(b) else 0.0
    except Exception:
        return 0.0


def infer_bit_depth(stream: Dict[str, Any]) -> int:
    raw = stream.get("bits_per_raw_sample")
    if raw:
        try:
            return int(raw)
        except Exception:
            pass

    pix = (stream.get("pix_fmt") or "").lower()

    if "16" in pix or pix.startswith("p016"):
        return 16
    if "12" in pix:
        return 12
    if "10" in pix or pix.startswith("p010"):
        return 10

    return 8


def media(p: Path) -> Dict[str, Any]:
    d = probe(p)
    fmt = d.get("format", {}) if d else {}

    v, a = {}, {}
    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and not v:
            v = s
        if s.get("codec_type") == "audio" and not a:
            a = s

    size = p.stat().st_size if p.exists() else int(fmt.get("size", 0) or 0)

    return {
        "duration": float(fmt.get("duration", 0) or 0),
        "size_mb": size / 1048576,
        "size_bytes": size,
        "bitrate_kbps": int(fmt.get("bit_rate", 0) or 0) / 1000,
        "width": int(v.get("width", 0) or 0),
        "height": int(v.get("height", 0) or 0),
        "fps": frac(v.get("avg_frame_rate", "0/1")),
        "vcodec": v.get("codec_name", "unknown"),
        "pix_fmt": v.get("pix_fmt", ""),
        "color_space": v.get("color_space", "") or "",
        "color_transfer": v.get("color_transfer", "") or "",
        "color_primaries": v.get("color_primaries", "") or "",
        "bit_depth": infer_bit_depth(v),
        "has_audio": bool(a),
        "acodec": a.get("codec_name", ""),
        "channels": int(a.get("channels", 0) or 0),
        "sample_rate": int(a.get("sample_rate", 0) or 0),
    }


# ============================================================
# Source analysis
# ============================================================

def detect_hdr(meta: Dict[str, Any]) -> bool:
    transfer = (meta.get("color_transfer") or "").lower()
    primaries = (meta.get("color_primaries") or "").lower()
    color_space = (meta.get("color_space") or "").lower()

    if any(k in transfer for k in ["smpte2084", "arib-std-b67", "pq", "hlg"]):
        return True

    if "bt2020" in primaries and any(k in transfer for k in ["smpte2084", "arib-std-b67"]):
        return True

    if "bt2020" in color_space and any(k in transfer for k in ["smpte2084", "arib-std-b67"]):
        return True

    return False


def recommend_interpolation(meta: Dict[str, Any]) -> Tuple[bool, str]:
    fps = meta.get("fps", 0)

    if fps >= 50:
        return False, f"Source is already {fps:.2f} fps. Interpolation is not recommended."
    if fps < 24:
        return True, f"Source is {fps:.2f} fps. Interpolation can improve smoothness."

    return True, f"Source is {fps:.2f} fps. Interpolation is optional."


# ============================================================
# Profiles
# ============================================================

PROFILES = {
    "📦 Smallest File": {
        "desc": "Maximum compression for storage/upload. Higher CRF, smaller file, lower visual fidelity.",
        "av1": {"crf": 38, "preset": "6", "mbr_720p": 1500, "mbr_1080p": 2500},
        "hevc": {"crf": 30, "preset": "medium"},
        "h264": {"crf": 30, "preset": "medium"},
        "audio_aac": "96k",
        "audio_opus": "64k",
        "default_codec": "AV1",
    },
    "⚖️ Balanced": {
        "desc": "Recommended default. Good compression with strong visual quality.",
        "av1": {"crf": 34, "preset": "6", "mbr_720p": 2200, "mbr_1080p": 3500},
        "hevc": {"crf": 27, "preset": "medium"},
        "h264": {"crf": 26, "preset": "medium"},
        "audio_aac": "128k",
        "audio_opus": "96k",
        "default_codec": "AV1",
    },
    "🎥 High Quality": {
        "desc": "Visually high-quality output. Lower CRF, larger file.",
        "av1": {"crf": 28, "preset": "5", "mbr_720p": 3500, "mbr_1080p": 6000},
        "hevc": {"crf": 22, "preset": "slow"},
        "h264": {"crf": 20, "preset": "slow"},
        "audio_aac": "192k",
        "audio_opus": "128k",
        "default_codec": "HEVC (H.265)",
    },
    "🏆 Archive Master": {
        "desc": "Near-lossless archive. Very large files.",
        "av1": {"crf": 22, "preset": "4", "mbr_720p": 0, "mbr_1080p": 0},
        "hevc": {"crf": 18, "preset": "slow"},
        "h264": {"crf": 16, "preset": "slow"},
        "audio_aac": "256k",
        "audio_opus": "160k",
        "default_codec": "HEVC (H.265)",
    },
    "⚡ Fast Encode": {
        "desc": "Speed-optimized H.264 for quick delivery.",
        "av1": {"crf": 35, "preset": "8", "mbr_720p": 2500, "mbr_1080p": 4000},
        "hevc": {"crf": 28, "preset": "veryfast"},
        "h264": {"crf": 26, "preset": "veryfast"},
        "audio_aac": "128k",
        "audio_opus": "96k",
        "default_codec": "AVC (H.264)",
    },
    "📱 Social Media": {
        "desc": "Optimized for social and mobile platforms.",
        "av1": {"crf": 32, "preset": "6", "mbr_720p": 2500, "mbr_1080p": 4500},
        "hevc": {"crf": 26, "preset": "fast"},
        "h264": {"crf": 24, "preset": "fast"},
        "audio_aac": "128k",
        "audio_opus": "96k",
        "default_codec": "AVC (H.264)",
    },
    TARGET_PROFILE: {
        "desc": "Hit an exact output file size using real two-pass bitrate encoding. Best for fixed upload caps.",
        "audio_aac": "128k",
        "audio_opus": "96k",
        "default_codec": "AVC (H.264)",
    },
}


def map_slider_to_profile(goal: int) -> str:
    if goal <= 20:
        return "🏆 Archive Master"
    if goal <= 40:
        return "🎥 High Quality"
    if goal <= 65:
        return "⚖️ Balanced"
    if goal <= 85:
        return "📱 Social Media"
    return "📦 Smallest File"


# ============================================================
# Filter chain
# ============================================================

def build_filter_chain(opts: Dict[str, Any], src_meta: Dict[str, Any]) -> str:
    f: List[str] = []

    if opts.get("denoise"):
        f.append("hqdn3d=2:2:4:4")

    if opts.get("deblock") and has_filter("deblock"):
        f.append("deblock")

    if opts.get("hdr_sdr") and detect_hdr(src_meta):
        if has_filter("zscale") and has_filter("tonemap"):
            f.append(
                "zscale=transfer=linear:npl=100,"
                "tonemap=tonemap=hable:desat=0,"
                "zscale=primaries=bt709:transfer=bt709:matrix=bt709:range=tv,"
                "format=yuv420p"
            )
        else:
            f.append("format=yuv420p")

    if opts.get("color"):
        f.append("eq=contrast=1.06:saturation=1.10")

    scale_to = opts.get("scale_to", "Source")
    if scale_to and scale_to != "Source":
        h = int(scale_to.replace("p", ""))
        f.append(f"scale=-2:{h}:flags=lanczos")

    if opts.get("sharpen"):
        f.append("unsharp=5:5:0.4:3:3:0.2")

    if opts.get("interp") and src_meta.get("fps", 0) < 50:
        f.append("minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")

    return ",".join(f)


# ============================================================
# Codec args
# ============================================================

def codec_args(
    codec: str,
    crf: int,
    preset: str,
    profile: Dict[str, Any],
    src_meta: Dict[str, Any],
) -> Tuple[List[str], str, str, str, str]:
    width = src_meta.get("width", 1280)
    mbr_key = "mbr_1080p" if width >= 1500 else "mbr_720p"

    if codec == "AVC (H.264)":
        enc = "libx264" if has_encoder("libx264") else "h264"
        args = [
            "-c:v", enc,
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", profile["audio_aac"],
            "-movflags", "+faststart",
        ]
        return args, ".mp4", "video/mp4", enc, ""

    if codec == "HEVC (H.265)":
        enc = "libx265" if has_encoder("libx265") else "hevc"
        args = [
            "-c:v", enc,
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", profile["audio_aac"],
            "-movflags", "+faststart",
        ]
        if enc == "libx265":
            args += ["-tag:v", "hvc1", "-x265-params", "log-level=error:repeat-headers=1"]
        return args, ".mp4", "video/mp4", enc, ""

    av1_cfg = profile["av1"]
    mbr = av1_cfg.get(mbr_key, 0)

    if has_encoder("libsvtav1"):
        args = [
            "-c:v", "libsvtav1",
            "-crf", str(crf),
            "-preset", str(av1_cfg["preset"]),
            "-pix_fmt", "yuv420p",
            "-c:a", "libopus",
            "-b:a", profile["audio_opus"],
        ]

        if mbr and mbr > 0:
            args += ["-maxrate", f"{mbr}k", "-bufsize", f"{mbr * 2}k"]

        return args, ".webm", "video/webm", "libsvtav1", ""

    if has_encoder("libaom-av1"):
        args = [
            "-c:v", "libaom-av1",
            "-crf", str(crf),
            "-b:v", "0",
            "-cpu-used", "6",
            "-row-mt", "1",
            "-pix_fmt", "yuv420p",
            "-c:a", "libopus",
            "-b:a", profile["audio_opus"],
        ]
        return args, ".webm", "video/webm", "libaom-av1", ""

    fallback_profile = profile
    args, ext, mime, actual, _ = codec_args(
        "AVC (H.264)",
        crf,
        "medium" if preset not in ["veryfast", "fast", "medium", "slow"] else preset,
        fallback_profile,
        src_meta,
    )
    return args, ext, mime, actual, "AV1 encoder unavailable. Fell back to H.264."


# ============================================================
# Estimator
# ============================================================

def estimate_output(src_meta: Dict[str, Any], codec: str, crf: int, enhancements: Dict[str, Any]) -> Dict[str, Any]:
    duration = src_meta.get("duration", 0)
    height = src_meta.get("height", 720)
    src_bitrate = src_meta.get("bitrate_kbps", 0) or 2000

    eff = {
        "AV1": 0.45,
        "HEVC (H.265)": 0.60,
        "AVC (H.264)": 0.85,
    }.get(codec, 0.85)

    crf_factor = 2 ** ((28 - crf) / 6.0) if crf > 0 else 1.0
    enh_factor = 1.0

    if enhancements.get("sharpen"):
        enh_factor *= 1.10
    if enhancements.get("color"):
        enh_factor *= 1.05
    if enhancements.get("interp") and src_meta.get("fps", 0) < 50:
        enh_factor *= 1.7
    if enhancements.get("scale_to", "Source") != "Source":
        target_h = int(enhancements["scale_to"].replace("p", ""))
        enh_factor *= max(0.4, target_h / max(height, 1))

    est_bitrate = max(150, src_bitrate * eff * crf_factor * enh_factor)
    est_size_mb = (est_bitrate * 1000 * duration) / 8 / 1048576 if duration else 0

    speed_mult = {
        "AV1": 4.5,
        "HEVC (H.265)": 2.2,
        "AVC (H.264)": 1.0,
    }.get(codec, 1.0)

    if enhancements.get("interp") and src_meta.get("fps", 0) < 50:
        speed_mult *= 2.5

    if enhancements.get("scale_to", "Source") in ["1080p", "2160p"]:
        speed_mult *= 1.6

    est_time_sec = duration * speed_mult * 0.5

    return {
        "est_bitrate_kbps": int(est_bitrate),
        "est_size_mb": round(est_size_mb, 2),
        "est_time_sec": int(est_time_sec),
        "expected_savings_pct": round(
            max(0, (1 - est_size_mb / max(src_meta.get("size_mb", 0.001), 0.001)) * 100),
            1,
        ),
    }


# ============================================================
# Target size bitrate
# ============================================================

def bitrate_from_target_size(
    duration_sec: float,
    target_mb: float,
    audio_kbps: int = 128,
    overhead_pct: float = 2.0,
) -> int:
    if duration_sec <= 0 or target_mb <= 0:
        return 0

    total_kbits = target_mb * 8192.0
    total_kbits *= 1 - overhead_pct / 100.0

    audio_kbits = audio_kbps * duration_sec
    video_kbits = total_kbits - audio_kbits

    if video_kbits <= 0:
        return 0

    return max(100, int(video_kbits / duration_sec))


# ============================================================
# FFmpeg runners
# ============================================================

def _run_encode_pass(
    cmd: List[str],
    duration: float,
    log: Path,
    cb=None,
    phase: Tuple[float, float] = (0.0, 1.0),
    label: str = "Encoding",
) -> Tuple[int, List[str]]:
    lines: List[str] = []
    lo, hi = phase
    log.parent.mkdir(parents=True, exist_ok=True)

    with log.open("a", encoding="utf-8") as f:
        f.write("\n\n$ " + " ".join(map(str, cmd)) + "\n")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    last = lo

    assert proc.stderr is not None

    for line in proc.stderr:
        lines.append(line.rstrip())
        with log.open("a", encoding="utf-8") as f:
            f.write(line)

        m = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
        if m and cb and duration > 0:
            sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            pct = lo + (hi - lo) * min(max(sec / duration, 0.0), 1.0)
            pct = max(pct, last)
            last = pct

            try:
                cb(pct, f"{label}… {pct * 100:.0f}%")
            except Exception:
                pass

    rc = proc.wait()

    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n[exit] {rc}\n")

    return rc, lines


def run_ffmpeg(cmd: List[str], log: Path, timeout: int = 900) -> str:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )

        with log.open("a", encoding="utf-8") as f:
            f.write("\n$ " + " ".join(map(str, cmd)) + "\n" + (p.stdout or ""))

        return p.stdout or ""

    except Exception as e:
        return str(e)


# ============================================================
# Encoding
# ============================================================

def encode_video(
    src: Path,
    logo: Optional[Path],
    opts: Dict[str, Any],
    src_meta: Dict[str, Any],
    sid: str,
    cb=None,
) -> Tuple[Optional[Path], Path, Dict[str, Any]]:
    log = LOG_DIR / f"{sid}.log"
    info = ffinfo()

    if not info["ffmpeg"]:
        return None, log, {"error": "FFmpeg missing. Ensure packages.txt contains `ffmpeg` and redeploy."}

    profile = PROFILES[opts["profile"]]
    codec = opts["codec"]
    crf = int(opts["crf"])
    preset = str(opts["preset"])

    args, ext, mime, actual_encoder, warning = codec_args(codec, crf, preset, profile, src_meta)

    codec_label = actual_encoder.replace("lib", "").replace("-", "")
    out = OUT_DIR / f"{clean(src.name)}_{codec_label}_crf{crf}_{sid[:8]}{ext}"

    vf = build_filter_chain(opts, src_meta)
    cmd = [info["ffmpeg"], "-hide_banner", "-y", "-i", str(src)]

    if logo and logo.exists() and opts.get("image_mode") == "Watermark / logo overlay":
        cmd += ["-i", str(logo)]

        pos = {
            "Top right": "main_w-overlay_w-24:24",
            "Top left": "24:24",
            "Bottom right": "main_w-overlay_w-24:main_h-overlay_h-24",
            "Bottom left": "24:main_h-overlay_h-24",
        }[opts.get("logo_pos", "Top right")]

        base = vf + "," if vf else ""
        fc = (
            f"[1:v]scale=iw*{opts.get('logo_scale', 14)}/100:-1[logo];"
            f"[0:v]{base}format=yuv420p[base];"
            f"[base][logo]overlay={pos}:format=auto[v]"
        )

        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-shortest"]

    elif vf:
        cmd += ["-vf", vf]

    cmd += args + [str(out)]

    duration = max(src_meta.get("duration", 0.001), 0.001)
    rc, lines = _run_encode_pass(cmd, duration, log, cb, phase=(0.0, 1.0), label="Encoding")

    if cb:
        cb(1.0, "Encoding complete")

    if rc != 0 or not out.exists():
        return None, log, {"error": "Encoding failed", "tail": "\n".join(lines[-120:])}

    return out, log, {
        "mime": mime,
        "actual_encoder": actual_encoder,
        "warning": warning,
    }


def encode_two_pass(
    src: Path,
    opts: Dict[str, Any],
    src_meta: Dict[str, Any],
    sid: str,
    cb=None,
) -> Tuple[Optional[Path], Path, Dict[str, Any]]:
    log = LOG_DIR / f"{sid}.log"
    info = ffinfo()

    if not info["ffmpeg"]:
        return None, log, {"error": "FFmpeg missing. Ensure packages.txt contains `ffmpeg` and redeploy."}

    duration = src_meta.get("duration", 0)

    if duration <= 0:
        return None, log, {"error": "Could not determine source duration. Target-size mode needs known duration."}

    codec = opts.get("codec", "AVC (H.264)")
    preset = opts.get("preset", "medium")
    target_mb = float(opts.get("target_mb", 25))
    audio_kbps = int(opts.get("audio_kbps", 128))

    v_kbps = bitrate_from_target_size(duration, target_mb, audio_kbps)

    if v_kbps <= 0:
        return None, log, {
            "error": "Target size is too small for this duration plus audio bitrate. Raise target size or lower audio bitrate."
        }

    warning = ""

    if codec == "HEVC (H.265)" and has_encoder("libx265"):
        venc, ext, acodec = "libx265", ".mp4", "aac"
    elif codec == "AV1" and has_encoder("libaom-av1"):
        venc, ext, acodec = "libaom-av1", ".webm", "libopus"
    else:
        if codec != "AVC (H.264)":
            warning = f"{codec} target-size encoder unavailable. Fell back to H.264."
        venc, ext, acodec = ("libx264" if has_encoder("libx264") else "h264"), ".mp4", "aac"

    mime = "video/webm" if ext == ".webm" else "video/mp4"
    out = OUT_DIR / f"{clean(src.name)}_target{int(target_mb)}mb_{venc}_{sid[:8]}{ext}"
    passlog = str(LOG_DIR / f"{sid}_2pass")

    vf = build_filter_chain(opts, src_meta)

    base = [info["ffmpeg"], "-hide_banner", "-y", "-i", str(src)]

    if vf:
        base += ["-vf", vf]

    v_args = ["-c:v", venc, "-b:v", f"{v_kbps}k", "-passlogfile", passlog]

    if venc in ("libx264", "libx265"):
        v_args += ["-preset", preset]
    elif venc == "libaom-av1":
        v_args += ["-cpu-used", "6", "-row-mt", "1"]

    cmd1 = base + v_args + ["-an", "-pass", "1", "-f", "null", os.devnull]
    rc1, lines1 = _run_encode_pass(
        cmd1,
        duration,
        log,
        cb,
        phase=(0.0, 0.45),
        label="Pass 1/2",
    )

    if rc1 != 0:
        return None, log, {
            "error": "Two-pass encode failed on pass 1.",
            "tail": "\n".join(lines1[-120:]),
        }

    cmd2 = base + v_args + [
        "-pass", "2",
        "-pix_fmt", "yuv420p",
        "-c:a", acodec,
        "-b:a", f"{audio_kbps}k",
    ]

    if venc == "libx265":
        cmd2 += ["-tag:v", "hvc1"]
    if ext == ".mp4":
        cmd2 += ["-movflags", "+faststart"]

    cmd2 += [str(out)]

    rc2, lines2 = _run_encode_pass(
        cmd2,
        duration,
        log,
        cb,
        phase=(0.45, 1.0),
        label="Pass 2/2",
    )

    if cb:
        cb(1.0, "Two-pass encode complete")

    for pf in LOG_DIR.glob(f"{sid}_2pass*"):
        try:
            pf.unlink()
        except Exception:
            pass

    if rc2 != 0 or not out.exists():
        return None, log, {
            "error": "Two-pass encode failed on pass 2.",
            "tail": "\n".join(lines2[-120:]),
        }

    return out, log, {
        "mime": mime,
        "target_video_kbps": v_kbps,
        "actual_encoder": venc,
        "warning": warning,
    }


# ============================================================
# Quality metrics
# ============================================================

def quality_metrics(ref: Path, dist: Path, sid: str, quick: bool = True) -> Dict[str, Any]:
    res: Dict[str, Any] = {}
    info = ffinfo()

    if not info["ffmpeg"]:
        return res

    log = LOG_DIR / f"{sid}.log"
    mm = media(ref)
    w, h = mm.get("width", 0), mm.get("height", 0)

    if not w or not h:
        return res

    limit = ["-t", "60"] if quick else []

    graph = (
        f"[0:v]setpts=PTS-STARTPTS,scale={w}:{h}:flags=bicubic,format=yuv420p,split=2[refp][refs];"
        f"[1:v]setpts=PTS-STARTPTS,scale={w}:{h}:flags=bicubic,format=yuv420p,split=2[distp][dists];"
        f"[refp][distp]psnr;"
        f"[refs][dists]ssim"
    )

    out = run_ffmpeg(
        [info["ffmpeg"], "-hide_banner", "-nostats", "-i", str(ref), "-i", str(dist)]
        + limit
        + ["-lavfi", graph, "-an", "-f", "null", "-"],
        log,
        600,
    )

    m = re.search(r"average:([0-9.]+|inf)", out)
    if m:
        res["PSNR"] = 100.0 if m.group(1) == "inf" else float(m.group(1))

    m = re.search(r"All:([0-9.]+)", out)
    if m:
        res["SSIM"] = float(m.group(1))

    if has_filter("libvmaf"):
        js = LOG_DIR / f"{sid}_vmaf.json"

        graph_v = (
            f"[0:v]setpts=PTS-STARTPTS,scale={w}:{h}:flags=bicubic,format=yuv420p[ref];"
            f"[1:v]setpts=PTS-STARTPTS,scale={w}:{h}:flags=bicubic,format=yuv420p[dist];"
            f"[dist][ref]libvmaf=log_fmt=json:log_path={js}"
        )

        run_ffmpeg(
            [info["ffmpeg"], "-hide_banner", "-nostats", "-i", str(ref), "-i", str(dist)]
            + limit
            + ["-lavfi", graph_v, "-an", "-f", "null", "-"],
            log,
            900,
        )

        try:
            data = json.loads(js.read_text())
            res["VMAF"] = float(data.get("pooled_metrics", {}).get("vmaf", {}).get("mean"))
        except Exception:
            pass

    elif res.get("SSIM"):
        res["VMAF_proxy"] = round(max(0, min(100, 100 * (res["SSIM"] ** 0.45))), 2)

    return res


# ============================================================
# Per-title ABR analysis
# ============================================================

def analyze_complexity(src: Path, duration: float, sid: str) -> float:
    info = ffinfo()
    log = LOG_DIR / f"{sid}.log"

    if not info["ffmpeg"] or not has_filter("signalstats"):
        return 0.5

    sample_t = min(20.0, max(3.0, duration * 0.1)) if duration else 8.0
    start = max(0.0, duration / 2 - sample_t / 2) if duration else 0.0

    cmd = [
        info["ffmpeg"],
        "-hide_banner",
        "-nostats",
        "-ss", str(round(start, 2)),
        "-i", str(src),
        "-t", str(round(sample_t, 2)),
        "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YDIF",
        "-f", "null",
        os.devnull,
    ]

    out = run_ffmpeg(cmd, log, 120)
    vals = [float(m) for m in re.findall(r"lavfi\.signalstats\.YDIF=([0-9.]+)", out)]

    if not vals:
        return 0.5

    avg_diff = sum(vals) / len(vals)

    return round(max(0.0, min(1.0, avg_diff / 20.0)), 3)


def per_title_ladder(src_meta: Dict[str, Any], complexity: float) -> List[Dict[str, Any]]:
    base_rungs = [
        {"h": 240, "w": 426, "base_kbps": 350},
        {"h": 480, "w": 854, "base_kbps": 800},
        {"h": 720, "w": 1280, "base_kbps": 2000},
    ]

    if src_meta.get("height", 0) >= 1000 and src_meta.get("width", 0) >= 1700:
        base_rungs.append({"h": 1080, "w": 1920, "base_kbps": 3800})

    mult = 0.7 + complexity * 0.8

    ladder = []
    for r in base_rungs:
        ladder.append({
            "Resolution": f"{r['w']}x{r['h']}",
            "w": r["w"],
            "h": r["h"],
            "bitrate_kbps": int(round(r["base_kbps"] * mult, -1)),
        })

    return ladder


# ============================================================
# HLS
# ============================================================

DEFAULT_LADDER = [
    {"w": 426, "h": 240, "bitrate_kbps": 400},
    {"w": 854, "h": 480, "bitrate_kbps": 900},
    {"w": 1280, "h": 720, "bitrate_kbps": 2200},
]


def make_hls(src: Path, sid: str, ladder: Optional[List[Dict[str, Any]]] = None) -> Tuple[Path, Path, List[str]]:
    log = LOG_DIR / f"{sid}.log"
    od = OUT_DIR / f"abr_{sid[:8]}"
    od.mkdir(exist_ok=True)

    rungs = ladder if ladder else DEFAULT_LADDER
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    errors: List[str] = []

    for rung in rungs:
        w, h, br_k = rung["w"], rung["h"], rung["bitrate_kbps"]
        br = f"{br_k}k"
        name = f"{h}p.m3u8"

        cmd = [
            ffinfo()["ffmpeg"],
            "-hide_banner",
            "-y",
            "-i", str(src),
            "-vf", f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264" if has_encoder("libx264") else "h264",
            "-preset", "veryfast",
            "-b:v", br,
            "-maxrate", br,
            "-bufsize", f"{br_k * 2}k",
            "-c:a", "aac",
            "-b:a", "96k",
            "-f", "hls",
            "-hls_time", "4",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(od / f"{h}p_%03d.ts"),
            str(od / name),
        ]

        try:
            p = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=1800,
            )

            with log.open("a", encoding="utf-8") as f:
                f.write("\n$ " + " ".join(map(str, cmd)) + "\n" + (p.stdout or ""))

            if p.returncode == 0 and (od / name).exists():
                lines += [
                    f"#EXT-X-STREAM-INF:BANDWIDTH={br_k * 1000},RESOLUTION={w}x{h}",
                    name,
                ]
            else:
                errors.append(f"{h}p failed")

        except Exception as e:
            errors.append(f"{h}p failed: {e}")

    master = od / "master.m3u8"
    master.write_text("\n".join(lines), encoding="utf-8")

    return master, log, errors


# ============================================================
# CSV logging
# ============================================================

CSV_FIELDS = [
    "timestamp",
    "source",
    "output",
    "mode",
    "profile",
    "codec",
    "actual_encoder",
    "crf",
    "preset",
    "target_mb",
    "source_mb",
    "output_mb",
    "saved_pct",
    "PSNR",
    "SSIM",
    "VMAF",
    "VMAF_proxy",
    "log",
]


def csvrow(row: Dict[str, Any]):
    p = LOG_DIR / "sessions.csv"
    new = not p.exists()
    full = {k: row.get(k, "") for k in CSV_FIELDS}

    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new:
            w.writeheader()
        w.writerow(full)


# ============================================================
# Render helpers
# ============================================================

def render_metric(label: str, value: str, sub: str = ""):
    sub_html = f"<div class='metric-sub'>{sub}</div>" if sub else ""
    st.markdown(
        f"<div class='metric-card'>"
        f"<div class='metric-label'>{label}</div>"
        f"<div class='metric-value'>{value}</div>"
        f"{sub_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def toast(msg: str, icon: str = "✅"):
    try:
        st.toast(msg, icon=icon)
    except Exception:
        pass


def player(path: Path, poster: Optional[Path], mime: str):
    if not path or not path.exists():
        return

    inline_limit_mb = 25

    if path.stat().st_size > inline_limit_mb * 1024 * 1024:
        st.video(str(path))
        return

    vb64 = base64.b64encode(path.read_bytes()).decode()
    pa = ""

    if poster and poster.exists() and poster.stat().st_size < 5 * 1024 * 1024:
        pm = "image/png" if poster.suffix.lower() == ".png" else "image/jpeg"
        pa = f"poster='data:{pm};base64,{base64.b64encode(poster.read_bytes()).decode()}'"

    components.html(
        f"""
        <div style='background:#fff;border:1px solid #e5edf5;border-radius:14px;padding:10px;'>
            <video controls preload='metadata' style='width:100%;max-height:520px;background:#000;border-radius:10px' {pa}>
                data:{mime};base64,{vb64}
            </video>
        </div>
        """,
        height=560,
    )


# ============================================================
# Session state
# ============================================================

for k in [
    "src",
    "out",
    "img",
    "src_meta",
    "last_metrics",
    "last_md",
    "last_log",
    "upload_src_id",
    "upload_img_id",
]:
    if k not in st.session_state:
        st.session_state[k] = None


# ============================================================
# Header
# ============================================================

info = ffinfo()
av1_ready = has_encoder("libsvtav1") or has_encoder("libaom-av1")

st.markdown(
    f"""
<div class='hero'>
  <h1>🎬 VideoForge Studio</h1>
  <p>Professional video optimization platform — intent-based encoding, target-size control, smart enhancement, side-by-side analysis, CRF sweep, and ABR packaging.</p>
  <div style='margin-top:12px'>
    <span class='badge'>{'✅' if info['ffmpeg'] else '❌'} FFmpeg</span>
    <span class='badge'>{'✅' if has_encoder('libx264') else '⚠️'} H.264</span>
    <span class='badge'>{'✅' if has_encoder('libx265') else '⚠️'} HEVC</span>
    <span class='badge'>{'✅' if av1_ready else '⚠️'} AV1</span>
    <span class='badge'>{'✅' if has_filter('libvmaf') else '⚠️'} VMAF</span>
    <span class='badge'>{'✅' if has_filter('signalstats') else '⚠️'} Per-title analysis</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if not info["ffmpeg"]:
    st.error("FFmpeg is missing. Repo must contain `packages.txt` with `ffmpeg` inside, then redeploy.")
    st.stop()


# ============================================================
# Tabs
# ============================================================

tab_work, tab_compare, tab_player, tab_quality, tab_sweep, tab_abr, tab_logs = st.tabs(
    ["🛠️ Workflow", "🆚 Compare", "▶️ Player", "📊 Quality", "📈 CRF Sweep", "📡 ABR", "🪵 Logs"]
)


# ============================================================
# Workflow tab
# ============================================================

with tab_work:
    st.markdown("<div class='section-title'>Step 1 · Upload</div>", unsafe_allow_html=True)

    with st.container(border=True):
        cu1, cu2 = st.columns([1.2, 0.8], gap="large")

        with cu1:
            up = st.file_uploader(
                "Source video",
                type=["mp4", "mov", "mkv", "webm", "avi", "m4v", "ts"],
                key="upload_src",
            )

            if up:
                uid = upload_identity(up)
                if st.session_state.get("upload_src_id") != uid:
                    p = save_upload(up, IN_DIR)
                    st.session_state.upload_src_id = uid
                    st.session_state.src = str(p)
                    st.session_state.src_meta = media(p)
                    st.success(f"Loaded: {p.name}")

        with cu2:
            im = st.file_uploader(
                "Image / logo / poster",
                type=["png", "jpg", "jpeg", "webp"],
                key="upload_img",
            )

            if im:
                iid = upload_identity(im)
                if st.session_state.get("upload_img_id") != iid:
                    ip = save_upload(im, IN_DIR)
                    st.session_state.upload_img_id = iid
                    st.session_state.img = str(ip)

                if st.session_state.img and Path(st.session_state.img).exists():
                    st.image(st.session_state.img, caption="Attached image", use_container_width=True)

        src_meta = st.session_state.src_meta or {}

        if src_meta:
            is_hdr = detect_hdr(src_meta)
            interp_ok, interp_msg = recommend_interpolation(src_meta)

            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                render_metric("Resolution", f"{src_meta['width']}×{src_meta['height']}")
            with c2:
                render_metric("Codec", src_meta["vcodec"].upper())
            with c3:
                render_metric("FPS", f"{src_meta['fps']:.2f}")
            with c4:
                render_metric("Bitrate", f"{src_meta['bitrate_kbps']:.0f} kbps")
            with c5:
                render_metric("Size", f"{src_meta['size_mb']:.2f} MB")

            st.markdown(
                f"<div class='{'warn-strip' if is_hdr else 'ok-strip'}'>"
                f"{'⚠️ HDR source detected' if is_hdr else '✅ SDR source detected — HDR conversion will be disabled.'}"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                f"<div class='{'warn-strip' if not interp_ok else 'info-strip'}'>🎞️ {interp_msg}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div class='section-title'>Step 2 · Optimization Goal</div>", unsafe_allow_html=True)

    with st.container(border=True):
        mode = st.radio(
            "Output control",
            ["Best quality at CRF", "Guaranteed target size"],
            horizontal=True,
            help="CRF optimizes quality/compression but does not guarantee smaller output. Target size uses two-pass bitrate encoding.",
        )

        is_target_mode = mode == "Guaranteed target size"

        if is_target_mode:
            profile_name = TARGET_PROFILE
            profile = PROFILES[profile_name]
        else:
            goal = st.slider(
                "Quality ◄────────► Size",
                0,
                100,
                55,
                help="0 = max quality, 100 = smallest file",
            )
            profile_name = map_slider_to_profile(goal)
            crf_profiles = [k for k in PROFILES.keys() if k != TARGET_PROFILE]
            profile_name = st.selectbox(
                "Profile override",
                crf_profiles,
                index=crf_profiles.index(profile_name),
            )
            profile = PROFILES[profile_name]

        st.markdown(f"<div class='info-strip'>{profile['desc']}</div>", unsafe_allow_html=True)

        if is_target_mode:
            tc1, tc2, tc3, tc4 = st.columns(4)

            with tc1:
                codec = st.selectbox(
                    "Codec",
                    ["AVC (H.264)", "HEVC (H.265)", "AV1"],
                    index=0,
                    key="target_codec",
                    help="AV1 target-size requires libaom-av1. If unavailable, the app falls back to H.264 and shows a warning.",
                )

            with tc2:
                target_mb = st.number_input(
                    "Target size (MB)",
                    min_value=1.0,
                    max_value=20000.0,
                    value=25.0,
                    step=1.0,
                )

            with tc3:
                target_audio_kbps = st.selectbox("Audio bitrate", [64, 96, 128, 160, 192], index=2)

            with tc4:
                preset = st.selectbox("Preset", ["veryfast", "fast", "medium", "slow"], index=2)

            crf = None

        else:
            pc1, pc2, pc3 = st.columns(3)

            with pc1:
                codec = st.selectbox(
                    "Codec",
                    ["AVC (H.264)", "HEVC (H.265)", "AV1"],
                    index=["AVC (H.264)", "HEVC (H.265)", "AV1"].index(profile["default_codec"]),
                )

            if codec == "AV1":
                default_crf = profile["av1"]["crf"]
                default_preset = profile["av1"]["preset"]
                preset_opts = ["4", "5", "6", "7", "8"]
                st.info("AV1 output uses WebM. Some environments may not preview AV1 WebM reliably.")
            elif codec == "HEVC (H.265)":
                default_crf = profile["hevc"]["crf"]
                default_preset = profile["hevc"]["preset"]
                preset_opts = ["veryfast", "fast", "medium", "slow"]
            else:
                default_crf = profile["h264"]["crf"]
                default_preset = profile["h264"]["preset"]
                preset_opts = ["veryfast", "fast", "medium", "slow"]

            with pc2:
                crf = st.slider(
                    "CRF override",
                    14,
                    45,
                    int(default_crf),
                    help="Lower = higher quality + larger file. Higher = smaller file + lower quality.",
                )

            with pc3:
                try:
                    preset_idx = preset_opts.index(str(default_preset))
                except ValueError:
                    preset_idx = 0

                preset = st.selectbox("Preset override", preset_opts, index=preset_idx)

            target_mb, target_audio_kbps = None, None

    st.markdown("<div class='section-title'>Step 3 · Enhancements</div>", unsafe_allow_html=True)

    with st.container(border=True):
        with st.expander("🛡️ Quality enhancement", expanded=True):
            e1, e2, e3 = st.columns(3)
            denoise = e1.checkbox("Denoise", value=False)
            deblock = e2.checkbox("Deblock", value=False)
            sharpen = e3.checkbox("Sharpen", value=False)

        with st.expander("🎨 Color processing", expanded=False):
            c1, c2 = st.columns(2)
            color = c1.checkbox("Color boost", value=False)
            is_hdr_src = detect_hdr(src_meta) if src_meta else False
            hdr_sdr = c2.checkbox(
                "HDR → SDR",
                value=is_hdr_src,
                disabled=not is_hdr_src,
                help="Enabled only when HDR metadata is detected.",
            )

        with st.expander("🎞️ Motion processing", expanded=False):
            interp_recommended, _ = recommend_interpolation(src_meta) if src_meta else (True, "")
            interp = st.checkbox(
                "Frame interpolation → 60fps",
                value=False,
                disabled=not interp_recommended,
                help="Disabled when source is already ≥ 50 fps.",
            )

        with st.expander("📐 Resolution", expanded=False):
            scale_to = st.selectbox(
                "Target resolution",
                ["Source", "480p", "720p", "1080p", "2160p"],
                index=0,
            )

        with st.expander("🖼️ Image / logo overlay", expanded=False):
            if is_target_mode:
                st.info("Watermark overlay is disabled in Target Size mode to keep two-pass output predictable.")
                image_mode = "Ignore image"
                logo_pos, logo_scale = "Top right", 14
            else:
                image_mode = st.selectbox(
                    "Attached image behavior",
                    ["Ignore image", "Watermark / logo overlay", "Poster only in player"],
                    index=1 if st.session_state.img else 0,
                )

                lc1, lc2 = st.columns(2)
                logo_pos = lc1.selectbox("Logo position", ["Top right", "Top left", "Bottom right", "Bottom left"])
                logo_scale = lc2.slider("Logo scale %", 5, 35, 14)

    enhancements = dict(
        denoise=denoise,
        sharpen=sharpen,
        deblock=deblock,
        color=color,
        hdr_sdr=hdr_sdr,
        interp=interp,
        scale_to=scale_to,
    )

    if src_meta and not is_target_mode:
        risky = []
        if interp:
            risky.append("frame interpolation")
        if scale_to in ["1080p", "2160p"]:
            risky.append("upscaling")
        if sharpen:
            risky.append("sharpening")
        if color:
            risky.append("color boost")

        if risky:
            st.warning(
                "Selected enhancements may increase file size because they add detail, pixels, frames, or visual complexity. "
                "Use Guaranteed Target Size mode if output size must be controlled. "
                f"Active: {', '.join(risky)}."
            )

    st.markdown("<div class='section-title'>Step 4 · Preview Impact</div>", unsafe_allow_html=True)

    if src_meta:
        with st.container(border=True):
            if is_target_mode:
                v_kbps = bitrate_from_target_size(
                    src_meta.get("duration", 0),
                    float(target_mb),
                    int(target_audio_kbps),
                )

                pc1, pc2, pc3, pc4 = st.columns(4)
                with pc1:
                    render_metric("Target Output Size", f"{target_mb:.1f} MB")
                with pc2:
                    render_metric(
                        "Computed Video Bitrate",
                        f"{v_kbps} kbps" if v_kbps else "—",
                        "Too small for duration" if not v_kbps else "",
                    )
                with pc3:
                    render_metric("Audio Bitrate", f"{target_audio_kbps} kbps")
                with pc4:
                    render_metric("Passes", "2")

            else:
                est = estimate_output(src_meta, codec, int(crf), enhancements)

                pc1, pc2, pc3, pc4 = st.columns(4)
                with pc1:
                    render_metric("Est. Output Size", f"{est['est_size_mb']:.2f} MB")
                with pc2:
                    render_metric("Est. Bitrate", f"{est['est_bitrate_kbps']} kbps")
                with pc3:
                    render_metric("Expected Savings", f"{est['expected_savings_pct']:.1f}%")
                with pc4:
                    m = est["est_time_sec"]
                    render_metric("Est. Encode Time", f"{m // 60}m {m % 60}s")
    else:
        st.info("Upload a source video to see estimates.")

    st.markdown("<div class='section-title'>Step 5 · Encode</div>", unsafe_allow_html=True)

    with st.container(border=True):
        go = st.button("✨ Encode Now", type="primary", use_container_width=True)

        if go:
            if not st.session_state.src:
                st.error("Upload a source video first.")
            else:
                sid = uuid.uuid4().hex
                src = Path(st.session_state.src)
                logo = Path(st.session_state.img) if st.session_state.img else None
                bar = st.progress(0.0, text="Starting FFmpeg encode…")

                if is_target_mode:
                    opts = dict(
                        codec=codec,
                        preset=preset,
                        target_mb=target_mb,
                        audio_kbps=target_audio_kbps,
                        denoise=denoise,
                        sharpen=sharpen,
                        deblock=deblock,
                        color=color,
                        hdr_sdr=hdr_sdr,
                        interp=interp,
                        scale_to=scale_to,
                    )

                    out_path, log, md = encode_two_pass(
                        src,
                        opts,
                        src_meta,
                        sid,
                        cb=lambda p, t: bar.progress(float(p), text=t),
                    )

                else:
                    opts = dict(
                        codec=codec,
                        crf=crf,
                        preset=preset,
                        profile=profile_name,
                        denoise=denoise,
                        sharpen=sharpen,
                        deblock=deblock,
                        color=color,
                        hdr_sdr=hdr_sdr,
                        interp=interp,
                        scale_to=scale_to,
                        image_mode=image_mode,
                        logo_pos=logo_pos,
                        logo_scale=logo_scale,
                    )

                    out_path, log, md = encode_video(
                        src,
                        logo,
                        opts,
                        src_meta,
                        sid,
                        cb=lambda p, t: bar.progress(float(p), text=t),
                    )

                if not out_path:
                    st.error(md.get("error", "Encoding failed"))
                    if md.get("tail"):
                        st.code(md["tail"])
                else:
                    st.session_state.out = str(out_path)
                    st.session_state.last_md = md
                    st.session_state.last_log = str(log)

                    if md.get("warning"):
                        st.warning(md["warning"])

                    with st.spinner("Computing quality metrics…"):
                        q = quality_metrics(src, out_path, sid, quick=True)

                    st.session_state.last_metrics = q

                    sm = src_meta
                    dm = media(out_path)
                    saved = (1 - dm["size_mb"] / sm["size_mb"]) * 100 if sm["size_mb"] else 0

                    row = {
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "source": src.name,
                        "output": out_path.name,
                        "mode": "Two-pass Target Size" if is_target_mode else "Standard CRF",
                        "profile": profile_name,
                        "codec": codec,
                        "actual_encoder": md.get("actual_encoder", ""),
                        "crf": crf if crf is not None else "",
                        "preset": preset,
                        "target_mb": target_mb if is_target_mode else "",
                        "source_mb": round(sm["size_mb"], 3),
                        "output_mb": round(dm["size_mb"], 3),
                        "saved_pct": round(saved, 2),
                        "PSNR": q.get("PSNR"),
                        "SSIM": q.get("SSIM"),
                        "VMAF": q.get("VMAF"),
                        "VMAF_proxy": q.get("VMAF_proxy"),
                        "log": str(log),
                    }

                    csvrow(row)

                    toast(f"Encode complete · {dm['size_mb']:.2f} MB")
                    st.success(
                        f"Done · {dm['size_mb']:.2f} MB · saved {saved:.1f}% · encoder {md.get('actual_encoder', 'unknown')}"
                    )

                    st.download_button(
                        "⬇ Download Output",
                        out_path.read_bytes(),
                        out_path.name,
                        md.get("mime", "application/octet-stream"),
                    )


# ============================================================
# Compare tab
# ============================================================

with tab_compare:
    if not (st.session_state.src and st.session_state.out and Path(st.session_state.out).exists()):
        st.info("Run an encode first to see the comparison dashboard.")
    else:
        src = Path(st.session_state.src)
        out = Path(st.session_state.out)

        sm = media(src)
        dm = media(out)
        q = st.session_state.last_metrics or {}

        saved_pct = (1 - dm["size_mb"] / sm["size_mb"]) * 100 if sm["size_mb"] else 0
        br_save = (1 - dm["bitrate_kbps"] / sm["bitrate_kbps"]) * 100 if sm["bitrate_kbps"] else 0

        st.markdown("<div class='section-title'>Input vs Output</div>", unsafe_allow_html=True)

        cc1, cc2, cc3 = st.columns([1, 1, 1])

        with cc1:
            st.markdown(
                f"""
                <div class='compare-input'>
                    <div style='font-weight:800;font-size:1rem;margin-bottom:10px;color:#475569'>📥 INPUT</div>
                    <div class='compare-row'><span class='compare-label'>Size</span><span class='compare-val'>{sm['size_mb']:.2f} MB</span></div>
                    <div class='compare-row'><span class='compare-label'>Codec</span><span class='compare-val'>{sm['vcodec'].upper()}</span></div>
                    <div class='compare-row'><span class='compare-label'>Bitrate</span><span class='compare-val'>{sm['bitrate_kbps']:.0f} kbps</span></div>
                    <div class='compare-row'><span class='compare-label'>Resolution</span><span class='compare-val'>{sm['width']}×{sm['height']}</span></div>
                    <div class='compare-row'><span class='compare-label'>FPS</span><span class='compare-val'>{sm['fps']:.2f}</span></div>
                    <div class='compare-row'><span class='compare-label'>Duration</span><span class='compare-val'>{sm['duration']:.1f}s</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with cc2:
            st.markdown(
                f"""
                <div class='savings-card'>
                    <div class='savings-value'>{saved_pct:+.1f}%</div>
                    <div class='savings-label'>Size Reduction</div>
                    <div style='margin-top:12px;font-size:.85rem;opacity:.95'>Bitrate {br_save:+.1f}%</div>
                    <div style='margin-top:6px;font-size:.85rem;opacity:.95'>Saved {(sm['size_mb'] - dm['size_mb']):.2f} MB</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with cc3:
            st.markdown(
                f"""
                <div class='compare-output'>
                    <div style='font-weight:800;font-size:1rem;margin-bottom:10px;color:#1e3a8a'>📤 OUTPUT</div>
                    <div class='compare-row'><span class='compare-label'>Size</span><span class='compare-val'>{dm['size_mb']:.2f} MB</span></div>
                    <div class='compare-row'><span class='compare-label'>Codec</span><span class='compare-val'>{dm['vcodec'].upper()}</span></div>
                    <div class='compare-row'><span class='compare-label'>Bitrate</span><span class='compare-val'>{dm['bitrate_kbps']:.0f} kbps</span></div>
                    <div class='compare-row'><span class='compare-label'>Resolution</span><span class='compare-val'>{dm['width']}×{dm['height']}</span></div>
                    <div class='compare-row'><span class='compare-label'>FPS</span><span class='compare-val'>{dm['fps']:.2f}</span></div>
                    <div class='compare-row'><span class='compare-label'>Duration</span><span class='compare-val'>{dm['duration']:.1f}s</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<div class='section-title'>Quality Dashboard</div>", unsafe_allow_html=True)

        with st.container(border=True):
            q1, q2, q3, q4 = st.columns(4)

            with q1:
                vmaf_val = q.get("VMAF", q.get("VMAF_proxy"))
                render_metric(
                    "VMAF",
                    f"{vmaf_val:.2f}" if vmaf_val else "—",
                    "True VMAF" if q.get("VMAF") else "Proxy from SSIM",
                )

            with q2:
                render_metric(
                    "SSIM",
                    f"{q.get('SSIM', 0):.4f}" if q.get("SSIM") else "—",
                    "0.95+ Good · 0.98+ Excellent",
                )

            with q3:
                render_metric(
                    "PSNR",
                    f"{q.get('PSNR', 0):.2f} dB" if q.get("PSNR") else "—",
                    "40+ dB Good",
                )

            with q4:
                ratio = sm["size_mb"] / dm["size_mb"] if dm["size_mb"] else 0
                render_metric("Compression Ratio", f"{ratio:.2f}×", "Size reduction factor")

        st.markdown("<div class='section-title'>Side-by-Side Playback</div>", unsafe_allow_html=True)

        sbs1, sbs2 = st.columns(2)
        poster = Path(st.session_state.img) if st.session_state.img and Path(st.session_state.img).exists() else None

        with sbs1:
            st.markdown("**Original**")
            player(src, poster, "video/mp4")

        with sbs2:
            st.markdown("**Encoded**")
            mime_out = "video/webm" if out.suffix.lower() == ".webm" else "video/mp4"
            player(out, poster, mime_out)

        if st.session_state.last_md:
            st.download_button(
                "⬇ Download Encoded Video",
                out.read_bytes(),
                out.name,
                st.session_state.last_md.get("mime", "application/octet-stream"),
            )


# ============================================================
# Player tab
# ============================================================

with tab_player:
    st.markdown("<div class='section-title'>Universal Player</div>", unsafe_allow_html=True)

    p = None

    if st.session_state.out and Path(st.session_state.out).exists():
        p = Path(st.session_state.out)
        st.caption(f"Loaded latest output: {p.name}")
    else:
        up_p = st.file_uploader("Upload media", type=["mp4", "webm", "mov", "mkv"], key="play_up")
        if up_p:
            p = save_upload(up_p, IN_DIR)

    if p:
        poster = Path(st.session_state.img) if st.session_state.img and Path(st.session_state.img).exists() else None
        mime = "video/webm" if p.suffix.lower() == ".webm" else "video/mp4"
        player(p, poster, mime)

    with st.expander("🎥 Experimental: WebRTC Camera Preview", expanded=False):
        st.caption("WebRTC may fail on free cloud runtimes. It is only used for live camera preview, not playback.")

        if WEBRTC_AVAILABLE:
            enable = st.checkbox("Enable camera preview", value=False)

            if enable:
                try:
                    webrtc_streamer(
                        key="webrtc-v3",
                        rtc_configuration=RTCConfiguration(
                            {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
                        ),
                        media_stream_constraints={"video": True, "audio": False},
                        async_processing=True,
                    )
                except Exception as e:
                    st.warning(f"WebRTC failed: {e}")
        else:
            st.warning("streamlit-webrtc is not installed.")


# ============================================================
# Quality tab
# ============================================================

with tab_quality:
    st.markdown("<div class='section-title'>Quality Analytics</div>", unsafe_allow_html=True)

    with st.container(border=True):
        qa, qb = st.columns(2)

        rf = qa.file_uploader("Reference / source", type=["mp4", "mov", "mkv", "webm"], key="ref_up")
        df_file = qb.file_uploader("Distorted / encoded", type=["mp4", "mov", "mkv", "webm"], key="dist_up")

        full = st.checkbox("Full duration", value=False)

        if st.button("Calculate PSNR / SSIM / VMAF", use_container_width=True):
            if not rf or not df_file:
                st.error("Upload both files.")
            else:
                sid = uuid.uuid4().hex
                rp = save_upload(rf, IN_DIR)
                dp = save_upload(df_file, IN_DIR)

                with st.spinner("Computing metrics…"):
                    qm = quality_metrics(rp, dp, sid, quick=not full)

                q1, q2, q3 = st.columns(3)

                with q1:
                    render_metric("PSNR", f"{qm.get('PSNR', 0):.2f} dB" if qm.get("PSNR") else "—")

                with q2:
                    render_metric("SSIM", f"{qm.get('SSIM', 0):.4f}" if qm.get("SSIM") else "—")

                with q3:
                    v = qm.get("VMAF", qm.get("VMAF_proxy"))
                    render_metric("VMAF", f"{v:.2f}" if v else "—", "True VMAF" if qm.get("VMAF") else "Proxy")


# ============================================================
# CRF Sweep tab
# ============================================================

with tab_sweep:
    st.markdown("<div class='section-title'>Rate-Distortion Sweep</div>", unsafe_allow_html=True)

    src_path = st.session_state.src

    with st.container(border=True):
        if not src_path:
            su = st.file_uploader("Upload source for sweep", type=["mp4", "mov", "mkv", "webm"], key="sweep_up")
            if su:
                sp = save_upload(su, IN_DIR)
                st.session_state.src = str(sp)
                st.session_state.src_meta = media(sp)
                src_path = str(sp)

        sw1, sw2, sw3, sw4 = st.columns(4)

        sw_codec = sw1.selectbox("Codec", ["AVC (H.264)", "HEVC (H.265)", "AV1"], key="sweep_codec_v3")
        sw_profile = sw2.selectbox(
            "Profile",
            [k for k in PROFILES if k != TARGET_PROFILE],
            index=1,
            key="sweep_profile_v3",
        )
        sw_start = sw3.number_input("CRF start", 14, 45, 22, key="sweep_start_v3")
        sw_end = sw4.number_input("CRF end", int(sw_start) + 1, 51, 38, key="sweep_end_v3")
        sw_step = st.slider("Step", 1, 10, 4, key="sweep_step_v3")

        sweep_sample = st.selectbox("Sweep sample duration", ["30", "60", "120", "Full"], index=1)

        st.info(
            "Sweep uses the existing encoder path. For very long files, use 30s or 60s sampling to avoid heavy cloud workloads."
        )

        if st.button("🚀 Run CRF Sweep", type="primary"):
            if not src_path:
                st.error("Upload a source first.")
            else:
                src = Path(src_path)
                sm = media(src)
                crfs = list(range(int(sw_start), int(sw_end) + 1, int(sw_step)))
                rows = []
                prog = st.progress(0, text="Starting sweep…")

                for i, cval in enumerate(crfs):
                    sid = uuid.uuid4().hex

                    opts = dict(
                        codec=sw_codec,
                        crf=cval,
                        preset="fast" if sw_codec != "AV1" else "6",
                        profile=sw_profile,
                        denoise=False,
                        sharpen=False,
                        deblock=False,
                        color=False,
                        hdr_sdr=False,
                        interp=False,
                        scale_to="Source",
                        image_mode="Ignore image",
                        logo_pos="Top right",
                        logo_scale=14,
                    )

                    out_p, log, md = encode_video(
                        src,
                        None,
                        opts,
                        sm,
                        sid,
                        cb=lambda p, t, i=i: prog.progress(
                            min(0.99, (i + p) / len(crfs)),
                            text=f"CRF {cval} · {t}",
                        ),
                    )

                    if out_p:
                        qm = quality_metrics(src, out_p, sid, quick=True)
                        dm = media(out_p)

                        rows.append({
                            "CRF": cval,
                            "Size MB": round(dm["size_mb"], 2),
                            "Bitrate kbps": round(dm["bitrate_kbps"]),
                            "PSNR": qm.get("PSNR"),
                            "SSIM": qm.get("SSIM"),
                            "VMAF": qm.get("VMAF", qm.get("VMAF_proxy")),
                            "Encoder": md.get("actual_encoder", ""),
                            "File": out_p.name,
                        })

                prog.progress(1.0, text="Sweep complete")

                if rows:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)

                    chart_cols = [c for c in ["Size MB", "VMAF", "SSIM"] if c in df.columns and df[c].notna().any()]
                    if chart_cols:
                        st.line_chart(df.set_index("CRF")[chart_cols])

                    st.download_button(
                        "⬇ Download CSV",
                        df.to_csv(index=False).encode(),
                        "crf_sweep.csv",
                        "text/csv",
                    )


# ============================================================
# ABR tab
# ============================================================

with tab_abr:
    st.markdown("<div class='section-title'>Adaptive Bitrate Ladder / HLS</div>", unsafe_allow_html=True)

    src_abr = None

    with st.container(border=True):
        if st.session_state.out and Path(st.session_state.out).exists():
            src_abr = Path(st.session_state.out)
            st.caption(f"Using latest output: {src_abr.name}")
        else:
            au = st.file_uploader("Upload for ABR", type=["mp4", "mov", "mkv", "webm"], key="abr_up")
            if au:
                src_abr = save_upload(au, IN_DIR)

        st.markdown("<div class='section-title' style='margin-top:8px'>Per-title encoding</div>", unsafe_allow_html=True)

        per_title = st.checkbox(
            "🎯 Content-adaptive bitrates",
            value=False,
            help="Analyzes motion/spatial complexity and scales each rung bitrate.",
        )

        ladder_preview = None

        if per_title and src_abr:
            comp_key = f"complexity_{src_abr.name}_{src_abr.stat().st_mtime}"

            if st.button("Analyze complexity", use_container_width=False):
                sid_a = uuid.uuid4().hex
                sm_a = media(src_abr)

                with st.spinner("Sampling motion and spatial complexity…"):
                    score = analyze_complexity(src_abr, sm_a.get("duration", 0), sid_a)

                st.session_state[comp_key] = score

            score = st.session_state.get(comp_key)

            if score is not None:
                tier = "high motion" if score > 0.66 else ("moderate motion" if score > 0.33 else "low motion")

                st.markdown(
                    f"<div class='info-strip'>Complexity score: {score:.2f} / 1.00 — {tier} content detected</div>",
                    unsafe_allow_html=True,
                )

                ladder_preview = per_title_ladder(media(src_abr), score)

                st.dataframe(
                    pd.DataFrame([
                        {"Resolution": r["Resolution"], "Bitrate kbps": r["bitrate_kbps"]}
                        for r in ladder_preview
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )

            elif not has_filter("signalstats"):
                st.warning("This FFmpeg build does not include `signalstats`. Neutral 0.5 complexity ladder will be used.")

        if st.button("Generate HLS ABR Ladder", type="primary"):
            if not src_abr:
                st.error("Upload or encode first.")
            else:
                sid = uuid.uuid4().hex
                ladder = ladder_preview if (per_title and ladder_preview) else None

                with st.spinner("Building HLS ladder…"):
                    master, log, errors = make_hls(src_abr, sid, ladder=ladder)

                zp = OUT_DIR / f"abr_package_{int(time.time())}.zip"

                with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
                    for pf in master.parent.glob("*"):
                        z.write(pf, pf.name)

                if errors:
                    st.warning("Some HLS rungs failed: " + ", ".join(errors))
                else:
                    st.success("ABR ladder ready" + (" with per-title bitrates." if ladder else "."))

                st.code(master.read_text())

                st.download_button(
                    "⬇ Download ABR Package",
                    zp.read_bytes(),
                    zp.name,
                    "application/zip",
                )


# ============================================================
# Logs tab
# ============================================================

with tab_logs:
    st.markdown("<div class='section-title'>Session Logs</div>", unsafe_allow_html=True)

    csv_p = LOG_DIR / "sessions.csv"

    with st.container(border=True):
        if csv_p.exists():
            df = pd.read_csv(csv_p)
            st.dataframe(df.tail(200), use_container_width=True)

            st.download_button(
                "⬇ Download sessions CSV",
                csv_p.read_bytes(),
                "sessions.csv",
                "text/csv",
            )
        else:
            st.info("No sessions yet.")

        logs = sorted(LOG_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)

        if logs:
            sel = st.selectbox("Log file", logs, format_func=lambda x: x.name)
            st.text_area("Preview", sel.read_text(errors="ignore")[-10000:], height=320)

            st.download_button(
                "⬇ Download selected log",
                sel.read_bytes(),
                sel.name,
                "text/plain",
            )

    with st.container(border=True):
        with st.expander("🔧 Diagnostics"):
            st.write("FFmpeg:", "✅ Ready" if info["ffmpeg"] else "❌ Missing")
            st.caption(info.get("version", ""))

            st.write("FFprobe:", "✅ Ready" if info["ffprobe"] else "❌ Missing")

            st.write(
                f"x264 {'✅' if has_encoder('libx264') else '⚠️'} · "
                f"x265 {'✅' if has_encoder('libx265') else '⚠️'} · "
                f"SVT-AV1 {'✅' if has_encoder('libsvtav1') else '⚠️'} · "
                f"AOM-AV1 {'✅' if has_encoder('libaom-av1') else '⚠️'} · "
                f"libvmaf {'✅' if has_filter('libvmaf') else '⚠️'} · "
                f"signalstats {'✅' if has_filter('signalstats') else '⚠️'}"
            )

            st.info("For Streamlit Cloud, add a repo-root file named `packages.txt` containing exactly: `ffmpeg`.")

            st.code(
                "Recommended requirements.txt:\n"
                "streamlit>=1.36\n"
                "pandas>=2.0\n"
                "streamlit-webrtc>=0.47\n"
                "av>=12.0\n",
                language="text",
            )
