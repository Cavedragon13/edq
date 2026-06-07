#!/usr/bin/env python3
"""Gemma 4 E4B Chat Server — streaming chat UI with image support over Ollama"""
import http.server, json, urllib.request, os, base64, mimetypes

LYRICS_SYSTEM_PROMPT = """You are an expert lyricist and editor. The user will give you draft song lyrics.
Your job: improve them — sharpen the language, fix weak rhymes or awkward meter, add vivid imagery and emotional punch — while preserving the original meaning, theme, and structure.
Keep every section tag exactly as-is ([Verse 1], [Chorus], [Bridge], etc.).
Return ONLY the improved lyrics. No commentary, no explanation, no preamble."""

LYRICS_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lyric Enhancer — Gemma 4</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font-family:system-ui,-apple-system,sans-serif;min-height:100vh;display:flex;flex-direction:column}
header{padding:14px 20px;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:12px}
header h1{font-size:1.1rem;font-weight:600;color:#7ee787}
.badge{background:#6e40c9;color:#e6edf3;font-size:.7rem;padding:2px 8px;border-radius:99px}
nav a{color:#58a6ff;font-size:.85rem;text-decoration:none;padding:4px 10px;border:1px solid #30363d;border-radius:6px}
nav a:hover{background:#161b22}
main{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px;max-width:1400px;width:100%}
.panel{display:flex;flex-direction:column;gap:10px}
h2{font-size:.9rem;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.05em}
textarea{flex:1;background:#161b22;border:1px solid #30363d;color:#e6edf3;border-radius:8px;padding:12px;
  font-size:.95rem;font-family:inherit;resize:vertical;min-height:320px;line-height:1.6}
textarea:focus{outline:none;border-color:#388bfd}
textarea[readonly]{border-color:#21262d;color:#c9d1d9}
.context-row{display:flex;flex-direction:column;gap:6px}
.context-row label{font-size:.8rem;color:#8b949e}
.context-row input{background:#161b22;border:1px solid #30363d;color:#e6edf3;border-radius:6px;
  padding:8px 10px;font-size:.9rem;font-family:inherit}
.context-row input:focus{outline:none;border-color:#388bfd}
.btn-row{display:flex;gap:8px}
button{border:none;border-radius:8px;padding:10px 18px;cursor:pointer;font-size:.9rem;font-weight:500}
#enhance-btn{background:#238636;color:#fff;flex:1}
#enhance-btn:disabled{opacity:.4;cursor:not-allowed}
#copy-btn{background:#161b22;color:#e6edf3;border:1px solid #30363d}
#copy-btn:hover{border-color:#58a6ff;color:#58a6ff}
#copy-btn.copied{border-color:#238636;color:#7ee787}
#status{font-size:.8rem;color:#8b949e;min-height:1.2em}
#status.working{color:#f0883e}
#status.done{color:#7ee787}
#status.err{color:#f85149}
</style></head>
<body>
<header>
  <h1>🎵 Lyric Enhancer</h1>
  <span class="badge">Gemma 4</span>
  <nav><a href="/">💬 Chat</a></nav>
</header>
<main>
  <div class="panel">
    <h2>Your Lyrics</h2>
    <div class="context-row">
      <label>Style / context (optional) — e.g. "dark country ballad, heartbreak"</label>
      <input id="style" type="text" placeholder="genre, mood, theme...">
    </div>
    <textarea id="input-lyrics" placeholder="[Verse 1]&#10;Paste your draft lyrics here...&#10;&#10;[Chorus]&#10;..."></textarea>
    <div class="btn-row">
      <button id="enhance-btn" onclick="enhance()">✨ Enhance Lyrics</button>
    </div>
    <div id="status"></div>
  </div>
  <div class="panel">
    <h2>Enhanced Lyrics</h2>
    <textarea id="output-lyrics" readonly placeholder="Enhanced lyrics will appear here..."></textarea>
    <div class="btn-row">
      <button id="copy-btn" onclick="copyResult()">📋 Copy</button>
    </div>
  </div>
</main>
<script>
async function enhance() {
  const lyrics = document.getElementById('input-lyrics').value.trim();
  if (!lyrics) return;
  const style = document.getElementById('style').value.trim();
  const btn = document.getElementById('enhance-btn');
  const status = document.getElementById('status');
  const out = document.getElementById('output-lyrics');

  btn.disabled = true;
  out.value = '';
  status.className = 'working';
  status.textContent = 'Enhancing…';

  const userContent = style
    ? `Style/context: ${style}\n\n${lyrics}`
    : lyrics;

  try {
    const resp = await fetch('/enhance-lyrics', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({lyrics: userContent})
    });
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const obj = JSON.parse(line);
          if (obj.delta) out.value += obj.delta;
          if (obj.error) { status.className='err'; status.textContent=obj.error; }
        } catch {}
      }
    }
    status.className = 'done';
    status.textContent = 'Done.';
  } catch (e) {
    status.className = 'err';
    status.textContent = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
  }
}

function copyResult() {
  const text = document.getElementById('output-lyrics').value;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('copy-btn');
    btn.textContent = '✓ Copied';
    btn.className = 'copied';
    setTimeout(() => { btn.textContent = '📋 Copy'; btn.className = ''; }, 2000);
  });
}
</script>
</body></html>
"""

PORT         = int(os.environ.get("GEMMA4_PORT", 8043))
OLLAMA       = "http://localhost:11434"

# Selectable models — each maps to the Ollama tag used for text vs. image requests.
# Gemma 4 12B is unified (encoder-free): one tag serves both text and vision.
# E4B keeps its existing abliterated text tag + separate vision tag (gemma4:e4b + mmproj).
MODELS = {
    "gemma4-12b": {"text": "gemma4:12b",        "vision": "gemma4:12b"},
    "e4b":        {"text": "gemma4-obliterated", "vision": "gemma4-vision"},
}
DEFAULT_MODEL = "gemma4-12b"

# Back-compat aliases for callers without a selector (e.g. the lyrics enhancer).
MODEL_TEXT   = MODELS[DEFAULT_MODEL]["text"]
MODEL_VISION = MODELS[DEFAULT_MODEL]["vision"]

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gemma 4 E4B</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font-family:system-ui,-apple-system,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#layout{flex:1;display:flex;overflow:hidden}
/* Sidebar */
#sidebar{width:220px;min-width:220px;background:#010409;border-right:1px solid #21262d;display:flex;flex-direction:column;transition:width .2s,min-width .2s;overflow:hidden}
#sidebar.collapsed{width:0;min-width:0}
#sb-head{padding:10px 10px;display:flex;gap:8px;border-bottom:1px solid #21262d;flex-shrink:0}
#new-btn{flex:1;background:#238636;color:#fff;border:none;border-radius:6px;padding:7px 8px;cursor:pointer;font-size:.82rem;white-space:nowrap}
#new-btn:hover{background:#2ea043}
#convo-list{flex:1;overflow-y:auto;padding:4px 0}
.ci{display:flex;align-items:center;padding:7px 10px;cursor:pointer;gap:6px;border-left:2px solid transparent}
.ci:hover{background:#161b22}
.ci.active{background:#161b22;border-left-color:#7ee787}
.ct{flex:1;font-size:.78rem;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;color:#c9d1d9}
.cd{font-size:.68rem;color:#484f58;white-space:nowrap}
.cx{background:none;border:none;color:#484f58;cursor:pointer;font-size:.8rem;padding:0 2px;opacity:0;line-height:1}
.ci:hover .cx{opacity:1}
.cx:hover{color:#f85149}
/* Main */
#main{flex:1;display:flex;flex-direction:column;overflow:hidden}
header{padding:10px 14px;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:8px;flex-shrink:0}
#tog{background:none;border:none;color:#8b949e;cursor:pointer;font-size:1.1rem;padding:3px 5px;border-radius:4px;line-height:1}
#tog:hover{background:#161b22;color:#e6edf3}
header h1{font-size:1rem;font-weight:600;color:#7ee787;white-space:nowrap}
.badge{background:#238636;color:#e6edf3;font-size:.68rem;padding:2px 7px;border-radius:99px}
#htitle{font-size:.82rem;color:#8b949e;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;flex:1;margin-left:4px}
nav a{color:#58a6ff;font-size:.8rem;text-decoration:none;padding:3px 9px;border:1px solid #30363d;border-radius:6px;white-space:nowrap}
nav a:hover{background:#161b22}
#model-sel{background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:4px 8px;font-size:.78rem;font-family:inherit;cursor:pointer}
#model-sel:hover{border-color:#8b949e}
#model-sel:focus{outline:none;border-color:#388bfd}
#chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:12px 16px;border-radius:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word}
.user{align-self:flex-end;background:#1f6feb;border-radius:12px 12px 4px 12px}
.bot{align-self:flex-start;background:#161b22;border:1px solid #21262d;border-radius:12px 12px 12px 4px}
.bot.streaming::after{content:"▋";animation:blink .7s infinite}
details.thinking{align-self:flex-start;background:#0d1117;border:1px dashed #30363d;border-radius:8px;
  font-size:.8rem;color:#8b949e;padding:8px 12px;max-width:80%;white-space:pre-wrap;word-break:break-word}
details.thinking summary{cursor:pointer;color:#58a6ff;margin-bottom:4px}
.img-preview{align-self:flex-end;max-width:320px;border-radius:8px;border:1px solid #30363d;margin-bottom:4px}
@keyframes blink{50%{opacity:0}}
footer{border-top:1px solid #21262d;flex-shrink:0}
#drop-zone{padding:0 20px;display:flex;flex-direction:column;gap:4px}
#pending-img{display:none;position:relative;width:fit-content;padding-top:8px}
#pending-img img{max-height:80px;max-width:160px;border-radius:6px;border:1px solid #388bfd}
#clear-img{position:absolute;top:2px;right:-6px;background:#da3633;color:#fff;border:none;
  border-radius:50%;width:18px;height:18px;font-size:10px;cursor:pointer;line-height:18px;text-align:center}
#input-row{display:flex;gap:8px;padding:10px 20px 12px;align-items:flex-end}
#inp{flex:1;background:#161b22;border:1px solid #30363d;color:#e6edf3;border-radius:8px;
  padding:10px;font-size:.95rem;resize:none;max-height:120px;font-family:inherit}
#inp:focus{outline:none;border-color:#388bfd}
#inp.drag-over{border-color:#7ee787;background:#0f2016}
.icon-btn{background:#161b22;color:#8b949e;border:1px solid #30363d;border-radius:8px;
  padding:9px 12px;cursor:pointer;font-size:1rem;line-height:1;white-space:nowrap}
.icon-btn:hover{color:#e6edf3;border-color:#8b949e}
.icon-btn.active{color:#f85149;border-color:#f85149;background:#1a0505}
#btn{background:#238636;color:#fff;border:none;border-radius:8px;padding:10px 18px;
  cursor:pointer;font-size:.95rem;white-space:nowrap}
#btn:disabled{opacity:.4;cursor:not-allowed}
</style></head>
<body>
<header>
  <button id="tog" onclick="toggleSidebar()" title="History">=</button>
  <h1>&#129408; Gemma 4</h1>
  <select id="model-sel" title="Model" aria-label="Model">
    <option value="gemma4-12b">Gemma 4 12B</option>
    <option value="e4b">Gemma 4 E4B</option>
  </select>
  <span id="htitle"></span>
  <nav style="margin-left:auto"><a href="/lyrics">&#127926; Lyrics</a></nav>
</header>
<div id="layout">
  <div id="sidebar">
    <div id="sb-head"><button id="new-btn" onclick="newChat()">+ New Chat</button></div>
    <div id="convo-list"></div>
  </div>
  <div id="main">
    <div id="chat"></div>
    <footer>
      <div id="drop-zone">
        <div id="pending-img"><img id="pending-thumb" src="" alt=""><button id="clear-img" title="Remove">&#x2715;</button></div>
      </div>
      <div id="input-row">
        <textarea id="inp" rows="1" placeholder="Message Gemma 4&#x2026; (drag &amp; drop image)"
          onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"
          ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)"
          ondrop="handleDrop(event)"></textarea>
        <button id="mic-btn" class="icon-btn" onclick="toggleMic()" title="Voice input">&#127908;</button>
        <button id="btn" onclick="send()">Send</button>
      </div>
    </footer>
  </div>
</div>
<input type="file" id="file-input" accept="image/*" style="display:none" onchange="handleFileSelect(event)">
<script>
const chatEl=document.getElementById('chat');
const inp=document.getElementById('inp');
const btn=document.getElementById('btn');
const pendingImg=document.getElementById('pending-img');
const pendingThumb=document.getElementById('pending-thumb');
const micBtn=document.getElementById('mic-btn');
let pendingImageB64=null,pendingImageType=null,currentId=null;

// ── Model selector (persisted) ───────────────────────────────
const MK='gemma4_model';
const modelSel=document.getElementById('model-sel');
modelSel.value=localStorage.getItem(MK)||'gemma4-12b';
modelSel.addEventListener('change',()=>localStorage.setItem(MK,modelSel.value));

// ── Sidebar & storage ────────────────────────────────────────
const SK='gemma4_convos';
function loadAll(){try{return JSON.parse(localStorage.getItem(SK))||[];}catch{return[];}}
function saveAll(cs){localStorage.setItem(SK,JSON.stringify(cs));}
function getConvo(id){return loadAll().find(c=>c.id===id)||null;}
function upsertConvo(c){const a=loadAll();const i=a.findIndex(x=>x.id===c.id);if(i>=0)a[i]=c;else a.unshift(c);saveAll(a);}
function genId(){return Date.now().toString(36)+Math.random().toString(36).slice(2,6);}

function toggleSidebar(){document.getElementById('sidebar').classList.toggle('collapsed');}

function renderSidebar(){
  const list=document.getElementById('convo-list');
  while(list.firstChild)list.removeChild(list.firstChild);
  const convos=loadAll();
  if(!convos.length){
    const em=document.createElement('div');
    em.style.cssText='padding:12px;font-size:.76rem;color:#484f58';
    em.textContent='No history yet';
    list.appendChild(em); return;
  }
  convos.forEach(c=>{
    const item=document.createElement('div');
    item.className='ci'+(c.id===currentId?' active':'');
    const t=document.createElement('span'); t.className='ct'; t.title=c.title; t.textContent=c.title;
    const d=document.createElement('span'); d.className='cd';
    d.textContent=new Date(c.created).toLocaleDateString(undefined,{month:'short',day:'numeric'});
    const x=document.createElement('button'); x.className='cx'; x.title='Delete'; x.textContent='\u2715';
    x.addEventListener('click',e=>{e.stopPropagation();delConvo(c.id);});
    item.append(t,d,x);
    item.addEventListener('click',()=>loadChat(c.id));
    list.appendChild(item);
  });
}

function delConvo(id){saveAll(loadAll().filter(c=>c.id!==id));if(currentId===id)newChat();else renderSidebar();}

function newChat(){
  currentId=null; chatEl.textContent='';
  document.getElementById('htitle').textContent='';
  renderSidebar(); inp.focus();
}
function loadChat(id){
  const c=getConvo(id); if(!c)return;
  currentId=id; chatEl.textContent='';
  document.getElementById('htitle').textContent=c.title;
  c.messages.forEach(m=>{
    if(m.role==='user') addMsg('user',m.content==='(image)'?'[image]':m.content);
    else if(m.role==='assistant') addMsg('bot',m.content);
  });
  chatEl.scrollTop=chatEl.scrollHeight; renderSidebar();
}
function getHistory(){if(!currentId)return[];const c=getConvo(currentId);return c?c.messages:[];}
function pushMsg(msg){
  if(!currentId)return;
  const c=getConvo(currentId)||{id:currentId,title:'',created:Date.now(),messages:[]};
  c.messages.push(msg); upsertConvo(c);
}

// ── Mic (Web Speech API) ─────────────────────────────────────
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
let recog=null, micActive=false;
if(!SR) micBtn.title='Speech recognition not supported in this browser';
function toggleMic(){
  if(!SR){alert('Speech recognition not supported in this browser.');return;}
  if(micActive){recog&&recog.stop();return;}
  recog=new SR(); recog.continuous=true; recog.interimResults=true; recog.lang='en-US';
  let base=inp.value;
  recog.onresult=e=>{
    let interim='';
    for(let i=e.resultIndex;i<e.results.length;i++){
      if(e.results[i].isFinal) base+=e.results[i][0].transcript+' ';
      else interim=e.results[i][0].transcript;
    }
    inp.value=base+interim;
    inp.style.height='auto'; inp.style.height=inp.scrollHeight+'px';
  };
  recog.onerror=e=>{console.warn('Speech error',e.error);stopMic();};
  recog.onend=()=>stopMic();
  recog.start(); micActive=true; micBtn.classList.add('active'); micBtn.title='Stop recording';
}
function stopMic(){micActive=false;micBtn.classList.remove('active');micBtn.title='Voice input';recog=null;}

// ── Image helpers ────────────────────────────────────────────
document.getElementById('clear-img').onclick=()=>clearPendingImage();
function clearPendingImage(){pendingImageB64=null;pendingImageType=null;pendingImg.style.display='none';pendingThumb.src='';}
function setPendingImage(b64,type){pendingImageB64=b64;pendingImageType=type;pendingThumb.src='data:'+type+';base64,'+b64;pendingImg.style.display='block';}
function readFileAsB64(file){return new Promise((res,rej)=>{const fr=new FileReader();fr.onload=e=>{res({b64:e.target.result.split(',')[1],type:file.type||'image/png'});};fr.onerror=rej;fr.readAsDataURL(file);});}
function handleDragOver(e){e.preventDefault();inp.classList.add('drag-over');}
function handleDragLeave(){inp.classList.remove('drag-over');}
async function handleDrop(e){e.preventDefault();inp.classList.remove('drag-over');const f=[...e.dataTransfer.files].filter(x=>x.type.startsWith('image/'));if(!f.length)return;const{b64,type}=await readFileAsB64(f[0]);setPendingImage(b64,type);}
async function handleFileSelect(e){const f=e.target.files[0];if(!f)return;const{b64,type}=await readFileAsB64(f);setPendingImage(b64,type);}

// ── Chat rendering ───────────────────────────────────────────
function addMsg(cls,text){const d=document.createElement('div');d.className='msg '+cls;d.textContent=text;chatEl.appendChild(d);chatEl.scrollTop=chatEl.scrollHeight;return d;}
function addImgPreview(b64,type){const img=document.createElement('img');img.className='img-preview';img.src='data:'+type+';base64,'+b64;chatEl.appendChild(img);chatEl.scrollTop=chatEl.scrollHeight;}
function addThinking(){const d=document.createElement('details');d.className='thinking';const s=document.createElement('summary');s.textContent='Thinking\u2026';d.appendChild(s);const p=document.createElement('span');d.appendChild(p);chatEl.appendChild(d);chatEl.scrollTop=chatEl.scrollHeight;return p;}

// ── Send ─────────────────────────────────────────────────────
async function send(){
  const text=inp.value.trim();
  if(!text&&!pendingImageB64)return;
  if(micActive){recog&&recog.stop();}
  inp.value=''; inp.style.height='auto'; btn.disabled=true;

  if(!currentId){
    currentId=genId();
    const title=(text||'image').slice(0,45);
    upsertConvo({id:currentId,title,created:Date.now(),messages:[]});
    document.getElementById('htitle').textContent=title;
    renderSidebar();
  }

  const userMsg={role:'user',content:text||'(image)'};
  if(pendingImageB64)userMsg.images=[pendingImageB64];
  if(pendingImageB64)addImgPreview(pendingImageB64,pendingImageType);
  if(text)addMsg('user',text);
  pushMsg(userMsg);

  const hist=getHistory();
  const payload=hist.map((m,i)=>{const o={role:m.role,content:m.content};if(m.images&&i===hist.length-1)o.images=m.images;return o;});
  clearPendingImage();

  let thinkBuf='',responseBuf='',inThink=false,thinkEl=null,botBubble=null;
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:payload,model:modelSel.value})});
    if(!r.ok)throw new Error('HTTP '+r.status);
    const reader=r.body.getReader(),dec=new TextDecoder();
    while(true){
      const{done,value}=await reader.read();if(done)break;
      for(const line of dec.decode(value).split('\n')){
        if(!line.trim())continue;
        let obj;try{obj=JSON.parse(line);}catch{continue;}
        const delta=obj.delta||'';if(!delta)continue;
        let buf=delta;
        while(buf.length){
          if(!inThink){
            const ti=buf.indexOf('<think>');
            if(ti===-1){
              responseBuf+=buf;
              if(!botBubble){botBubble=addMsg('bot','');botBubble.classList.add('streaming');}
              botBubble.textContent=responseBuf;
              chatEl.scrollTop=chatEl.scrollHeight; buf='';
            } else {
              const pre=buf.slice(0,ti);
              if(pre){responseBuf+=pre;
                if(!botBubble){botBubble=addMsg('bot','');botBubble.classList.add('streaming');}
                botBubble.textContent=responseBuf;}
              inThink=true; buf=buf.slice(ti+7);
            }
          } else {
            const te=buf.indexOf('</think>');
            if(te===-1){
              thinkBuf+=buf;
              if(!thinkEl) thinkEl=addThinking();
              thinkEl.textContent=thinkBuf;
              chatEl.scrollTop=chatEl.scrollHeight; buf='';
            } else {
              thinkBuf+=buf.slice(0,te);
              if(!thinkEl) thinkEl=addThinking();
              thinkEl.textContent=thinkBuf;
              inThink=false; buf=buf.slice(te+8);
            }
          }
        }
      }
    }
  } catch(e){
    const m='[error: '+e.message+']';
    if(botBubble) botBubble.textContent=m; else addMsg('bot',m);
  }
  if(botBubble) botBubble.classList.remove('streaming');
  pushMsg({role:'assistant',content:responseBuf});
  btn.disabled=false; inp.focus();
}
</script></body></html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            b = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(b))
            self.end_headers(); self.wfile.write(b)
        elif self.path in ("/lyrics", "/lyrics.html"):
            b = LYRICS_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(b))
            self.end_headers(); self.wfile.write(b)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "9")
            self.end_headers(); self.wfile.write(b"Not found")

    def do_POST(self):
        if self.path == "/enhance-lyrics":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            lyrics = body.get("lyrics", "")
            payload = json.dumps({
                "model": MODEL_TEXT,
                "messages": [
                    {"role": "system", "content": LYRICS_SYSTEM_PROMPT},
                    {"role": "user", "content": lyrics},
                ],
                "stream": True
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                req = urllib.request.Request(
                    f"{OLLAMA}/api/chat", data=payload,
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=300) as resp:
                    for raw in resp:
                        obj = json.loads(raw.decode())
                        delta = obj.get("message", {}).get("content", "")
                        if delta:
                            line = (json.dumps({"delta": delta}) + "\n").encode()
                            self.wfile.write(line); self.wfile.flush()
            except Exception as e:
                try:
                    self.wfile.write((json.dumps({"error": str(e)}) + "\n").encode())
                except: pass
            return

        if self.path != "/chat":
            self.send_response(404)
            self.send_header("Content-Length", "9")
            self.end_headers(); self.wfile.write(b"Not found"); return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        messages = body.get("messages", [])
        sel = MODELS.get(body.get("model"), MODELS[DEFAULT_MODEL])

        # Build Ollama messages — images stay as-is (already base64 strings)
        has_images = False
        ollama_messages = []
        for m in messages:
            om = {"role": m["role"], "content": m.get("content", "")}
            if "images" in m:
                om["images"] = m["images"]  # list of base64 strings
                has_images = True
            ollama_messages.append(om)

        # Route: vision tag when images present, text tag otherwise (per selected model)
        model = sel["vision"] if has_images else sel["text"]

        payload = json.dumps({
            "model": model,
            "messages": ollama_messages,
            "stream": True
        }).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            req = urllib.request.Request(
                f"{OLLAMA}/api/chat", data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw in resp:
                    obj = json.loads(raw.decode())
                    delta = obj.get("message", {}).get("content", "")
                    if delta:
                        line = (json.dumps({"delta": delta}) + "\n").encode()
                        self.wfile.write(line); self.wfile.flush()
        except Exception as e:
            try:
                self.wfile.write((json.dumps({"delta": f"[error: {e}]"}) + "\n").encode())
            except: pass

if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Gemma 4 E4B chat on http://0.0.0.0:{PORT} (image drag-and-drop enabled)", flush=True)
    srv.serve_forever()
