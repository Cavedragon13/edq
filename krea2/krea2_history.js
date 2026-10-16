// Drafts and runs live on the runner, so every machine sees the same history.
let promptSession = sessionStorage.getItem('krea2-session') ||
  (globalThis.crypto?.randomUUID?.() || Date.now().toString(36) + Math.random().toString(36).slice(2));
sessionStorage.setItem('krea2-session', promptSession);
let sessionName = 'Untitled session';
let draftTimer, restoringHistory = false, saveChain = Promise.resolve();
let draftRevision=0,savedRevision=0;
const historyFields = {prompt:'prompt', width:'width', height:'height', steps:'steps',
  batchCount:'batch_count', seed:'seed', cfg:'cfg_scale', shift:'flow_shift',
  sampler:'sampler', loraMode:'lora_apply_mode', customLora:'custom_lora_tags', strength:'strength'};

function historyPayload(){
  const payload={session_id:promptSession,session_name:sessionName};
  Object.entries(historyFields).forEach(([id,key])=>{payload[key]=qs(id).value;});
  payload.loras=selectedLoras.filter(item=>item.tag).map(item=>({tag:item.tag,weight:item.weight ?? 1}));
  if(sourceImage) payload.init_image={...sourceImage};
  return payload;
}
function saveDraft(){
  clearTimeout(draftTimer);
  if(restoringHistory || draftRevision===savedRevision || !qs('prompt').value.trim()) return saveChain.catch(()=>{});
  const payload=historyPayload();
  const revision=draftRevision;
  saveChain=saveChain.catch(()=>{}).then(()=>json('/api/history/draft',{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)
  })).then(()=>{savedRevision=Math.max(savedRevision,revision);qs('historyButton').title=
    savedRevision===draftRevision?'Draft saved on udragon; available from every machine':'Saving draft…';})
    .catch(e=>{qs('historyButton').title='Draft save failed: '+e.message; throw e;});
  return saveChain;
}
function scheduleDraft(){
  if(restoringHistory) return;
  draftRevision++;
  qs('historyButton').title='Saving draft…';
  clearTimeout(draftTimer);
  draftTimer=setTimeout(()=>saveDraft().catch(()=>{
    qs('msg').textContent='Could not save this draft. Check the connection before switching machines.';
  }),700);
}

const historyDialog=document.createElement('dialog');
historyDialog.id='promptHistory';
historyDialog.style.cssText='width:min(900px,94vw);max-height:85vh;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:12px;padding:20px';
historyDialog.innerHTML=`<div class="actions" style="justify-content:space-between"><h2>Prompt history</h2><button id="closeHistory" class="secondary">Close</button></div>
<p>Saved on udragon. Restore a draft or generation from either machine. Images stay linked to their session.</p>
<label for="sessionName">Current session name</label><input id="sessionName" maxlength="150" placeholder="Name this idea or project">
<div class="actions"><button id="newSession" class="secondary">New session</button></div>
<label for="historySearch">Search prompts or session names</label><input id="historySearch" type="search" placeholder="Find an idea…">
<p id="historyNote" role="status"></p><div id="historyRows"></div>`;
document.body.appendChild(historyDialog);
qs('closeHistory').onclick=()=>historyDialog.close();
qs('sessionName').addEventListener('input',()=>{sessionName=qs('sessionName').value.trim()||'Untitled session';scheduleDraft();});

