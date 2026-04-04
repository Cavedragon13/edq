#!/usr/bin/env python3
"""Gemma 4 E4B Chat Server — streaming chat UI with image support over Ollama"""
import http.server, json, urllib.request, os, base64, mimetypes

PORT   = int(os.environ.get("GEMMA4_PORT", 8043))
OLLAMA = "http://localhost:11434"
MODEL  = "gemma4:e4b"

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gemma 4 E4B</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font-family:system-ui,-apple-system,sans-serif;height:100vh;display:flex;flex-direction:column}
header{padding:14px 20px;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:10px}
header h1{font-size:1.1rem;font-weight:600;color:#7ee787}
.badge{background:#238636;color:#e6edf3;font-size:.7rem;padding:2px 8px;border-radius:99px}
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
/* Footer */
footer{border-top:1px solid #21262d}
#drop-zone{padding:0 20px;display:flex;flex-direction:column;gap:6px}
#pending-img{display:none;position:relative;width:fit-content}
#pending-img img{max-height:80px;max-width:160px;border-radius:6px;border:1px solid #388bfd}
#clear-img{position:absolute;top:-6px;right:-6px;background:#da3633;color:#fff;border:none;
  border-radius:50%;width:18px;height:18px;font-size:11px;cursor:pointer;line-height:18px;text-align:center}
#input-row{display:flex;gap:8px;padding:12px 20px 14px}
textarea{flex:1;background:#161b22;border:1px solid #30363d;color:#e6edf3;border-radius:8px;
  padding:10px;font-size:.95rem;resize:none;max-height:120px}
textarea:focus{outline:none;border-color:#388bfd}
textarea.drag-over{border-color:#7ee787;background:#0f2016}
button#btn{background:#238636;color:#fff;border:none;border-radius:8px;padding:10px 18px;
  cursor:pointer;font-size:.95rem;white-space:nowrap;align-self:flex-end}
button#btn:disabled{opacity:.4;cursor:not-allowed}
</style></head>
<body>
<header><h1>&#129408; Gemma 4 E4B</h1><span class="badge">LLM</span></header>
<div id="chat"></div>
<footer>
  <div id="drop-zone">
    <div id="pending-img"><img id="pending-thumb" src="" alt=""><button id="clear-img" title="Remove image">✕</button></div>
  </div>
  <div id="input-row">
    <textarea id="inp" rows="1" placeholder="Message Gemma 4… (drag &amp; drop image here)"
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"
      ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)"
      ondrop="handleDrop(event)"></textarea>
    <button id="btn" onclick="send()">Send</button>
  </div>
</footer>
<input type="file" id="file-input" accept="image/*" style="display:none" onchange="handleFileSelect(event)">
<script>
const chat=document.getElementById('chat');
const inp=document.getElementById('inp');
const btn=document.getElementById('btn');
const pendingImg=document.getElementById('pending-img');
const pendingThumb=document.getElementById('pending-thumb');
const fileInput=document.getElementById('file-input');
let history=[];
let pendingImageB64=null;
let pendingImageType=null;

document.getElementById('clear-img').onclick=()=>clearPendingImage();

function clearPendingImage(){
  pendingImageB64=null; pendingImageType=null;
  pendingImg.style.display='none'; pendingThumb.src='';
}

function setPendingImage(b64, type){
  pendingImageB64=b64; pendingImageType=type;
  pendingThumb.src='data:'+type+';base64,'+b64;
  pendingImg.style.display='block';
}

function readFileAsB64(file){
  return new Promise((res,rej)=>{
    const fr=new FileReader();
    fr.onload=e=>{
      const dataUrl=e.target.result;
      const b64=dataUrl.split(',')[1];
      res({b64, type:file.type||'image/png'});
    };
    fr.onerror=rej;
    fr.readAsDataURL(file);
  });
}

function handleDragOver(e){e.preventDefault();inp.classList.add('drag-over');}
function handleDragLeave(e){inp.classList.remove('drag-over');}
async function handleDrop(e){
  e.preventDefault(); inp.classList.remove('drag-over');
  const files=[...e.dataTransfer.files].filter(f=>f.type.startsWith('image/'));
  if(!files.length) return;
  const {b64,type}=await readFileAsB64(files[0]);
  setPendingImage(b64,type);
}
async function handleFileSelect(e){
  const f=e.target.files[0]; if(!f)return;
  const {b64,type}=await readFileAsB64(f);
  setPendingImage(b64,type);
}

function addMsg(cls,text){
  const d=document.createElement('div');
  d.className='msg '+cls; d.textContent=text;
  chat.appendChild(d); chat.scrollTop=chat.scrollHeight; return d;
}
function addImgPreview(b64,type){
  const img=document.createElement('img');
  img.className='img-preview'; img.src='data:'+type+';base64,'+b64;
  chat.appendChild(img); chat.scrollTop=chat.scrollHeight;
}
function addThinking(){
  const d=document.createElement('details');
  d.className='thinking';
  const s=document.createElement('summary'); s.textContent='Thinking…'; d.appendChild(s);
  const pre=document.createElement('span'); d.appendChild(pre);
  chat.appendChild(d); chat.scrollTop=chat.scrollHeight; return pre;
}

async function send(){
  const text=inp.value.trim();
  if(!text && !pendingImageB64) return;
  inp.value=''; btn.disabled=true;

  // Build user message for history
  const userMsg={role:'user', content:text||'(image)'};
  if(pendingImageB64) userMsg.images=[pendingImageB64];

  // Show in chat
  if(pendingImageB64) addImgPreview(pendingImageB64, pendingImageType);
  if(text) addMsg('user',text);
  history.push(userMsg);
  // Strip images from all but the latest message to avoid ballooning history payload
  history.forEach((m,i) => { if(i < history.length-1) delete m.images; });
  clearPendingImage();

  let thinkBuf='', responseBuf='', inThink=false;
  let thinkEl=null, botBubble=null;

  try{
    const r=await fetch('/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:history})});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const reader=r.body.getReader(), dec=new TextDecoder();
    while(true){
      const{done,value}=await reader.read(); if(done)break;
      for(const line of dec.decode(value).split('\n')){
        if(!line.trim()) continue;
        let obj; try{obj=JSON.parse(line);}catch{continue;}
        const delta=obj.delta||''; if(!delta) continue;
        let buf=delta;
        while(buf.length){
          if(!inThink){
            const ti=buf.indexOf('<think>');
            if(ti===-1){
              responseBuf+=buf;
              if(!botBubble){botBubble=addMsg('bot','');botBubble.classList.add('streaming');}
              botBubble.textContent=responseBuf;
              chat.scrollTop=chat.scrollHeight; buf='';
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
              chat.scrollTop=chat.scrollHeight; buf='';
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
  history.push({role:'assistant',content:responseBuf});
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
        else:
            self.send_response(404)
            self.send_header("Content-Length", "9")
            self.end_headers(); self.wfile.write(b"Not found")

    def do_POST(self):
        if self.path != "/chat":
            self.send_response(404)
            self.send_header("Content-Length", "9")
            self.end_headers(); self.wfile.write(b"Not found"); return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        messages = body.get("messages", [])

        # Build Ollama messages — images stay as-is (already base64 strings)
        ollama_messages = []
        for m in messages:
            om = {"role": m["role"], "content": m.get("content", "")}
            if "images" in m:
                om["images"] = m["images"]  # list of base64 strings
            ollama_messages.append(om)

        payload = json.dumps({
            "model": MODEL,
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
