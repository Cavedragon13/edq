#!/usr/bin/env python3
"""Gemma 4 E4B Chat Server — minimal streaming chat UI over Ollama"""
import http.server, json, urllib.request, urllib.error, threading, os, sys, re

PORT = int(os.environ.get("GEMMA4_PORT", 8043))
OLLAMA = "http://localhost:11434"
MODEL  = "gemma4:e4b"

HTML = """<!DOCTYPE html>
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
@keyframes blink{50%{opacity:0}}
footer{padding:12px 20px;border-top:1px solid #21262d;display:flex;gap:8px}
textarea{flex:1;background:#161b22;border:1px solid #30363d;color:#e6edf3;border-radius:8px;padding:10px;font-size:.95rem;resize:none;max-height:120px}
textarea:focus{outline:none;border-color:#388bfd}
button{background:#238636;color:#fff;border:none;border-radius:8px;padding:10px 18px;cursor:pointer;font-size:.95rem;white-space:nowrap}
button:disabled{opacity:.4;cursor:not-allowed}
</style></head>
<body>
<header><h1>&#129408; Gemma 4 E4B</h1><span class="badge">LLM</span></header>
<div id="chat"></div>
<footer>
  <textarea id="inp" rows="1" placeholder="Message Gemma 4…" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"></textarea>
  <button id="btn" onclick="send()">Send</button>
</footer>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),btn=document.getElementById('btn');
let history=[];
function addMsg(role,text){
  const d=document.createElement('div');
  d.className='msg '+(role==='user'?'user':'bot');
  d.textContent=text; chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight; return d;
}
async function send(){
  const text=inp.value.trim(); if(!text)return;
  inp.value=''; btn.disabled=true;
  addMsg('user',text);
  history.push({role:'user',content:text});
  const bubble=addMsg('bot',''); bubble.classList.add('streaming');
  let full='';
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:history})});
    const reader=r.body.getReader(),dec=new TextDecoder();
    while(true){
      const{done,value}=await reader.read(); if(done)break;
      const chunk=dec.decode(value);
      for(const line of chunk.split('\\n')){
        if(!line.trim())continue;
        try{const obj=JSON.parse(line);if(obj.delta){full+=obj.delta;bubble.textContent=full;chat.scrollTop=chat.scrollHeight;}}catch{}
      }
    }
  }catch(e){full='Error: '+e.message; bubble.textContent=full;}
  bubble.classList.remove('streaming');
  history.push({role:'assistant',content:full});
  btn.disabled=false; inp.focus();
}
</script></body></html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send_html(self, code, body, ct="text/html"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ct)
        self.send_header("Content-Length", len(b)); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path in ("/", "/index.html"): self.send_html(200, HTML)
        else: self.send_html(404, "Not found")
    def do_POST(self):
        if self.path != "/chat": self.send_html(404, "Not found"); return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        messages = body.get("messages", [])
        payload = json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
        try:
            req = urllib.request.Request(f"{OLLAMA}/api/chat", data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw in resp:
                    obj = json.loads(raw.decode())
                    delta = obj.get("message", {}).get("content", "")
                    if delta:
                        line = json.dumps({"delta": delta}) + "\n"
                        self.wfile.write(line.encode()); self.wfile.flush()
        except Exception as e:
            self.wfile.write((json.dumps({"delta": f"[error: {e}]"}) + "\n").encode())

if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Gemma 4 E4B chat server on port {PORT}", flush=True)
    srv.serve_forever()