async function showHistory(){
  qs('sessionName').value=sessionName==='Untitled session'?'':sessionName;
  historyDialog.showModal();
  try{await saveDraft();await loadHistory();}
  catch(e){qs('historyNote').textContent='History could not be loaded: '+e.message;}
}
async function loadHistory(){
  const query=qs('historySearch').value;
  const d=await json('/api/history?q='+encodeURIComponent(query));
  if(query!==qs('historySearch').value) return;
  qs('historyNote').textContent=d.entries.length?'Latest '+d.entries.length+' matching drafts and generations.':'No saved prompts yet.';
  qs('historyRows').replaceChildren();
  d.entries.forEach(entry=>{
    const row=document.createElement('section');
    row.style.cssText='padding:16px 0;border-top:1px solid var(--line)';
    const title=document.createElement('b');title.textContent=entry.name;
    const meta=document.createElement('div');meta.className='mini';
    meta.textContent=new Date(entry.updated).toLocaleString()+' · '+entry.status;
    const prompt=document.createElement('p');prompt.style.whiteSpace='pre-wrap';
    prompt.textContent=entry.prompt.slice(0,900);
    const images=document.createElement('div');images.style.cssText='display:flex;gap:8px;margin:12px 0;flex-wrap:wrap';
    (entry.image_urls||[]).forEach(url=>{
      const link=document.createElement('a');link.href=url;link.target='_blank';link.rel='noopener';
      const img=document.createElement('img');img.src=url;img.loading='lazy';img.alt='Saved generation';
      img.style.cssText='width:90px;height:90px;object-fit:cover;border-radius:6px';link.append(img);images.append(link);
    });
    const restore=document.createElement('button');restore.className='secondary';restore.textContent='Restore prompt & settings';
    restore.onclick=async()=>{
      try{await saveDraft();await restoreHistory(entry.id);historyDialog.close();}
      catch(e){qs('historyNote').textContent='Could not restore: '+e.message;}
    };
    row.append(title,meta,prompt,images,restore);qs('historyRows').append(row);
  });
}
async function restoreHistory(id){
  const entry=await json('/api/history/'+encodeURIComponent(id));
  const payload=entry.payload;
  restoringHistory=true;
  try{
    Object.entries(historyFields).forEach(([control,key])=>{
      if(payload[key]!==undefined) qs(control).value=payload[key];
    });
    selectedLoras=payload.loras||[];renderLoraRows();
    sourceImage=null;qs('initImage').value='';
    if(payload.init_image){
      const image=new Image();
      await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(new Error('Saved source image cannot be loaded'));image.src=payload.init_image.data_url;});
      sourceImage={...payload.init_image,width:image.naturalWidth,height:image.naturalHeight};
    }
    renderSourcePreview();syncAspect();qs('strengthValue').textContent=Number(qs('strength').value).toFixed(2);
    promptSession=entry.session_id;sessionName=entry.name;
    sessionStorage.setItem('krea2-session',promptSession);
    const urls=entry.result.image_urls||[];
    qs('preview').replaceChildren();
    urls.forEach(url=>{const img=new Image();img.src=url;img.alt='Restored generation';qs('preview').append(img);});
    if(!urls.length) qs('preview').textContent='Prompt restored. Generate to continue this idea.';
    qs('msg').textContent=entry.source_missing?'Prompt restored, but its source image is missing. Choose it again before generating.':'Restored “'+entry.name+'”. Ready to continue.';
  }finally{restoringHistory=false;}
  draftRevision++;
  await saveDraft();
}
qs('historyButton').onclick=showHistory;
let historySearchTimer;
qs('historySearch').oninput=()=>{clearTimeout(historySearchTimer);historySearchTimer=setTimeout(()=>loadHistory().catch(e=>{qs('historyNote').textContent=e.message;}),250);};
qs('newSession').onclick=async()=>{
  try{
    await saveDraft();
    promptSession=Date.now().toString(36)+Math.random().toString(36).slice(2);
    sessionName='Untitled session';sessionStorage.setItem('krea2-session',promptSession);
    qs('sessionName').value='';qs('prompt').value='';
    historyDialog.close();qs('prompt').focus();
  }catch(e){qs('historyNote').textContent=e.message;}
};
document.addEventListener('input',event=>{
  if(historyFields[event.target.id] || event.target.closest('#loraRows')) scheduleDraft();
});
document.addEventListener('change',event=>{
  if(historyFields[event.target.id] || event.target.closest('#loraRows')) scheduleDraft();
});
document.addEventListener('click',event=>{
  if(['addLora','clearInitImage','matchInitSize'].includes(event.target.id)||event.target.dataset.role==='remove') scheduleDraft();
});
// Source image reads finish asynchronously; save after the preview is updated.
const originalRenderSourcePreview=renderSourcePreview;
renderSourcePreview=function(){originalRenderSourcePreview();scheduleDraft();};
window.addEventListener('pagehide',()=>{
  if(!restoringHistory && draftRevision!==savedRevision && qs('prompt').value.trim()) navigator.sendBeacon('/api/history/draft',JSON.stringify(historyPayload()));
});
// Reload restores this tab's draft; a different machine starts independently until History is used.
refreshLoras().then(async()=>{
  try{await restoreHistory('draft:'+promptSession);}
  catch(e){if(!e.message.includes('not found')) qs('msg').textContent='Draft could not be restored: '+e.message;}
});
