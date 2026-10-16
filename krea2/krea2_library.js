const libraryPanel=document.createElement('dialog');
libraryPanel.id='loraLibrary';
libraryPanel.setAttribute('aria-label','LoRA Library');
libraryPanel.style.cssText='position:fixed;margin:0 0 0 auto;inset:0 0 0 auto;width:min(690px,95vw);height:100vh;max-height:100vh;background:var(--panel);color:var(--text);border:1px solid var(--line);padding:22px';
libraryPanel.innerHTML=`<div class="actions" style="justify-content:space-between"><h2>LoRA Library</h2><button id="closeLibrary" class="secondary">Close</button></div>
<p>Find styles, check versions, and update weights without changing your saved LoRA selections.</p>
<div class="actions" style="flex-wrap:wrap"><button id="checkLoraUpdates" class="secondary">Check updates</button><button id="updateAllLoras">Update all</button><button id="openLoraFolder" class="secondary">Open folder</button><a id="finderLoraFolder" class="link-button secondary" href="smb://192.168.7.226/edq/krea2/loras">Open in Finder</a><a class="link-button secondary" href="/loras/" target="_blank" rel="noopener">Browse files</a></div>
<p class="mini">Updates keep your current filenames. Use Restore previous if you prefer an older version. Files needing a manual choice stay unchanged.</p>
<p id="libraryProgress" class="msg" role="status"></p>
<label for="librarySearch">Find a LoRA</label><input id="librarySearch" type="search" placeholder="Name, filename or trigger…">
<div id="libraryRows"></div>
<details><summary>Service details</summary><div class="status" id="status"></div><div class="mini" id="loraStatus"></div><button id="refreshServiceDetails" class="secondary compact">Refresh details</button></details>`;
document.body.append(libraryPanel);
let libraryTimer;
function renderLibrary(){
 const needle=qs('librarySearch').value.toLowerCase();
 const list=loraCatalog.filter(item=>[item.name,item.filename,item.trigger].join(' ').toLowerCase().includes(needle));
 qs('libraryRows').replaceChildren();
 list.forEach(item=>{
  const row=document.createElement('section');row.style.cssText='padding:14px 0;border-bottom:1px solid var(--line)';
  const title=document.createElement('b');title.textContent=item.name;
  const detail=document.createElement('div');detail.className='mini';
  detail.textContent=item.filename+' · '+item.size;
  const version=document.createElement('p');version.className='mini';
  version.textContent=(item.installed_version?'Installed: '+item.installed_version+' · ':'')+
    (item.latest_version?'Latest: '+item.latest_version+' · ':'')+(item.update_status||'Not checked');
  const trigger=document.createElement('p');trigger.className='mini';trigger.textContent=item.trigger?'Trigger: '+item.trigger:'Trigger not identified yet.';
  const actions=document.createElement('div');actions.className='actions';actions.style.flexWrap='wrap';
  const use=document.createElement('button');use.className='secondary small';use.textContent='Add LoRA';
  use.onclick=()=>{
    if(!selectedLoras.some(l=>l.tag===item.tag)) selectedLoras.push({tag:item.tag,weight:1});
    renderLoraRows();scheduleDraft();qs('libraryProgress').textContent='Added '+item.name+' to this session.';
  };
  actions.append(use);
  if(item.can_restore){
    const restore=document.createElement('button');restore.className='secondary small';restore.textContent='Restore previous';
    restore.onclick=async()=>{
      try{await json('/api/library/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:item.filename})});await refreshLibrary();}
      catch(error){showLibraryError(error);}
    };actions.append(restore);
  }
  if(item.trigger){
    const addTrigger=document.createElement('button');addTrigger.className='secondary small';addTrigger.textContent='Add trigger to prompt';
    addTrigger.onclick=()=>{if(!qs('prompt').value.includes(item.trigger)) qs('prompt').value+=', '+item.trigger;scheduleDraft();qs('libraryProgress').textContent='Trigger added to prompt.';};actions.append(addTrigger);
  }
  if(item.source_url){
    const link=document.createElement('a');link.className='mini';link.href=item.source_url;link.target='_blank';link.rel='noopener';link.textContent='Source & versions';actions.append(link);
  }
  row.append(title,detail,version,trigger,actions);qs('libraryRows').append(row);
 });
 if(!list.length) qs('libraryRows').textContent='No matching LoRAs.';
}
async function refreshLibrary(){
 clearTimeout(libraryTimer);
 const state=await json('/api/library');
 await refreshLoras();renderLibrary();
 qs('libraryProgress').textContent=state.job.message;
 qs('checkLoraUpdates').disabled=state.job.running;qs('updateAllLoras').disabled=state.job.running;
 if(state.job.running && libraryPanel.open) libraryTimer=setTimeout(()=>refreshLibrary().catch(showLibraryError),2500);
}
function showLibraryError(error){qs('libraryProgress').textContent=error.message;}
qs('libraryButton').onclick=async()=>{libraryPanel.showModal();await refreshLibrary().catch(showLibraryError);};
qs('closeLibrary').onclick=()=>{clearTimeout(libraryTimer);libraryPanel.close();};
qs('librarySearch').oninput=renderLibrary;
qs('refreshServiceDetails').onclick=()=>refresh().catch(showLibraryError);
async function launchUpdate(mode){
 try{
  qs('checkLoraUpdates').disabled=true;qs('updateAllLoras').disabled=true;
  await json('/api/library/'+mode,{method:'POST'});await refreshLibrary();
 }catch(error){showLibraryError(error);qs('checkLoraUpdates').disabled=false;qs('updateAllLoras').disabled=false;}
}
qs('checkLoraUpdates').onclick=()=>launchUpdate('check');
qs('updateAllLoras').onclick=()=>launchUpdate('update');
qs('openLoraFolder').onclick=async()=>{
 try{const result=await json('/api/library/open-folder',{method:'POST'});qs('libraryProgress').textContent=result.message;}
 catch(error){showLibraryError(error);}
};
const isMac=/Mac|iPhone|iPad/.test(navigator.platform+' '+navigator.userAgent);
qs('finderLoraFolder').hidden=!isMac;qs('openLoraFolder').hidden=isMac;
refresh().catch(()=>{});
