import {draft,seal,openFinal,hex,from64,to64} from "./paquete.js";
const $=id=>document.getElementById(id), note=s=>$("message").textContent=s;
const clock=s=>Math.floor(s/60)+":"+String(Math.floor(s%60)).padStart(2,"0");
const config=await (await fetch("proyecto.json")).json();
const invite=new URLSearchParams(location.hash.slice(1)), slides=$("slides");
let role,stream,recorder,mode="idle",scene=-1,phrase=-1,seconds=0,raf,started=0,runId=0,lastWord="";
let activeBlob,blobURL,packageURL,packageBlob,monitor,levelTimer,wake,latest,previewSize=0,restoreId=0,validInvite=false;
const errors=e=>({NotAllowedError:"Autoriza la cámara y el micrófono en los permisos de este sitio.",NotFoundError:"No se encontraron cámara y micrófono. Puedes importar un video.",NotReadableError:"Otro programa está usando la cámara o el micrófono."}[e.name]||e.message||"No se pudo completar la operación.");
for(const r of config.roles) $("role").add(new Option(r.name,r.id));
const initial=config.roles.find(r=>r.id===invite.get("p"));
if(initial) $("role").value=initial.id;
slides.addEventListener("loadedmetadata",()=>{if(role&&mode==="idle")slides.currentTime=role.start+seconds;});
function setMode(next){
  mode=next;const busy=mode!=="idle";document.body.classList.toggle("running",busy);
  $("role").disabled=busy||validInvite;$("record").hidden=$("rehearse").hidden=busy;$("stop").hidden=!busy;
  $("enable").disabled=busy;$("file").disabled=busy;$("send").disabled=busy||!activeBlob;
  for(const b of $("scenes").children)b.disabled=busy;
}
function draw(t,force=false){
  seconds=Math.min(t,role.duration);$("time").textContent=clock(seconds);$("progress").value=seconds;
  const i=Math.max(0,role.scenes.findLastIndex?role.scenes.findLastIndex(s=>s.start<=seconds):role.scenes.reduce((a,s,j)=>s.start<=seconds?j:a,0));
  const s=role.scenes[i];
  if(i!==scene||force){
    scene=i;phrase=-1;lastWord="";$("cue").textContent="DIAPOSITIVA "+s.number+"  /  "+clock(s.start)+"–"+clock(s.start+s.duration);
    $("sceneTitle").textContent=s.title;$("pageNo").textContent=s.number+" DE 8";
    $("prompt").replaceChildren(...(s.text.match(/[^.!?]+[.!?]*\s*/g)||[s.text]).map(str=>{const el=document.createElement("span");el.textContent=str;return el;}));
    [...$("scenes").children].forEach((b,j)=>b.setAttribute("aria-current",String(j===i)));
    $("prompt").scrollTop=0;
  }
  const spans=[...$("prompt").children], total=spans.reduce((n,p)=>n+p.textContent.length,0);
  let pos=Math.min(.999,(seconds-s.start)/s.duration)*total,j=0;
  while(j<spans.length-1 && pos>=spans[j].textContent.length){pos-=spans[j].textContent.length;j++;}
  if(j!==phrase){
    spans[phrase]?.classList.remove("active");spans[j].classList.add("active");phrase=j;
  }
  if(mode==="record"||mode==="rehearse"){
    const node=spans[j].firstChild, text=node.textContent;
    let offset=Math.max(0,Math.min(text.length-1,Math.floor(pos)));
    while(offset>0 && !/\s/.test(text[offset-1])) offset--;
    const marker=i+"-"+j+"-"+offset;
    if(lastWord!==marker){lastWord=marker;const range=document.createRange();range.setStart(node,offset);range.setEnd(node,Math.min(text.length,offset+1));
      const box=$("prompt"), y=range.getBoundingClientRect().top-box.getBoundingClientRect().top;
      if(y<0||y>box.clientHeight*.65)box.scrollTop+=y-box.clientHeight*.24;}
  }
}
function seek(t){slides.currentTime=role.start+t;draw(t,true);}
function showDraft(blob){
  if(blobURL)URL.revokeObjectURL(blobURL);
  activeBlob=blob||null;blobURL=blob&&URL.createObjectURL(blob);
  const player=$("playback");player.pause();player.removeAttribute("src");player.hidden=!blob;
  $("saveRaw").hidden=!blob;$("send").disabled=!blob||mode!=="idle";
  $("draftState").textContent=blob?"Revisa la imagen y escucha el audio antes de entregar.":"Al terminar podrás revisar tu toma antes de enviarla.";
  if(blob){player.src=blobURL;$("saveRaw").href=blobURL;$("saveRaw").download=role.id+"."+(/mp4|quicktime/i.test(blob.type)?"mp4":"webm");}
}
async function changeRole(){
  const v=++restoreId;role=config.roles.find(r=>r.id===$("role").value);
  $("assignment").textContent=role.theme+" · "+clock(role.duration);$("length").textContent=clock(role.duration);$("progress").max=role.duration;
  $("scenes").replaceChildren(...role.scenes.map(s=>{const b=document.createElement("button");b.textContent="Diap. "+s.number;b.onclick=()=>seek(s.start);return b;}));
  showDraft(null);seek(0);validInvite=false;
  if(initial===role&&invite.get("k")&&invite.get("v")){
    try{validInvite=hex(await crypto.subtle.digest("SHA-256",from64(invite.get("k"))))===role.keyHash&&from64(invite.get("v")).length===32;}catch{}
  }
  if(v!==restoreId)return;setMode("idle");note(validInvite?"Tu invitación está lista para grabar y entregar.":"Puedes ensayar y grabar. Para entregar, abre tu invitación individual.");
  try{const b=await draft(role.id);if(v===restoreId)showDraft(b);}catch{}
  refresh();
}
async function saveTake(blob){
  showDraft(blob);const id=role.id;
  try{await draft(id,blob);$("draftState").textContent="Toma guardada en este dispositivo. Revisa imagen y audio antes de entregar.";}
  catch{$("draftState").textContent="Guarda una copia antes de cerrar esta pestaña. El navegador no pudo conservar el borrador.";}
}
function disableCam(){
  if(stream)stream.getTracks().forEach(track=>track.stop());stream=null;clearInterval(levelTimer);monitor?.close().catch(()=>{});monitor=null;
  $("camera").srcObject=null;$("meter").value=0;$("enable").textContent="Activar";$("camicon").hidden=false;$("deviceState").textContent="Tu cámara está apagada.";
}
async function enableCam(){
  if(stream&&stream.getTracks().every(t=>t.readyState==="live"))return;
  if(!navigator.mediaDevices?.getUserMedia)throw Error("Este navegador no ofrece captura. Abre la app en Safari, Chrome o Edge, o importa tu video.");
  const media=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user",width:{ideal:960},height:{ideal:720},frameRate:{ideal:24,max:30}},audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
  stream=media;$("camera").srcObject=media;$("camera").play().catch(()=>{});$("camicon").hidden=true;$("enable").textContent="Apagar";$("deviceState").textContent="Centrado en el cuadro · micrófono activo.";
  try{monitor=new (window.AudioContext||window.webkitAudioContext)();await monitor.resume();const a=monitor.createAnalyser();a.fftSize=256;monitor.createMediaStreamSource(media).connect(a);
    const buf=new Uint8Array(a.fftSize);levelTimer=setInterval(()=>{a.getByteTimeDomainData(buf);$("meter").value=Math.min(1,Math.sqrt(buf.reduce((n,k)=>n+((k-128)/128)**2,0)/buf.length)*4);},160);}catch{}
}
function makeRecorder(){
  if(!window.MediaRecorder)throw Error("Graba con la cámara de tu dispositivo e importa el archivo en Mi toma.");
  const types=["video/webm;codecs=vp8,opus","video/mp4;codecs=avc1.42E01E,mp4a.40.2","video/mp4","video/webm"];
  const type=types.find(t=>MediaRecorder.isTypeSupported(t));
  try{return new MediaRecorder(stream,{...(type?{mimeType:type}:{}),videoBitsPerSecond:1000000,audioBitsPerSecond:96000});}
  catch{return new MediaRecorder(stream);}
}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function start(record){
  if(mode!=="idle")return;const id=++runId;let r, data=[],complete=false;
  setMode("prepare");$("playback").pause();
  try{
    if(record){await enableCam();if(id!==runId)return;r=makeRecorder();}
    seek(0);slides.muted=true;await slides.play();slides.pause();slides.currentTime=role.start;
    if(id!==runId)return;
    for(let i=3;i>0;i--){note((record?"Grabación":"Ensayo")+" en "+i+"…");await wait(820);if(id!==runId)return;}
    if(slides.seeking)await Promise.race([new Promise(ok=>slides.addEventListener("seeked",ok,{once:true})),wait(1500)]);
    await slides.play();if(id!==runId){slides.pause();return;}
    if(r){
      recorder=r;r.ondataavailable=e=>{if(e.data.size)data.push(e.data);};
      r.onstop=async()=>{const blob=new Blob(data,{type:r.mimeType||data[0]?.type});recorder=null;
        if(complete&&blob.size){await saveTake(blob);note("Toma completa. Ya puedes revisarla.");}
        else note("Grabación interrumpida. Vuelve a empezar cuando estés listo.");setMode("idle");};
      r.onerror=()=>finish(false);
      for(const track of stream.getTracks())track.addEventListener("ended",()=>{if(recorder===r)finish(false);},{once:true});
      r.start(1000);
    }
    setMode(record?"record":"rehearse");started=performance.now();note(record?"Grabando cámara y audio…":"Ensayo en curso.");navigator.wakeLock?.request("screen").then(w=>{if(id===runId)wake=w;else w.release();}).catch(()=>{});
    function tick(){
      if(id!==runId)return;const t=(performance.now()-started)/1000;draw(t);
      if(t>=role.duration){complete=true;finish(true);return;}
      if(!slides.seeking && Math.abs(slides.currentTime-role.start-t)>.65) slides.currentTime=role.start+t;
      raf=requestAnimationFrame(tick);
    }tick();
  }catch(e){if(id===runId){finish(false);note(errors(e));}}
}
function finish(done){
  runId++;cancelAnimationFrame(raf);slides.pause();wake?.release().catch(()=>{});wake=null;
  if(recorder&&recorder.state!=="inactive"){setMode("saving");recorder.stop();return;}
  setMode("idle");note(done?"Ensayo completo. Puedes grabar cuando quieras.":"Toma detenida. Puedes volver a empezar.");
}
$("role").onchange=changeRole;$("enable").onclick=async()=>{try{if(stream)disableCam();else await enableCam();}catch(e){note(errors(e));}};
$("record").onclick=()=>start(true);$("rehearse").onclick=()=>start(false);$("stop").onclick=()=>{if(mode!=="saving")finish(false);};
document.addEventListener("visibilitychange",()=>{if(document.hidden&&["record","rehearse","prepare"].includes(mode))finish(false);});
$("fontSize").onclick=()=>{previewSize=(previewSize+1)%3;document.documentElement.style.setProperty("--read-size",["1.45rem","1.7rem","1.2rem"][previewSize]);};
$("file").onchange=async e=>{const f=e.target.files[0];e.target.value="";if(!f)return;
  if(f.size>22*1024*1024){note("El límite por toma es 22 MB. Graba desde la app o exporta el video a 720p.");return;}
  const player=document.createElement("video"),url=URL.createObjectURL(f);player.preload="metadata";player.src=url;
  try{await Promise.race([new Promise((ok,no)=>{player.onloadedmetadata=ok;player.onerror=()=>no(Error("Este navegador no pudo leer el archivo."));}),wait(8000).then(()=>{throw Error("No se pudo leer la duración del video.");})]);
    if(Number.isFinite(player.duration)&&Math.abs(player.duration-role.duration)>3)throw Error("La toma debe durar "+clock(role.duration)+" (margen de 3 s).");
    await saveTake(f);note("Video importado. Reproduce la toma antes de enviarla.");}catch(err){note(errors(err));}finally{URL.revokeObjectURL(url);}
};
$("send").onclick=async()=>{if(!validInvite){note("Abre tu enlace individual en este navegador para enviar el borrador.");return;}
  try{$("send").disabled=true;if(activeBlob.size>22*1024*1024)throw Error("La toma supera 22 MB. Importa una versión comprimida.");
    packageBlob=await seal(activeBlob,role.id,invite.get("k"));if(packageURL)URL.revokeObjectURL(packageURL);packageURL=URL.createObjectURL(packageBlob);
    $("package").href=packageURL;$("package").download="toma-"+role.id+".zip";
    const qs=new URLSearchParams({title:"Toma / "+role.id,body:"Adjunta aquí el archivo toma-"+role.id+".zip y confirma la entrega."});
    $("issue").href="https://github.com/"+config.repo+"/issues/new?"+qs;$("uploadState").textContent="";$("submission").showModal();
  }catch(e){note(errors(e));}finally{$("send").disabled=false;}
};
$("close").onclick=()=>{$("token").value="";$("submission").close();};$("submission").addEventListener("close",()=>{$("token").value="";});
$("direct").onclick=async()=>{
  const token=$("token").value.trim();if(!token)return;$("token").value="";$("direct").disabled=true;
  try{const path="https://api.github.com/repos/"+config.repo+"/contents/entradas/"+role.id+"/"+crypto.randomUUID()+".zip";
    $("uploadState").textContent="Subiendo la toma cifrada…";
    const content=to64(new Uint8Array(await packageBlob.arrayBuffer()));
    const res=await fetch(path,{method:"PUT",headers:{Authorization:"Bearer "+token,"Content-Type":"application/json","Accept":"application/vnd.github+json"},body:JSON.stringify({message:"Entrega de "+role.id,content,branch:"main"})});
    if(!res.ok)throw Error("GitHub rechazó el envío ("+res.status+"). Puedes entregar el ZIP con la opción de arriba.");$("uploadState").textContent="Toma enviada. El estado se actualizará cuando termine la validación.";}
  catch(e){$("uploadState").textContent=errors(e);}finally{$("direct").disabled=false;}
};
async function refresh(){
  try{const response=await fetch("estado.json?t="+Date.now(),{cache:"no-store"});if(!response.ok)throw Error();
    latest=await response.json();$("roster").replaceChildren(...config.roles.map(r=>{const li=document.createElement("li"),s=document.createElement("small");li.append(r.name);
      s.textContent=latest.roles[r.id]?"Recibida":"Pendiente";if(latest.roles[r.id])s.className="ready";li.append(s);return li;}));
    $("finalStatus").textContent=latest.final?"El montaje de 3:41 está listo.":latest.message||"El montaje empieza al recibir las tres tomas.";
    $("final").hidden=!(latest.final&&validInvite);}catch{$("finalStatus").textContent="No se pudo consultar el estado. Vuelve a actualizar.";}
}
$("refresh").onclick=refresh;setInterval(()=>{if(!document.hidden&&mode==="idle")refresh();},45000);
$("final").onclick=async()=>{try{$("final").disabled=true;$("finalStatus").textContent="Preparando el MP4…";
  const r=await fetch("resultado.bin?v="+encodeURIComponent(latest.final));if(!r.ok)throw Error("No se pudo descargar el montaje.");
  const blob=await openFinal(await r.arrayBuffer(),invite.get("v"));const a=$("finalLink");if(a.href.startsWith("blob:"))URL.revokeObjectURL(a.href);a.href=URL.createObjectURL(blob);a.hidden=false;a.click();$("finalStatus").textContent="MP4 listo para guardar.";
}catch(e){$("finalStatus").textContent=errors(e);}finally{$("final").disabled=false;}};
await changeRole();
