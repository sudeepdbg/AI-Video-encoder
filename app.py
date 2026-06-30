import re, json, time, uuid, shutil, subprocess, zipfile, base64, csv
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
try:
    from streamlit_webrtc import webrtc_streamer, RTCConfiguration
    WEBRTC_AVAILABLE=True
except Exception:
    WEBRTC_AVAILABLE=False

WORK=Path('work'); IN=WORK/'inputs'; OUT=WORK/'outputs'; LOG=WORK/'logs'
for d in (IN,OUT,LOG): d.mkdir(parents=True, exist_ok=True)
st.set_page_config(page_title='VideoForge Studio', page_icon='🎬', layout='wide')
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#f8fbff,#edf5fb);color:#1f2937}.block-container{max-width:1500px;padding-top:1.2rem}.hero{background:linear-gradient(135deg,#fff,#f2f7ff);border:1px solid #dbeafe;border-radius:22px;padding:24px;box-shadow:0 10px 30px rgba(59,130,246,.1);margin-bottom:18px}.hero h1{margin:0;color:#0f172a;font-size:2.1rem}.hero p{color:#53657d}.badge{display:inline-block;padding:6px 10px;margin:3px;border-radius:999px;background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;font-weight:650;font-size:.82rem}.sec{font-size:.78rem;letter-spacing:.22em;text-transform:uppercase;color:#64748b;font-weight:850;margin:22px 0 10px}.info{background:#dbeafe;color:#1e3a8a;border:1px solid #bfdbfe;border-radius:12px;padding:13px 16px;font-weight:650;margin:10px 0}.stButton>button{border-radius:12px!important;border:0!important;background:linear-gradient(135deg,#2563eb,#60a5fa)!important;color:#fff!important;font-weight:800!important}.stDownloadButton>button{border-radius:12px!important;font-weight:800!important}[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #e5edf5}[data-testid="stMetric"]{background:#fff;border:1px solid #e5edf5;border-radius:14px;padding:12px}video{border-radius:16px;background:#000}
</style>
""", unsafe_allow_html=True)

def ffinfo():
    ff,fp=shutil.which('ffmpeg'),shutil.which('ffprobe')
    d={'ffmpeg':ff or '', 'ffprobe':fp or '', 'version':'', 'encoders':'', 'filters':''}
    if ff:
        try:
            d['version']=subprocess.check_output([ff,'-version'],text=True,stderr=subprocess.STDOUT,timeout=5).splitlines()[0]
            d['encoders']=subprocess.check_output([ff,'-hide_banner','-encoders'],text=True,stderr=subprocess.STDOUT,timeout=8)
            d['filters']=subprocess.check_output([ff,'-hide_banner','-filters'],text=True,stderr=subprocess.STDOUT,timeout=8)
        except Exception as e: d['version']=str(e)
    return d

def has_encoder(x): return x in ffinfo().get('encoders','')
def has_filter(x): return x in (ffinfo().get('filters','') or '')
def clean(n): return re.sub(r'[^A-Za-z0-9_.-]+','_',Path(n).stem)[:70] or 'video'
def save(u, folder):
    if not u: return None
    p=folder/f'{int(time.time())}_{clean(u.name)}{Path(u.name).suffix.lower()}'; p.write_bytes(u.getbuffer()); return p

def probe(p):
    if not ffinfo()['ffprobe']: return {}
    try: return json.loads(subprocess.check_output([ffinfo()['ffprobe'],'-v','error','-show_streams','-show_format','-print_format','json',str(p)],text=True,stderr=subprocess.STDOUT,timeout=25))
    except Exception: return {}
def fr(v):
    try:
        a,b=v.split('/'); return round(float(a)/float(b),3) if float(b) else 0
    except Exception: return 0
def media(p):
    d=probe(p); fmt=d.get('format',{}) if d else {}; v={}; a={}
    for s in d.get('streams',[]):
        if s.get('codec_type')=='video' and not v: v=s
        if s.get('codec_type')=='audio' and not a: a=s
    size=Path(p).stat().st_size if Path(p).exists() else int(fmt.get('size',0) or 0)
    return {'duration':float(fmt.get('duration',0) or 0),'size_mb':size/1048576,'bitrate_kbps':int(fmt.get('bit_rate',0) or 0)/1000,'width':int(v.get('width',0) or 0),'height':int(v.get('height',0) or 0),'fps':fr(v.get('avg_frame_rate','0/1')),'codec':v.get('codec_name','unknown')}

def chain(o):
    f=[]
    if o['denoise']: f.append('hqdn3d=4:4:6:6')
    if o['deblock'] and has_filter('deblock'): f.append('deblock')
    if o['hdr_sdr']: f.append('zscale=t=linear:npl=100,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p' if has_filter('zscale') and has_filter('tonemap') else 'format=yuv420p')
    if o['color']: f.append('eq=contrast=1.08:saturation=1.12')
    if o['scale_to']!='Source': f.append(f"scale=-2:{int(o['scale_to'].replace('p',''))}:flags=lanczos")
    if o['sharpen']: f.append('unsharp=5:5:0.45:3:3:0.2')
    if o['interp']: f.append('minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1')
    return ','.join(f)

def cargs(codec, crf, preset):
    if codec=='AVC (H.264)':
        enc='libx264' if has_encoder('libx264') else 'h264'; return ['-c:v',enc,'-preset',preset,'-crf',str(crf),'-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart'],'.mp4','video/mp4'
    if codec=='HEVC (H.265)':
        enc='libx265' if has_encoder('libx265') else 'hevc'; args=['-c:v',enc,'-preset',preset,'-crf',str(crf),'-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart']
        if enc=='libx265': args += ['-tag:v','hvc1','-x265-params','log-level=error']
        return args,'.mp4','video/mp4'
    if has_encoder('libsvtav1'): return ['-c:v','libsvtav1','-crf',str(crf),'-preset','7','-pix_fmt','yuv420p','-c:a','libopus','-b:a','96k'],'.webm','video/webm'
    if has_encoder('libaom-av1'): return ['-c:v','libaom-av1','-crf',str(crf),'-b:v','0','-cpu-used','6','-pix_fmt','yuv420p','-c:a','libopus','-b:a','96k'],'.webm','video/webm'
    return cargs('AVC (H.264)',crf,preset)

def encode(src, logo, o, sid, cb=None):
    log=LOG/f'{sid}.log'
    if not ffinfo()['ffmpeg']: return None,log,{'error':'FFmpeg missing. Add ffmpeg to packages.txt and redeploy.'}
    args,ext,mime=cargs(o['codec'],o['crf'],o['preset']); out=OUT/f"{clean(src.name)}_{o['codec'].split()[0].lower()}_crf{o['crf']}_{sid[:8]}{ext}"; vf=chain(o)
    cmd=[ffinfo()['ffmpeg'],'-hide_banner','-y','-i',str(src)]
    if logo and o['image_mode']=='Watermark / logo overlay':
        cmd += ['-i',str(logo)]; pos={'Top right':'main_w-overlay_w-24:24','Top left':'24:24','Bottom right':'main_w-overlay_w-24:main_h-overlay_h-24','Bottom left':'24:main_h-overlay_h-24'}[o['logo_pos']]
        base=vf+',' if vf else ''; fc=f"[1:v]scale=iw*{o['logo_scale']}/100:-1[logo];[0:v]{base}format=yuv420p[base];[base][logo]overlay={pos}:format=auto[v]"
        cmd += ['-filter_complex',fc,'-map','[v]','-map','0:a?','-shortest']
    elif vf: cmd += ['-vf',vf]
    cmd += args+[str(out)]
    dur=max(media(src)['duration'],.001); lines=[]; log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('a',encoding='utf-8') as f: f.write('\n\n$ '+' '.join(map(str,cmd))+'\n')
    p=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,bufsize=1)
    last=0.0
    for line in p.stderr:
        lines.append(line.rstrip()); log.open('a',encoding='utf-8').write(line)
        m=re.search(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)',line)
        if m and cb:
            sec=int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)); pct=min(max(sec/dur,last),.995); last=pct; cb(pct,f'Encoding… {pct*100:.0f}%')
    rc=p.wait(); log.open('a',encoding='utf-8').write(f'\n[exit] {rc}\n')
    if cb: cb(1.0,'Encoding complete')
    if rc!=0 or not out.exists(): return None,log,{'error':'Encoding failed','tail':'\n'.join(lines[-80:])}
    return out,log,{'mime':mime}

def run(cmd,log,timeout=900):
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout); log.open('a',encoding='utf-8').write('\n$ '+' '.join(map(str,cmd))+'\n'+(p.stdout or '')); return p.stdout or ''
    except Exception as e: return str(e)
def quality(ref,dist,sid):
    res={}; log=LOG/f'{sid}.log'; mm=media(ref); scale=f"scale={mm['width']}:{mm['height']}:flags=bicubic" if mm['width'] and mm['height'] else 'null'
    graph=f"[0:v]setpts=PTS-STARTPTS,{scale},format=yuv420p,split=2[r1][r2];[1:v]setpts=PTS-STARTPTS,{scale},format=yuv420p,split=2[d1][d2];[r1][d1]psnr;[r2][d2]ssim"
    out=run([ffinfo()['ffmpeg'],'-hide_banner','-nostats','-i',str(ref),'-i',str(dist),'-t','90','-lavfi',graph,'-f','null','-'],log)
    m=re.search(r'average:([0-9.]+|inf)',out); res['PSNR']=100 if m and m.group(1)=='inf' else (float(m.group(1)) if m else None)
    m=re.search(r'All:([0-9.]+)',out); res['SSIM']=float(m.group(1)) if m else None
    if has_filter('libvmaf'):
        js=LOG/f'{sid}_vmaf.json'; graph=f"[0:v]setpts=PTS-STARTPTS,{scale},format=yuv420p[ref];[1:v]setpts=PTS-STARTPTS,{scale},format=yuv420p[dst];[dst][ref]libvmaf=log_fmt=json:log_path={js}"
        run([ffinfo()['ffmpeg'],'-hide_banner','-nostats','-i',str(ref),'-i',str(dist),'-t','90','-lavfi',graph,'-f','null','-'],log,1200)
        try: res['VMAF']=float(json.loads(js.read_text()).get('pooled_metrics',{}).get('vmaf',{}).get('mean'))
        except Exception: pass
    elif res.get('SSIM'): res['VMAF_proxy']=round(max(0,min(100,100*(res['SSIM']**0.45))),2)
    return res

def csvrow(row):
    p=LOG/'sessions.csv'; new=not p.exists()
    with p.open('a',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(row.keys()))
        if new: w.writeheader()
        w.writerow(row)

def html_player(path,poster,mime):
    if path.stat().st_size>260*1024*1024: return st.video(str(path))
    vb64=base64.b64encode(path.read_bytes()).decode(); pa=''
    if poster and poster.exists():
        pm='image/png' if poster.suffix.lower()=='.png' else 'image/jpeg'; pa=f"poster='data:{pm};base64,{base64.b64encode(poster.read_bytes()).decode()}'"
    components.html(f"<video controls preload='metadata' style='width:100%;max-height:620px;background:#000;border-radius:16px' {pa}><source src='data:{mime};base64,{vb64}' type='{mime}'></video>",height=680)

def hls(src,sid):
    log=LOG/f'{sid}.log'; od=OUT/f'abr_{sid[:8]}'; od.mkdir(exist_ok=True); lines=['#EXTM3U','#EXT-X-VERSION:3']
    for w,h,br in [(426,240,'400k'),(854,480,'900k'),(1280,720,'2200k')]:
        name=f'{h}p.m3u8'; cmd=[ffinfo()['ffmpeg'],'-hide_banner','-y','-i',str(src),'-vf',f'scale=w={w}:h={h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2','-c:v','libx264' if has_encoder('libx264') else 'h264','-preset','veryfast','-b:v',br,'-maxrate',br,'-bufsize',str(int(br[:-1])*2)+'k','-c:a','aac','-b:a','96k','-f','hls','-hls_time','4','-hls_playlist_type','vod','-hls_segment_filename',str(od/f'{h}p_%03d.ts'),str(od/name)]
        subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1800)
        if (od/name).exists(): lines += [f'#EXT-X-STREAM-INF:BANDWIDTH={int(br[:-1])*1000},RESOLUTION={w}x{h}',name]
    master=od/'master.m3u8'; master.write_text('\n'.join(lines)); return master,log

st.markdown("""<div class='hero'><h1>🎬 VideoForge Studio</h1><p>Light UI app for professional encoding, AI enhancement, quality analytics, CRF sweep, ABR simulation, universal playback, WebRTC and image overlay.</p><span class='badge'>H.264</span><span class='badge'>HEVC</span><span class='badge'>AV1</span><span class='badge'>VMAF/PSNR/SSIM</span><span class='badge'>Progress Bar</span></div>""",unsafe_allow_html=True)
info=ffinfo()
with st.sidebar:
    st.subheader('System readiness'); st.write('FFmpeg:', '✅ Ready' if info['ffmpeg'] else '❌ Missing'); st.caption(info['version']); st.write('FFprobe:', '✅ Ready' if info['ffprobe'] else '❌ Missing'); st.caption(f"x264 {'✅' if has_encoder('libx264') else '⚠️'} · x265 {'✅' if has_encoder('libx265') else '⚠️'} · AV1 {'✅' if has_encoder('libsvtav1') or has_encoder('libaom-av1') else '⚠️'}"); st.info('For Streamlit Cloud, keep packages.txt with ffmpeg and redeploy.')
for k in ['src','out','img']:
    if k not in st.session_state: st.session_state[k]=None
enc,play,qa,sweep,abr,logs=st.tabs(['Encode','Universal Player','Quality','CRF Sweep','ABR Simulation','Logs'])
with enc:
    l,r=st.columns([.36,.64],gap='large')
    with l:
        st.markdown("<div class='sec'>Source</div>",unsafe_allow_html=True); up=st.file_uploader('Upload video',type=['mp4','mov','mkv','webm','avi','m4v','ts']); im=st.file_uploader('Attach image/logo/poster',type=['png','jpg','jpeg','webp'])
        if up:
            p=save(up,IN); st.session_state.src=str(p); m=media(p); st.success(p.name); a,b=st.columns(2); a.metric('Resolution',f"{m['width']}×{m['height']}"); b.metric('Size',f"{m['size_mb']:.2f} MB"); a.metric('Codec',m['codec'].upper()); b.metric('FPS',m['fps'])
        if im:
            ip=save(im,IN); st.session_state.img=str(ip); st.image(str(ip),caption='Attached image',use_container_width=True)
        st.markdown("<div class='sec'>Encoder Settings</div>",unsafe_allow_html=True); codec=st.selectbox('Video Codec',['AVC (H.264)','HEVC (H.265)','AV1']); crf=st.slider('CRF Quality',14,40,23); preset=st.selectbox('Preset',['veryfast','fast','medium','slow'],index=1)
    with r:
        st.markdown("<div class='sec'>AI Video Enhancement</div>",unsafe_allow_html=True); c1,c2,c3,c4=st.columns(4); denoise=c1.checkbox('Denoise'); sharpen=c1.checkbox('Sharpen'); deblock=c2.checkbox('Deblock'); color=c2.checkbox('Color boost'); hdr_sdr=c3.checkbox('HDR → SDR'); interp=c3.checkbox('Interpolation'); scale_to=c4.selectbox('Target size',['Source','480p','720p','1080p','2160p']); image_mode=st.selectbox('Attached image behavior',['Ignore image','Watermark / logo overlay','Poster only in player'],index=1); p1,p2=st.columns(2); logo_pos=p1.selectbox('Logo position',['Top right','Top left','Bottom right','Bottom left']); logo_scale=p2.slider('Logo scale %',5,35,14)
        active=[x for x,on in [('Denoise',denoise),('Sharpen',sharpen),('Deblock',deblock),('Color',color),('HDR→SDR',hdr_sdr),('Interpolation',interp),('Resize',scale_to!='Source')] if on]; st.markdown(f"<div class='info'>⏱️ Active: {', '.join(active) if active else 'No enhancement selected'}</div>",unsafe_allow_html=True)
        if st.button('✨ Enhance + Encode',type='primary',use_container_width=True):
            if not st.session_state.src: st.error('Upload a source video first.')
            else:
                sid=uuid.uuid4().hex; src=Path(st.session_state.src); logo=Path(st.session_state.img) if st.session_state.img else None; o=dict(codec=codec,crf=crf,preset=preset,denoise=denoise,sharpen=sharpen,deblock=deblock,color=color,hdr_sdr=hdr_sdr,interp=interp,scale_to=scale_to,image_mode=image_mode,logo_pos=logo_pos,logo_scale=logo_scale)
                bar=st.progress(0.0,text='Starting FFmpeg encode…')
                out,log,md=encode(src,logo,o,sid,cb=lambda p,t: bar.progress(float(p),text=t))
                if not out: st.error(md.get('error','Failed')); st.code(md.get('tail',''))
                else:
                    st.session_state.out=str(out); sm,dm=media(src),media(out); q=quality(src,out,sid); saved=(1-dm['size_mb']/sm['size_mb'])*100 if sm['size_mb'] else 0; row={'timestamp':datetime.now().isoformat(timespec='seconds'),'source':src.name,'output':out.name,'codec':codec,'crf':crf,'source_mb':round(sm['size_mb'],3),'output_mb':round(dm['size_mb'],3),'saved_pct':round(saved,2),'PSNR':q.get('PSNR'),'SSIM':q.get('SSIM'),'VMAF':q.get('VMAF'),'VMAF_proxy':q.get('VMAF_proxy'),'log':str(log)}; csvrow(row); st.success(f"Done · {dm['size_mb']:.2f} MB · saved {saved:.1f}%"); a,b,c,d=st.columns(4); a.metric('Output size',f"{dm['size_mb']:.2f} MB",f'{saved:.1f}%'); b.metric('Bitrate',f"{dm['bitrate_kbps']:.0f} kbps"); c.metric('SSIM',f"{q.get('SSIM',0):.4f}" if q.get('SSIM') else '—'); d.metric('VMAF',f"{q.get('VMAF',q.get('VMAF_proxy',0)):.2f}" if (q.get('VMAF') or q.get('VMAF_proxy')) else '—'); st.download_button('Download output',out.read_bytes(),out.name,md.get('mime','application/octet-stream')); st.download_button('Download log',log.read_bytes(),log.name,'text/plain')
with play:
    p=Path(st.session_state.out) if st.session_state.out and Path(st.session_state.out).exists() else None
    if not p:
        up=st.file_uploader('Upload media for playback',type=['mp4','webm','mov','mkv'],key='play'); p=save(up,IN) if up else None
    if p: html_player(p,Path(st.session_state.img) if st.session_state.img and Path(st.session_state.img).exists() else None,'video/webm' if p.suffix.lower()=='.webm' else 'video/mp4')
    st.markdown("<div class='sec'>WebRTC Preview</div>",unsafe_allow_html=True)
    if WEBRTC_AVAILABLE: webrtc_streamer(key='webrtc',rtc_configuration=RTCConfiguration({'iceServers':[{'urls':['stun:stun.l.google.com:19302']}]}),media_stream_constraints={'video':True,'audio':False})
    else: st.warning('streamlit-webrtc not installed.')
with qa:
    a,b=st.columns(2); r=a.file_uploader('Reference/source',type=['mp4','mov','mkv','webm'],key='ref'); d=b.file_uploader('Encoded/distorted',type=['mp4','mov','mkv','webm'],key='dist')
    if st.button('Calculate PSNR / SSIM / VMAF'):
        if r and d: st.json(quality(save(r,IN),save(d,IN),uuid.uuid4().hex))
        else: st.error('Upload both files.')
with sweep:
    if not st.session_state.src:
        su=st.file_uploader('Upload source for sweep',type=['mp4','mov','mkv','webm'],key='sweepup')
        if su: st.session_state.src=str(save(su,IN))
    c=st.selectbox('Codec',['AVC (H.264)','HEVC (H.265)','AV1'],key='sweepcodec'); start=st.number_input('CRF Start',10,45,18); end=st.number_input('CRF End',int(start)+1,51,38); step=st.number_input('Step',1,10,10)
    if st.button('🚀 Run CRF Sweep') and st.session_state.src:
        rows=[]; prog=st.progress(0); crfs=list(range(int(start),int(end)+1,int(step))); src=Path(st.session_state.src)
        for i,x in enumerate(crfs):
            prog.progress(i/len(crfs),text=f'Encoding CRF {x} ({i+1}/{len(crfs)})…'); out,log,md=encode(src,None,dict(codec=c,crf=x,preset='fast',denoise=False,sharpen=False,deblock=False,color=False,hdr_sdr=False,interp=False,scale_to='Source',image_mode='Ignore image',logo_pos='Top right',logo_scale=14),uuid.uuid4().hex)
            if out: dm=media(out); q=quality(src,out,uuid.uuid4().hex); rows.append({'CRF':x,'Size MB':round(dm['size_mb'],2),'Bitrate kbps':round(dm['bitrate_kbps']),'SSIM':q.get('SSIM'),'VMAF':q.get('VMAF',q.get('VMAF_proxy')),'File':out.name})
        prog.progress(1.0,text='CRF sweep complete')
        if rows:
            df=pd.DataFrame(rows); st.dataframe(df,use_container_width=True); st.download_button('Download CSV',df.to_csv(index=False).encode(),'crf_sweep.csv','text/csv')
with abr:
    src=Path(st.session_state.out) if st.session_state.out and Path(st.session_state.out).exists() else None
    if not src:
        au=st.file_uploader('Upload source/output for ABR ladder',type=['mp4','mov','mkv','webm'],key='abrup'); src=save(au,IN) if au else None
    if st.button('Generate HLS ABR Ladder') and src:
        master,log=hls(src,uuid.uuid4().hex); zp=OUT/f'abr_package_{int(time.time())}.zip'
        with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
            for p in master.parent.glob('*'): z.write(p,p.name)
        st.code(master.read_text()); st.download_button('Download ABR package',zp.read_bytes(),zp.name,'application/zip')
with logs:
    p=LOG/'sessions.csv'
    if p.exists(): st.dataframe(pd.read_csv(p).tail(100),use_container_width=True); st.download_button('Download sessions CSV',p.read_bytes(),'sessions.csv','text/csv')
    ls=sorted(LOG.glob('*.log'),key=lambda x:x.stat().st_mtime,reverse=True)
    if ls:
        s=st.selectbox('Log file',ls,format_func=lambda x:x.name); st.text_area('Preview',s.read_text(errors='ignore')[-8000:],height=320); st.download_button('Download selected log',s.read_bytes(),s.name,'text/plain')
