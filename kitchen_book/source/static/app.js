'use strict';
const $=id=>document.getElementById(id);
const {Timer,GestureGate,timeText,normalizeRecipe}=KitchenCore;
const deviceOwner = crypto.randomUUID();
const OWNER_KEY='kitchen-active-display';
const STORE='handsfree-kitchen-v1';
let token='',demo=false,busy=false,stream=null,gestureOn=false,gesturePending=false;
let recipe=null,page=0,menus=[],timerMode=false,incrementIndex=2,timerSource='직접 설정';
let timerPageKey='',reviewed=false,stage=1,bookPart=0,bookParts=[],evidencePart=0,evidenceParts=[],evidenceTexts=[];
let gestureSession=0, cameraEpoch=0, captureTarget=null, piConfigured=false;
let lastDeviceState='', lastSyncTime=0, sendingState=false, deviceReady=false;
function rebuildTargets(){
 const select=$('target');
 select.replaceChildren(new Option('누락 재료 추가','add'));
 const items=$('ingredients').value.split(/[,，\n]/).map(x=>x.trim()).filter(Boolean);
 items.forEach((name,i)=>select.add(new Option(name+' 교체',String(i))));
}
function setTarget(value){
 captureTarget=value;
 $('targetHint').hidden=value===null;
 $('targetHint').textContent=value===null?'':value.name?value.name+' 교체 · 해당 재료 하나만 보여 주세요.':'재료 추가 · 재료 하나만 보여 주세요.';
}
async function piStream(epoch){
 const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
 async function frame(){
   const res=await fetch('/api/device/frame',{cache:'no-store',signal:AbortSignal.timeout(6000)});
   if(!res.ok)throw Error('Pi 카메라에 연결할 수 없습니다.');
   const bmp=await createImageBitmap(await res.blob());
   try{
     if(epoch!==cameraEpoch)return;
     if(canvas.width!==bmp.width||canvas.height!==bmp.height){canvas.width=bmp.width;canvas.height=bmp.height;}
     ctx.drawImage(bmp,0,0);
   }finally{bmp.close();}
 }
 await frame();
 if(epoch!==cameraEpoch)return null;
 const media=canvas.captureStream(12);
 async function poll(){
   if(epoch!==cameraEpoch)return;
   try{await frame();if(epoch===cameraEpoch)setTimeout(poll,80);}
   catch(e){if(epoch===cameraEpoch){stopCamera();notice('Pi 영상이 끊겼습니다. 카메라를 다시 켜 주세요.',true);}}
 }
 setTimeout(poll,80);
 return media;
}
// Rasterize on Windows so the Pi can display Korean without installing a font.
function oledBitmap(stage, title, page, total, mode, seconds){
 const canvas=document.createElement('canvas');canvas.width=128;canvas.height=64;
 const ctx=canvas.getContext('2d');
 ctx.fillStyle='white';ctx.textBaseline='top';
 const labels=['재료 촬영','재료 확인','메뉴 추천','요리 시작'];
 ctx.font='bold 13px "Malgun Gothic", sans-serif';
 ctx.fillText('0'+stage+' '+labels[stage-1],2,1);
 if(stage===4){
   ctx.font='12px "Malgun Gothic", sans-serif';
   ctx.fillText(page?page+'/'+total:'준비 · '+total+'단계',2,18);
   ctx.fillText(title,2,33,124);
   if(mode==='running'||mode==='paused')ctx.fillText((mode==='running'?'타이머 ':'일시정지 ')+timeText(seconds),2,49);
   if(mode==='finished')ctx.fillText('타이머 완료',2,49);
 }
 const pixels=ctx.getImageData(0,0,128,64).data, bytes=new Uint8Array(1024);
 for(let i=0;i<8192;i++)if(pixels[i*4+3]>=90)bytes[i>>3]|=128>>(i%8);
 return btoa(String.fromCharCode(...bytes));
}
async function syncDevice(){
 if(!piConfigured||!token||sendingState)return;
 try{const owner=localStorage.getItem(OWNER_KEY);if(owner&&owner!==deviceOwner)return;}catch{}
 const cooking=stage===4&&!!recipe;
 const mode=!cooking?'idle':timer.running?'running':timer.finished?'finished':timerMode&&timer.left()>0?'paused':stage===4?'step':'idle';
 const state={stage,mode,page:cooking?page:0,total:cooking?recipe.steps.length:0,seconds:cooking?Math.ceil(timer.left()):0};
 const title=cooking?(page?recipe.steps[page-1].title:recipe.title):'';
 const key=JSON.stringify([stage,title,state]);
 if(key===lastDeviceState&&deviceReady&&Date.now()-lastSyncTime<10000)return;
 sendingState=true;
 try{if(cooking)state.bitmap=oledBitmap(stage,title,state.page,state.total,mode,state.seconds);const ack=await request('/api/device/state',state);if(ack.stage!==state.stage||ack.page!==state.page)throw Error('PC·Pi 서버를 업데이트하고 재시작하세요.');lastDeviceState=key;lastSyncTime=Date.now();deviceReady=true;$('piStatus').textContent='Pi 출력 연결됨';}
 catch(e){deviceReady=false;$('piStatus').textContent='OLED 출력 실패 · '+e.message;}
 finally{sendingState=false;}
}

let timer=new Timer(),gate=new GestureGate(),audio=null,recognition=null;
const increments=[1,10,60,300];
const names={Thumb_Up:'👍 엄지 위',Thumb_Down:'👎 엄지 아래',Pointing_Up:'☝️ 검지',Open_Palm:'🖐 손바닥',None:'손을 보여 주세요'};
function notice(text,error=false){$('notice').textContent=text;$('notice').className=error?'error':'';if($('bookFeedback')){$('bookFeedback').textContent=text;$('bookFeedback').classList.toggle('error',!!error);}}
function element(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function save(){try{localStorage.setItem(STORE,JSON.stringify({recipe,page,timer:timer.snapshot(),timerSource,timerPageKey,ingredients:$('ingredients').value,request:$('request').value}));}catch(e){notice('브라우저 저장 공간을 사용할 수 없습니다. 레시피 저장 버튼으로 내보내세요.',true);}}
function validRecipe(x){
 if(!x || typeof x.title!=='string' || x.title.length>80 || !x.title.trim() || !Array.isArray(x.ingredients) || !x.ingredients.length || x.ingredients.length>30 || !Array.isArray(x.steps) || !x.steps.length || x.steps.length>16 || !Array.isArray(x.notes) || x.notes.length>10)return false;
 return x.ingredients.concat(x.notes).every(s=>typeof s==='string'&&s.length<=200) && x.steps.every(s=>s && typeof s.title==='string'&&s.title.length<=80 && typeof s.instruction==='string'&&s.instruction.length<=1000 && Number.isInteger(s.timer_seconds)&&s.timer_seconds>=0&&s.timer_seconds<=86400);
}
function restore(){try{const data=JSON.parse(localStorage.getItem(STORE)||'null');if(!data)return;data.recipe=normalizeRecipe(data.recipe);if(validRecipe(data.recipe)){recipe=data.recipe;page=Math.max(0,Math.min(recipe.steps.length,Number.isInteger(data.page)?data.page:0));}timer=new Timer(data.timer||{});timerPageKey=typeof data.timerPageKey==='string'?data.timerPageKey:'';timerSource=typeof data.timerSource==='string'?data.timerSource:'복원된 타이머';$('ingredients').value=typeof data.ingredients==='string'?data.ingredients:'';$('request').value=typeof data.request==='string'?data.request:'';}catch(e){notice('저장된 상태를 복원하지 못했습니다.',true);}}
async function request(path,data){
 const options=data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Kitchen-Token':token},body:JSON.stringify(data)};
 const response=await fetch(path,options);const result=await response.json();if(!response.ok)throw Error(result.error||'서버 요청 실패');return result;
}
function setBusy(value){busy=value;$('capture').disabled=busy||!stream;$('recommend').disabled=busy||!reviewed;$('voice').disabled=busy||!recognition;document.querySelectorAll('.menu-select').forEach(b=>b.disabled=busy);$('importBook').disabled=busy;$('ingredients').disabled=busy;$('reviewIngredients').disabled=busy;$('captureArea').disabled=busy;$('closeup').disabled=busy;$('cameraSource').disabled=busy;$('target').disabled=busy;document.querySelectorAll('[data-stage],#retake,#skipCapture,#editIngredients,#backMenus').forEach(b=>b.disabled=busy||(b.dataset.stage==='3'&&!menus.length)||(b.dataset.stage==='4'&&!recipe));}
async function aiJob(kind,payload){
 if(busy)throw Error('AI 작업이 진행 중입니다.');setBusy(true);
 try{
   const {job_id}=await request('/api/'+kind,payload);
   // Inference may take minutes on CPU. Keep polling; do not silently submit duplicates.
   const started=Date.now();
   while(true){
     await new Promise(resolve=>setTimeout(resolve,600));
     const job=await request('/api/jobs/'+job_id);
     if(job.status==='done')return job.result;
     if(job.status==='error')throw Error(job.error);
     notice(`로컬 AI가 ${kind==='ingredients'?'재료를 확인':kind==='menus'?'메뉴를 추천':'레시피북을 작성'}하고 있습니다. ${Math.floor((Date.now()-started)/1000)}초 경과 · CPU에서는 수 분 걸릴 수 있습니다.`);
   }
 }finally{setBusy(false);}
}
function getIngredients(){const items=$('ingredients').value.split(/[,，\n]/).map(x=>x.trim()).filter(Boolean);if(!items.length)throw Error('촬영한 재료를 확인하거나 재료 이름을 직접 입력하세요.');if(items.length>30)throw Error('재료는 30개까지 입력할 수 있습니다.');return items;}
function cameraFrame(maxSide=896,crop=false){
 if(!stream || !$('video').videoWidth)throw Error('웹캠을 먼저 켜고 화면이 보일 때까지 기다려 주세요.');
 const video=$('video'),canvas=document.createElement('canvas');
 const side=Math.min(video.videoWidth,video.videoHeight)*.75,sw=crop?side:video.videoWidth,sh=crop?side:video.videoHeight;
 const sx=(video.videoWidth-sw)/2,sy=(video.videoHeight-sh)/2,scale=Math.min(1,maxSide/Math.max(sw,sh));
 canvas.width=Math.round(sw*scale);canvas.height=Math.round(sh*scale);canvas.getContext('2d').drawImage(video,sx,sy,sw,sh,0,0,canvas.width,canvas.height);return canvas.toDataURL('image/jpeg',.93);
}
async function startCamera(){try{
 if(stream)return;
 const epoch=++cameraEpoch;
 $('cameraStart').disabled=true;
 if($('cameraSource').value!=='pi'&&!navigator.mediaDevices?.getUserMedia)throw Error('localhost의 Chrome/Edge에서 실행하세요.');
 const media=$('cameraSource').value==='pi'?await piStream(epoch):await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}},audio:false});
 if(epoch!==cameraEpoch){media?.getTracks().forEach(t=>t.stop());return;}stream=media;
 $('video').srcObject=stream;$('gestureVideo').srcObject=stream;await Promise.all([$('video').play(),$('gestureVideo').play()]);$('gestureCameraHint').hidden=true;$('cameraHint').hidden=true;$('cameraStart').disabled=true;$('cameraStop').disabled=false;setBusy(busy);notice('재료를 카메라에 보여 주고 촬영하세요.');
 stream.getVideoTracks()[0].addEventListener('ended',stopCamera);
}catch(e){stopCamera();notice('웹캠 연결 실패: '+e.message,true);}}
function stopCamera(){cameraEpoch++;gestureSession++;gestureOn=false;gesturePending=false;gate.reset();if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}$('video').srcObject=null;$('gestureVideo').srcObject=null;$('gestureCameraHint').hidden=false;$('cameraHint').hidden=false;$('cameraStart').disabled=false;$('cameraStop').disabled=true;$('gestureToggle').textContent='제스처 켜기';$('gestureName').textContent='대기 중';$('holdProgress').value=0;setBusy(busy);}
function resetReview(){reviewed=false;$('reviewIngredients').checked=false;menus=[];renderMenus();setBusy(busy);}
async function capture(){try{
 if(busy)return;
 const target=captureTarget;
 const scan=target?'single':$('scanMode').value;
 const image=cameraFrame(1600,$('captureArea').value==='center');
 showStage(2);resetReview();
 {
   $('photo').src=image;$('photo').hidden=false;$('photoPlaceholder').hidden=true;
 }
 $('photoInfo').textContent=target?'근접 사진 분석 중…':scan==='quick'?'전체 사진에서 재료를 찾고 있습니다…':'전체 사진과 확대 영역을 대조하고 있습니다…';
 const result=await aiJob('ingredients',{image,scan});
 let items=$('ingredients').value.split(/[,，\n]/).map(x=>x.trim()).filter(Boolean);
 if(!target)items=result.ingredients;
 else if(result.ingredients.length===1){
   if(target.index===null)items.push(result.ingredients[0]);
   else items[target.index]=result.ingredients[0];
 }
 $('ingredients').value=[...new Set(items)].join(', ');
 rebuildTargets();setTarget(null);
 evidenceTexts=(result.evidence||[]).map(item=>item.name+' · '+item.evidence);
 evidenceTexts.push(...result.uncertain.map(x=>'확인 필요 · '+x));
 if(target&&result.ingredients.length!==1)evidenceTexts.unshift('한 가지로 식별하지 못해 기존 목록을 유지했습니다. 한 재료만 가까이 찍거나 이름을 입력하세요.');
 $('uncertain').textContent='';renderEvidence();
 $('photoInfo').textContent=demo?'DEMO · 고정 예시':target?result.ingredients.length===1?'근접 촬영 · 재료 목록을 갱신했습니다.':'근접 촬영 · 식별이 어려워 목록을 유지했습니다.':(scan==='quick'?'빠른 확인 · 재료 후보 ':'정밀 확인 · 재료 후보 ')+items.length+'개';
 save();notice(demo?'DEMO: 고정 예시입니다. 실제 사진 인식은 일반 모드에서 실행하세요.':result.verification_status==='unverified'?'재확인을 완료하지 못했습니다. 표시된 재료는 미검증 후보입니다. 사진과 직접 비교하여 수정한 뒤 확인란을 체크하세요.':'인식은 확정 결과가 아닙니다. 사진과 비교하여 재료를 수정하고 확인란을 체크하세요.');
}catch(e){$('photoInfo').textContent='사진은 촬영됐지만 분석을 완료하지 못했습니다. 위 오류 내용을 확인하세요.';notice(e.message,true);}}
async function recommend(){try{
 if(!reviewed)throw Error('재료 목록을 확인하고 확인란을 체크해 주세요.');const items=getIngredients();notice('메뉴 추천을 시작합니다.');const result=await aiJob('menus',{ingredients:items,request:$('request').value});menus=result.menus;renderMenus();showStage(3);save();notice('메뉴를 선택하면 LLM이 해당 메뉴의 레시피북을 만듭니다.');
}catch(e){notice(e.message,true);}}
function renderMenus(){
 const container=$('menus');container.replaceChildren();menus.forEach(menu=>{
  const card=element('article',undefined,'menu-card');
  const button=element('button',undefined,'menu-select');button.append(element('strong',menu.id+'. '+menu.name));button.onclick=()=>selectMenu(menu);button.disabled=busy;
  if(menu.name.length>25)button.classList.add('long-name');
  const details=element('div',undefined,'menu-description'),nav=element('div',undefined,'mini-pages');
  const previous=element('button','←'),label=element('span'),next=element('button','→');
  previous.setAttribute('aria-label',menu.name+' 이전 설명');next.setAttribute('aria-label',menu.name+' 다음 설명');nav.append(previous,label,next);
  card.append(button,details,nav);container.append(card);
  let parts=[],part=0;
  const paint=()=>{details.replaceChildren(...parts[part]);label.textContent=`추천 설명 ${part+1}/${parts.length}`;previous.disabled=part===0;next.disabled=part===parts.length-1;};
  card.refit=()=>{parts=paginate(details,[element('p',menu.reason),element('p','추가 준비: '+(menu.missing.join(', ')||'없음'),'menu-missing')]);part=Math.min(part,parts.length-1);paint();};
  previous.onclick=()=>{if(part>0){part--;paint();}};next.onclick=()=>{if(part<parts.length-1){part++;paint();}};
  if(stage===3)card.refit();
 });
}
async function selectMenu(menu){try{
 const items=getIngredients();notice(menu.name+' 레시피북 생성 중');const rawResult=await aiJob('recipe',{ingredients:items,request:$('request').value,menu});
 const result=normalizeRecipe(rawResult);if(!validRecipe(result))throw Error('레시피 출력 형식이 올바르지 않습니다. 다시 생성하세요.');
 recipe=result;page=1;bookPart=0;timerMode=false;if(!timer.running){timer.set(0);timerPageKey='';timerSource='설정 대기';}prepareStepTimer();showStage(4);renderBook();renderMode();save();notice('레시피북이 준비되었습니다. 요리 중 제스처를 켜서 페이지와 타이머를 조작하세요.');
}catch(e){notice(e.message,true);}}
// Paginate actual rendered text at the current viewport size; never hide recipe text.
function paginate(container,nodes){
 if(container.clientHeight<=0)return [nodes];
 const pages=[];let current=[];container.replaceChildren();
 const fits=()=>container.scrollHeight<=container.clientHeight+1;
 const flush=()=>{if(current.length)pages.push(current);current=[];container.replaceChildren();};
 for(const source of nodes){
  let node=source.cloneNode(true);container.append(node);
  if(fits()){current.push(node);continue;}
  node.remove();if(current.length)flush();container.append(node);
  if(fits()){current.push(node);continue;}
  // A single long paragraph/list item can span several pages. Unicode characters
  // are kept intact and the complete original text is retained across fragments.
  let chars=Array.from(source.textContent);node.remove();
  while(chars.length){
   node=source.cloneNode(false);container.append(node);let low=1,high=chars.length,best=1;
   while(low<=high){const mid=Math.floor((low+high)/2);node.textContent=chars.slice(0,mid).join('');if(fits()){best=mid;low=mid+1;}else high=mid-1;}
   node.textContent=chars.splice(0,best).join('');current.push(node);
   if(chars.length)flush();
  }
 }
 flush();return pages.length?pages:[[]];
}
function renderBook(){
 $('exportBook').disabled=!recipe;if(!recipe)return;
 if(stage!==4)return;
 const blocks=[];
 if(page===0){
  blocks.push(element('p','RECIPE / 준비하기','eyebrow'),element('h2',recipe.title,'recipe-title'),element('p','재료와 분량을 확인한 후 다음 페이지로 넘겨 주세요.','small'));
  recipe.ingredients.forEach(item=>blocks.push(element('p','• '+item,'recipe-item')));
  recipe.notes.forEach(note=>blocks.push(element('p',note,'recipe-note')));
 }else{
  const step=recipe.steps[page-1];
  blocks.push(element('p',recipe.title,'eyebrow'),element('p',String(page).padStart(2,'0'),'step-number'),element('h2',step.title,'recipe-title'),element('p',step.instruction,'instruction'));
  blocks.push(element('p',step.timer_seconds?'이 단계 시간 '+timeText(step.timer_seconds):'지정된 시간이 없습니다. 필요하면 타이머를 직접 설정하세요.','step-timer'));
 }
 bookParts=paginate($('bookContent'),blocks);bookPart=Math.max(0,Math.min(bookPart,bookParts.length-1));paintBook();
}
function paintBook(){
 $('bookContent').replaceChildren(...bookParts[bookPart]);
 $('previous').disabled=page===0&&bookPart===0;
 $('next').disabled=page===recipe.steps.length&&bookPart===bookParts.length-1;
 $('pageLabel').textContent=`${page===0?'준비':page+'단계'} / ${recipe.steps.length}단계`+(bookParts.length>1?` · ${bookPart+1}/${bookParts.length}쪽`:'');
}
function movePage(delta){
 if(!recipe)return;
 if(bookPart+delta>=0&&bookPart+delta<bookParts.length){bookPart+=delta;paintBook();return;}
 const next=Math.max(0,Math.min(recipe.steps.length,page+delta));
 if(next===page){notice(delta>0?'마지막 페이지입니다.':'첫 페이지입니다.');return;}
 page=next;void syncDevice();bookPart=delta<0?Number.MAX_SAFE_INTEGER:0;prepareStepTimer();renderBook();renderTimer();save();
}
function renderEvidence(){
 if(stage!==2)return;
 const nodes=(evidenceTexts.length?evidenceTexts:['사진을 확인하고 재료를 직접 수정해 주세요.']).map(t=>element('p',t));
 evidenceParts=paginate($('evidence'),nodes);evidencePart=Math.max(0,Math.min(evidencePart,evidenceParts.length-1));paintEvidence();
}
function paintEvidence(){
 $('evidence').replaceChildren(...evidenceParts[evidencePart]);
 $('evidencePage').textContent=`인식 설명 ${evidencePart+1}/${evidenceParts.length}`;
 $('evidencePrev').disabled=evidencePart===0;$('evidenceNext').disabled=evidencePart===evidenceParts.length-1;
}
function showStage(next){
 if(busy)return;
 if(next===3&&!menus.length)return;if(next===4&&!recipe)return;
 try{localStorage.setItem(OWNER_KEY,deviceOwner);}catch{}
 if(next===2){setTarget(null);rebuildTargets();}
 stage=next;gestureSession++;gate.reset();$('holdProgress').value=0;
 if(next!==4){gestureOn=false;$('gestureToggle').textContent='제스처 켜기';$('gestureName').textContent='대기 중';}
 document.querySelectorAll('.stage').forEach(el=>el.hidden=el.id!=='stage'+stage);
 document.querySelectorAll('[data-stage]').forEach(el=>{if(Number(el.dataset.stage)===stage)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current');});
 setBusy(busy);if(stage===3)document.querySelectorAll('.menu-card').forEach(c=>c.refit());if(stage===4){renderBook();renderTimer();}if(stage===2)renderEvidence();void syncDevice();
}
function stepKey(){return recipe&&page>0?recipe.title+'|'+page+'|'+recipe.steps[page-1].instruction:'';}
function prepareStepTimer(){
 const key=stepKey();if(timer.running||key===timerPageKey)return;
 timerPageKey=key;
 const step=recipe&&page>0?recipe.steps[page-1]:null;
 timer.set(step?step.timer_seconds:0);timerSource=step?step.title:'설정 대기';syncInputs();
}
function loadStepTimer(){
 if(!recipe||page===0){notice('조리 단계 페이지에서 시간을 설정하세요.');return false;}
 if(timer.running){notice('기존 타이머가 실행 중입니다. 👎로 일시정지한 뒤 현재 단계 시간을 설정하세요.',true);return false;}
 const step=recipe.steps[page-1];timerPageKey=stepKey();
 timer.set(step.timer_seconds);timerSource=step.title;syncInputs();save();renderTimer();
 notice(step.timer_seconds?'단계 시간 '+timeText(step.timer_seconds)+' 설정 완료. 👍로 시작하세요.':'이 단계에는 명시된 시간이 없습니다. ☝️로 시간을 더한 뒤 👍로 시작하세요.');
 return true; // A no-time step must still allow hands-free timer setup mode.
}
function enterTimer(){
 gestureSession++;
 timerMode=!timerMode;
 if(timerMode){prepareStepTimer();syncInputs();renderTimer();save();}
 renderMode();notice(timerMode?'타이머 모드: 👍 시작 · 👎 일시정지 · ☝️ 시간 추가 · 🖐 책 모드':'책 모드: 👍 다음 · 👎 이전 · ☝️ 단계 시간 설정 · 🖐 타이머 모드');
}
function renderMode(){
 $('gestureMode').textContent=timerMode?'타이머 모드':'책 모드';$('timerMode').textContent=timerMode?'책 모드로':'타이머 모드';$('timerPanel').classList.toggle('active',timerMode);
 $('gestureGuide').textContent='손바닥이 카메라를 향하게 약 0.9초 유지하세요. 반복하려면 손을 잠시 내리세요.';
 $('increment').textContent='추가 단위: '+({1:'1초',10:'10초',60:'1분',300:'5분'}[increments[incrementIndex]]);
 const items=timerMode?[['👍','시작 / 재개'],['👎','일시정지'],['☝️','시간 추가'],['🖐','책 모드']]:[['👍','다음 페이지'],['👎','이전 페이지'],['☝️','단계 시간 설정'],['🖐','타이머 모드']];
 $('gestureCards').replaceChildren();for(const [icon,label] of items){const card=element('div',undefined,'gesture-card');const copy=element('div',undefined,'gesture-copy');copy.append(element('span',{'👍':'엄지 위','👎':'엄지 아래','☝️':'검지만 펴기','🖐':'손바닥 펴기'}[icon],'pose-name'),element('strong',label));card.append(element('span',icon,'hand-icon'),copy);$('gestureCards').append(card);}
}
function syncInputs(){const left=Math.ceil(timer.left());$('minutes').value=Math.floor(left/60);$('seconds').value=left%60;}
function renderTimer(){
 $('clock').textContent=timeText(timer.left());$('clock').classList.toggle('done',timer.finished);$('clock').classList.toggle('long-clock',timer.left()>=3600);$('timerState').textContent=timer.finished?'시간이 되었습니다!':timer.running?'조리 중 · 타이머 작동 중':timer.remaining>0?'설정됨 / 일시정지':'설정 대기';$('timerSource').textContent='현재 타이머: '+timerSource;
 const step=recipe&&page>0?recipe.steps[page-1]:null;
 $('currentStepTime').textContent=step?(step.timer_seconds?'현재 단계 시간: '+timeText(step.timer_seconds):'현재 단계: 지정 시간 없음'):'조리 단계에서 시간이 자동 준비됩니다.';
 $('loadCurrentTimer').disabled=!step||timer.running;
 $('timerRunningHint').textContent=timer.running&&timerPageKey!==stepKey()?'다른 단계로 이동해도 실행 중인 타이머는 유지됩니다. 현재 단계 시간을 쓰려면 먼저 일시정지하세요.':'';
}
function unlockAudio(){try{audio=audio||new (window.AudioContext||window.webkitAudioContext)();if(audio.state==='suspended')audio.resume();}catch(e){/* Visual alert still works. */}}
function alarm(){
 if(!audio||audio.state!=='running')return;
 for(let i=0;i<4;i++){const osc=audio.createOscillator(),gain=audio.createGain();osc.frequency.value=740;gain.gain.value=.14;osc.connect(gain);gain.connect(audio.destination);osc.start(audio.currentTime+i*.45);osc.stop(audio.currentTime+i*.45+.22);}
}
function timerAction(action,amount){
 if(action==='start'){unlockAudio();if(timer.left()<=0)prepareStepTimer();if(timer.left()<=0)return notice('먼저 타이머 시간을 설정하세요.',true);timer.start();}
 if(action==='pause')timer.pause();
 if(action==='reset')timer.reset();
 if(action==='adjust'){timer.adjust(amount);timerSource='손동작 / 직접 조절';timerPageKey=stepKey();}
 syncInputs();save();renderTimer();
}
function dispatchGesture(name){
 if(stage!==4)return;
 if(name==='Open_Palm'){enterTimer();return;}
 if(!timerMode){if(name==='Thumb_Up')movePage(1);if(name==='Thumb_Down')movePage(-1);if(name==='Pointing_Up'&&loadStepTimer()){timerMode=true;renderMode();}return;}
 if(name==='Thumb_Up')timerAction('start');
 if(name==='Thumb_Down')timerAction('pause');
 if(name==='Pointing_Up')timerAction('adjust',increments[incrementIndex]);
}
async function gestureLoop(){
 if(stage!==4||!gestureOn||!stream||gesturePending)return;
 const session=gestureSession;
 gesturePending=true;
 try{
   const result=await request('/api/gesture',{image:cameraFrame(640)});
   if(!gestureOn||stage!==4||session!==gestureSession)return;
   const name=Object.hasOwn(names,result.gesture)?result.gesture:'None';const gated=gate.feed(name,result.score,performance.now());
   $('gestureName').textContent=(names[name]||name)+(gated.progress===1?' · 손을 내려 주세요':'');$('holdProgress').value=gated.progress;
   if(gated.event)dispatchGesture(gated.event);
 }catch(e){if(session!==gestureSession)return;gestureOn=false;gate.reset();$('gestureToggle').textContent='제스처 켜기';notice('제스처 인식 실패: '+e.message,true);}
 finally{gesturePending=false;}
}
async function toggleGestures(){
 if(!stream)await startCamera();if(!stream||stage!==4)return;
 gestureSession++;
 unlockAudio();gestureOn=!gestureOn;gate.reset();$('gestureToggle').textContent=gestureOn?'제스처 끄기':'제스처 켜기';$('holdProgress').value=0;
 if(gestureOn)notice('제스처 인식 시작. 동작을 약 0.9초 유지하세요. 다른 동작도 유지하면 실행됩니다. 같은 동작을 반복하려면 손을 잠시 내려 주세요.');else $('gestureName').textContent='대기 중';
}
function configureVoice(){
 const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!Speech){$('voice').disabled=true;$('voice').title='이 브라우저는 음성 인식을 지원하지 않습니다.';return;}
 recognition=new Speech();recognition.lang='ko-KR';recognition.interimResults=false;
 recognition.onresult=event=>{const text=event.results[0][0].transcript;notice('음성 입력: '+text);if(/추천/.test(text)){const extra=text.replace(/메뉴|추천|해줘|해주세요|해 줘/g,'').trim();if(extra)$('request').value=extra;recommend();}else{$('request').value=text;save();notice('요청 사항에 반영했습니다. “메뉴 추천해줘”라고 말하거나 추천 버튼을 누르세요.');}};
 recognition.onerror=event=>notice('음성 인식 실패: '+event.error+' · 입력창과 추천 버튼을 사용할 수 있습니다.',true);
 recognition.onend=()=>{$('voice').textContent='음성 요청';};
 $('voice').onclick=()=>{try{recognition.start();$('voice').textContent='듣는 중…';notice('“메뉴 추천해줘”라고 말해 주세요. 브라우저 음성 서비스가 사용됩니다.');}catch(e){notice(e.message,true);}};
}
function exportBook(){if(!recipe)return;const blob=new Blob([JSON.stringify(recipe,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='recipe-book.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function importBook(event){try{const file=event.target.files[0];if(!file)return;if(file.size>100000)throw Error('레시피 파일은 100KB 이하여야 합니다.');const data=normalizeRecipe(JSON.parse(await file.text()));if(!validRecipe(data))throw Error('올바른 레시피 JSON 파일이 아닙니다.');recipe=normalizeRecipe(data);page=1;bookPart=0;timerMode=false;if(!timer.running){timer.set(0);timerPageKey='';timerSource='설정 대기';}prepareStepTimer();showStage(4);renderBook();renderMode();save();notice('저장한 레시피북을 불러왔습니다.');}catch(e){notice(e.message,true);}finally{event.target.value='';}}
document.querySelectorAll('[data-stage]').forEach(b=>b.onclick=()=>showStage(Number(b.dataset.stage)));
$('cameraSource').onchange=()=>stopCamera();
$('closeup').onclick=()=>{
 const key=$('target').value;
 const index=key==='add'?null:Number(key);
 const items=$('ingredients').value.split(/[,，\n]/).map(x=>x.trim()).filter(Boolean);
 setTarget({index,name:index===null?'':items[index]});showStage(1);
};
$('skipCapture').onclick=()=>{setTarget(null);showStage(2);};$('retake').onclick=()=>{setTarget(null);showStage(1);};
$('editIngredients').onclick=()=>showStage(2);$('backMenus').onclick=()=>showStage(menus.length?3:2);
$('evidencePrev').onclick=()=>{if(evidencePart>0){evidencePart--;paintEvidence();}};
$('evidenceNext').onclick=()=>{if(evidencePart<evidenceParts.length-1){evidencePart++;paintEvidence();}};
$('changeIncrement').onclick=()=>{incrementIndex=(incrementIndex+1)%increments.length;renderMode();};
$('manualTimer').onclick=()=>{syncInputs();$('timerDialog').showModal();};
$('cameraStart').onclick=startCamera;$('cameraStop').onclick=stopCamera;$('capture').onclick=capture;$('recommend').onclick=recommend;
$('previous').onclick=()=>movePage(-1);$('next').onclick=()=>movePage(1);$('gestureToggle').onclick=toggleGestures;$('timerMode').onclick=enterTimer;
$('startTimer').onclick=()=>timerAction('start');$('pauseTimer').onclick=()=>timerAction('pause');$('resetTimer').onclick=()=>timerAction('reset');$('plusTimer').onclick=()=>timerAction('adjust',60);$('minusTimer').onclick=()=>timerAction('adjust',-60);
$('setTimer').onclick=()=>{const min=Number($('minutes').value),sec=Number($('seconds').value);if(!Number.isInteger(min)||!Number.isInteger(sec)||min<0||sec<0||sec>59||min*60+sec>86400)return notice('0~24시간 범위로 분과 초를 입력하세요.',true);timer.set(min*60+sec);timerSource='직접 설정';timerPageKey=stepKey();save();renderTimer();$('timerDialog').close();};
$('exportBook').onclick=exportBook;$('importBook').onclick=()=>$('importFile').click();$('importFile').onchange=importBook;
$('ingredients').oninput=()=>{rebuildTargets();resetReview();save();};$('request').onchange=()=>{menus=[];renderMenus();save();};
$('reviewIngredients').onchange=()=>{reviewed=$('reviewIngredients').checked;setBusy(busy);};
$('loadCurrentTimer').onclick=()=>{if(loadStepTimer()){timerMode=true;renderMode();}};
let layoutFrame=0;
function refit(){cancelAnimationFrame(layoutFrame);layoutFrame=requestAnimationFrame(()=>{if(stage===4)renderBook();if(stage===2)renderEvidence();if(stage===3)document.querySelectorAll('.menu-card').forEach(c=>c.refit());});}
if(typeof ResizeObserver!=='undefined'){const observer=new ResizeObserver(refit);observer.observe($('bookContent'));observer.observe($('evidence'));observer.observe($('menus'));}
window.addEventListener('resize',refit);if(document.fonts)document.fonts.ready.then(refit);
document.addEventListener('visibilitychange',()=>{gate.reset();if(document.hidden){$('holdProgress').value=0;}else renderTimer();});
setInterval(()=>{if(!document.hidden)gestureLoop();},150);
setInterval(()=>{if(timer.tick()){alarm();notice('⏰ 타이머 완료: '+timerSource);save();}renderTimer();},200);
async function initialize(){
 try{localStorage.setItem(OWNER_KEY,deviceOwner);$('resumeBook').hidden=!localStorage.getItem(STORE);}catch{}
 showStage(1);configureVoice();prepareStepTimer();renderBook();renderMode();syncInputs();renderTimer();setBusy(false);
 try{const health=await request('/api/health');token=health.csrf;demo=health.demo;piConfigured=!!health.device;$('cameraSource').options[1].disabled=!piConfigured;$('modeBadge').textContent=demo?'DEMO · 고정 예시':'LOCAL AI · 내 PC';
 await syncDevice();
 const missing=Object.entries(health.models).filter(([,value])=>!value.exists).map(([key])=>key);
 notice(demo?'DEMO 모드입니다. 촬영·추천·생성 결과는 고정 예시이며 실제 모델 추론이 아닙니다. 제스처에는 실제 모델이 필요합니다.':missing.length?'모델 파일 확인 필요: '+missing.join(', ')+' · source/README.md를 확인하세요.':'준비되었습니다. 재료를 촬영하거나 직접 입력하세요.',!demo&&missing.length>0);
 }catch(e){notice('서버 연결 실패: '+e.message,true);}
}
$('resumeBook').onclick=()=>{restore();if(recipe){showStage(4);renderMode();syncInputs();}else notice('이어볼 레시피가 없습니다.');};
setInterval(syncDevice,500);
initialize();
