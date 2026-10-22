'use strict';
const $=id=>document.getElementById(id);
const {Timer,GestureGate,timeText,normalizeRecipe}=KitchenCore;
const STORE='handsfree-kitchen-v1';
let token='',demo=false,busy=false,stream=null,gestureOn=false,gesturePending=false;
let recipe=null,page=0,menus=[],timerMode=false,incrementIndex=2,timerSource='직접 설정';
let timerPageKey='',reviewed=false;
let timer=new Timer(),gate=new GestureGate(),audio=null,recognition=null;
let stage=1;
const increments=[1,10,60,300];
const names={Thumb_Up:'👍 엄지 위',Thumb_Down:'👎 엄지 아래',Victory:'✌️ V',Closed_Fist:'✊ 주먹',Pointing_Up:'☝️ 검지',Open_Palm:'🖐 손바닥',ILoveYou:'🤟 I Love You',None:'손을 보여 주세요'};
function notice(text,error=false){$('notice').textContent=text;$('notice').className=error?'error':'';if($('bookFeedback')){$('bookFeedback').textContent=text;$('bookFeedback').classList.toggle('error',!!error);}}
function element(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function save(){try{localStorage.setItem(STORE,JSON.stringify({recipe,page,timer:timer.snapshot(),timerSource,timerPageKey,ingredients:$('ingredients').value,request:$('request').value}));}catch(e){notice('브라우저 저장 공간을 사용할 수 없습니다. 레시피 저장 버튼으로 내보내세요.',true);}}
function validRecipe(x){
 if(!x || typeof x.title!=='string' || x.title.length>80 || !x.title.trim() || !Array.isArray(x.ingredients) || !x.ingredients.length || x.ingredients.length>30 || !Array.isArray(x.steps) || !x.steps.length || x.steps.length>16 || !Array.isArray(x.notes) || x.notes.length>10)return false;
 return x.ingredients.concat(x.notes).every(s=>typeof s==='string'&&s.length<=200) && x.steps.every(s=>s && typeof s.title==='string'&&s.title.length<=80 && typeof s.instruction==='string'&&s.instruction.length<=1000 && Number.isInteger(s.timer_seconds)&&s.timer_seconds>=0&&s.timer_seconds<=86400);
}
function restore(){try{const data=JSON.parse(localStorage.getItem(STORE)||'null');if(!data)return;data.recipe=normalizeRecipe(data.recipe);if(validRecipe(data.recipe)){recipe=data.recipe;page=Math.max(0,Math.min(recipe.steps.length,Number.isInteger(data.page)?data.page:0));}timer=new Timer(data.timer||{});timerPageKey=typeof data.timerPageKey==='string'?data.timerPageKey:'';timerSource=typeof data.timerSource==='string'?data.timerSource:'복원된 타이머';$('ingredients').value=typeof data.ingredients==='string'?data.ingredients:'';$('request').value=typeof data.request==='string'?data.request:'';}catch(e){notice('저장된 상태를 복원하지 못했습니다.',true);}}
function showStage(next){
 stage=next;
 for(let n=1;n<=4;n++)$('stage'+n).hidden=n!==next;
 document.querySelectorAll('[data-step]').forEach(el=>el.classList.toggle('active',Number(el.dataset.step)===next));
 $('backButton').hidden=next===1;
 $('backButton').textContent=next===2?'← 재촬영':next===3?'← 재료 수정':'← 메뉴 선택';
 if(next!==4){gestureOn=false;gate.reset();$('gestureToggle').textContent='제스처 켜기';$('gestureName').textContent='대기 중';$('holdProgress').value=0;}
 (next===4?$('gestureCameraSlot'):$('captureCameraSlot')).append($('cameraModule'));
 $('confirmedItems').textContent='확인한 재료: '+$('ingredients').value;
 $('retryMenus').hidden=menus.length>0;
 document.querySelector('#stage'+next+' h1')?.focus();
 window.scrollTo(0,0);
}
async function request(path,data){
 const options=data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Kitchen-Token':token},body:JSON.stringify(data)};
 const response=await fetch(path,options);const result=await response.json();if(!response.ok)throw Error(result.error||'서버 요청 실패');return result;
}
function setBusy(value){busy=value;$('capture').disabled=busy||!stream;$('recommend').disabled=busy||!reviewed;$('voice').disabled=busy||!recognition;document.querySelectorAll('.menu-card').forEach(b=>b.disabled=busy);$('importBook').disabled=busy;$('ingredients').disabled=busy;$('reviewIngredients').disabled=busy;$('captureArea').disabled=busy;$('request').disabled=busy;$('backButton').disabled=busy;$('manualEntry').disabled=busy;$('retryMenus').disabled=busy;}
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
     notice(`로컬 AI가 ${kind==='ingredients'?'재료를 확인':kind==='menus'?'메뉴를 추천':'레시피북을 작성'}하고 있습니다. ${Math.floor((Date.now()-started)/1000)}초 경과 · 첫 실행에는 모델 로딩이 포함됩니다.`);
   }
 }finally{setBusy(false);}
}
function getIngredients(){const items=$('ingredients').value.split(/[,，\n]/).map(x=>x.trim()).filter(Boolean);if(!items.length)throw Error('촬영한 재료를 확인하거나 재료 이름을 직접 입력하세요.');if(items.length>30)throw Error('재료는 30개까지 입력할 수 있습니다.');return items;}
function cameraFrame(maxSide=448,crop=false){
 if(!stream || !$('video').videoWidth)throw Error('웹캠을 먼저 켜고 화면이 보일 때까지 기다려 주세요.');
 const video=$('video'),canvas=document.createElement('canvas');
 const side=Math.min(video.videoWidth,video.videoHeight)*.75,sw=crop?side:video.videoWidth,sh=crop?side:video.videoHeight;
 const sx=(video.videoWidth-sw)/2,sy=(video.videoHeight-sh)/2,scale=Math.min(1,maxSide/Math.max(sw,sh));
 canvas.width=Math.round(sw*scale);canvas.height=Math.round(sh*scale);canvas.getContext('2d').drawImage(video,sx,sy,sw,sh,0,0,canvas.width,canvas.height);return canvas.toDataURL('image/jpeg',.93);
}
async function startCamera(){try{
 if(stream)return;
 if(!navigator.mediaDevices?.getUserMedia)throw Error('localhost의 Chrome/Edge에서 실행하세요.');
 stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}},audio:false});
 $('video').srcObject=stream;await $('video').play();$('cameraHint').hidden=true;$('cameraStart').disabled=true;$('cameraStop').disabled=false;setBusy(busy);notice('재료를 카메라에 보여 주고 촬영하세요.');
 stream.getVideoTracks()[0].addEventListener('ended',stopCamera);
}catch(e){stopCamera();notice('웹캠 연결 실패: '+e.message,true);}}
function stopCamera(){gestureOn=false;gesturePending=false;gate.reset();if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}$('video').srcObject=null;$('cameraHint').hidden=false;$('cameraStart').disabled=false;$('cameraStop').disabled=true;$('gestureToggle').textContent='제스처 켜기';$('gestureName').textContent='대기 중';$('holdProgress').value=0;setBusy(busy);}
function resetReview(){reviewed=false;$('reviewIngredients').checked=false;menus=[];renderMenus();setBusy(busy);}
async function capture(){try{
 if(busy)return;
 const image=cameraFrame(448,$('captureArea').value==='center');
 $('photo').src=image;$('photo').hidden=false;
 showStage(2);resetReview();$('ingredients').value='';$('uncertain').textContent='';$('evidence').replaceChildren();
 $('photoInfo').textContent='아래 촬영 사진이 모델에 전달됩니다. 인식 중…';
 notice('촬영 사진에서 재료 후보를 한 번 분석합니다. 완료 후 직접 확인해 주세요.');
 const result=await aiJob('ingredients',{image});
 $('ingredients').value=result.ingredients.join(', ');
 $('uncertain').textContent=result.uncertain.length?'확인 필요: '+result.uncertain.join(' / '):'사진과 재료 목록이 일치하는지 확인하세요.';
 for(const item of result.evidence||[]){$('evidence').append(element('p',item.name+' · '+item.evidence));}
 const info=result.image_info;
 $('photoInfo').textContent=demo?'DEMO: 사진과 무관한 고정 예시입니다.':info?`분석 사진 ${info.width} × ${info.height} · ${result.verification_status==='unverified'?'재확인 미완료 후보':'인식 후보'} ${result.ingredients.length}개`:'촬영 사진을 확인하세요.';
 save();notice(demo?'DEMO: 고정 예시입니다. 실제 사진 인식은 일반 모드에서 실행하세요.':result.verification_status==='unverified'?'재확인을 완료하지 못했습니다. 표시된 재료는 미검증 후보입니다. 사진과 직접 비교하여 수정한 뒤 확인란을 체크하세요.':'인식은 확정 결과가 아닙니다. 사진과 비교하여 재료를 수정하고 아래 확인란을 체크하세요.');
}catch(e){$('photoInfo').textContent='사진은 촬영됐지만 분석을 완료하지 못했습니다. 위 오류 내용을 확인하세요.';notice(e.message,true);}}
async function recommend(){try{
 if(!reviewed)throw Error('재료 목록을 확인하고 확인란을 체크해 주세요.');const items=getIngredients();showStage(3);notice('메뉴 추천을 시작합니다.');const result=await aiJob('menus',{ingredients:items,request:$('request').value});menus=result.menus;renderMenus();$('retryMenus').hidden=true;save();notice('메뉴를 선택하면 LLM이 해당 메뉴의 레시피북을 만듭니다.');
}catch(e){$('retryMenus').hidden=false;notice(e.message,true);}}
function renderMenus(){const container=$('menus');container.replaceChildren();menus.forEach(menu=>{
 const button=element('button',undefined,'menu-card');button.append(element('strong',menu.id+'. '+menu.name),element('p',menu.reason),element('small','추가 준비: '+(menu.missing.join(', ')||'없음')));button.onclick=()=>selectMenu(menu);button.disabled=busy;container.append(button);
});}
async function selectMenu(menu){try{
 const items=getIngredients();notice(menu.name+' 레시피북 생성 중');const rawResult=await aiJob('recipe',{ingredients:items,request:$('request').value,menu});
 const result=normalizeRecipe(rawResult);if(!validRecipe(result))throw Error('레시피 출력 형식이 올바르지 않습니다. 다시 생성하세요.');
 recipe=result;showStage(4);page=0;timerMode=false;if(!timer.running){timer.set(0);timerPageKey='';timerSource='설정 대기';}renderBook();renderMode();save();notice('레시피북이 준비되었습니다. 요리 중 제스처를 켜서 페이지와 타이머를 조작하세요.');
}catch(e){notice(e.message,true);}}
function renderBook(){
 const book=$('book');$('exportBook').disabled=!recipe;$('previous').disabled=!recipe||page===0;$('next').disabled=!recipe||page===recipe.steps.length;
 if(!recipe)return;
 book.replaceChildren();
 if(page===0){
   book.append(element('p','RECIPE / 준비하기','eyebrow'),element('h2',recipe.title,'recipe-title'),element('p','재료와 분량을 확인한 후 다음 페이지로 넘겨 주세요.','small'));
   const list=element('ul',undefined,'recipe-list');recipe.ingredients.forEach(item=>list.append(element('li',item)));book.append(list);
   if(recipe.notes.length){const notes=element('div',undefined,'recipe-notes');recipe.notes.forEach(note=>notes.append(element('p',note)));book.append(notes);}
 }else{
   const step=recipe.steps[page-1];book.append(element('p',recipe.title,'eyebrow'),element('p',String(page).padStart(2,'0'),'step-number'),element('h2',step.title,'recipe-title'),element('p',step.instruction,'instruction'));
   if(step.timer_seconds>0){const box=element('div',undefined,'step-timer'),button=element('button','이 단계 시간 설정','primary');button.onclick=()=>loadStepTimer();box.append(element('strong','이 단계 시간 '+timeText(step.timer_seconds)),button);book.append(box);}
   else book.append(element('p','이 단계에는 지정된 타이머가 없습니다. 필요하면 아래에서 직접 설정하세요.','small'));
 }
 $('pageLabel').textContent=`${page+1} / ${recipe.steps.length+1} · ${page===0?'준비':page===recipe.steps.length?'마지막 단계':'조리 단계'}`;
}
function movePage(delta){if(!recipe)return;const next=Math.max(0,Math.min(recipe.steps.length,page+delta));if(next===page){notice(delta>0?'마지막 페이지입니다.':'첫 페이지입니다.');return;}page=next;prepareStepTimer();renderBook();renderTimer();save();}
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
 timerMode=!timerMode;
 if(timerMode){prepareStepTimer();syncInputs();renderTimer();save();}
 renderMode();notice(timerMode?'타이머 모드: 👍 시작, 👎 일시정지, ☝️ 시간 증가, 🖐 감소, ✊ 초기화, 🤟 단위 변경, ✌️ 책 모드':'책 모드: 👍 다음 페이지, 👎 이전 페이지, ✌️ 타이머 모드, ✊ 이 단계 시간 설정');
}
function renderMode(){
 document.querySelector('.gesture-panel').classList.toggle('timer-guide',timerMode);$('gestureMode').textContent=timerMode?'타이머 모드':'책 모드';$('timerMode').textContent=timerMode?'책 모드로 돌아가기':'타이머 모드 열기';$('timerPanel').classList.toggle('active',timerMode);
 $('gestureGuide').textContent=timerMode?'약 0.9초 유지하세요. 다른 동작으로 바꾸면 새 명령을 받습니다. 같은 명령을 반복하려면 손을 잠시 내려 주세요.':'약 0.9초 유지하세요. ✊로 현재 단계 시간을 설정한 뒤 👍로 시작합니다. 같은 명령을 반복하려면 손을 내려 주세요.';
 $('increment').textContent='시간 조절 단위: '+({1:'1초',10:'10초',60:'1분',300:'5분'}[increments[incrementIndex]]);
 const items=timerMode?[['👍','시작 / 재개'],['👎','일시정지'],['✊','설정 시간으로 초기화'],['☝️','시간 +'],['🖐','시간 −'],['🤟','조절 단위 변경'],['✌️','책 모드로 돌아가기']]:[['👍','다음 페이지'],['👎','이전 페이지'],['✊','이 단계 시간 설정'],['✌️','타이머 모드 열기']];
 $('gestureCards').replaceChildren();for(const [icon,label] of items){const card=element('div',undefined,'gesture-card');card.append(element('span',icon,'hand-icon'),element('strong',label));$('gestureCards').append(card);}
}
function syncInputs(){const left=Math.ceil(timer.left());$('minutes').value=Math.floor(left/60);$('seconds').value=left%60;}
function renderTimer(){
 $('clock').textContent=timeText(timer.left());$('clock').classList.toggle('done',timer.finished);$('clock').classList.toggle('long-clock',timer.left()>=3600);$('timerState').textContent=timer.finished?'시간이 되었습니다!':timer.running?'조리 중 · 타이머 작동 중':timer.remaining>0?'설정됨 / 일시정지':'설정 대기';$('timerSource').textContent='현재 타이머: '+timerSource;
 const step=recipe&&page>0?recipe.steps[page-1]:null;
 $('currentStepTime').textContent=step?(step.timer_seconds?'현재 페이지: '+step.title+' · '+timeText(step.timer_seconds):'현재 페이지에는 지정 시간이 없습니다. 손동작으로 시간을 설정하세요.'):'조리 단계로 넘기면 시간이 자동 준비됩니다.';
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
 if(name==='Victory'){enterTimer();return;}
 if(!timerMode){if(name==='Thumb_Up')movePage(1);if(name==='Thumb_Down')movePage(-1);if(name==='Closed_Fist' && loadStepTimer()){timerMode=true;renderMode();}return;}
 if(name==='Thumb_Up')timerAction('start');
 if(name==='Thumb_Down')timerAction('pause');
 if(name==='Closed_Fist')timerAction('reset');
 if(name==='Pointing_Up')timerAction('adjust',increments[incrementIndex]);
 if(name==='Open_Palm')timerAction('adjust',-increments[incrementIndex]);
 if(name==='ILoveYou'){incrementIndex=(incrementIndex+1)%increments.length;renderMode();}
}
async function gestureLoop(){
 if(stage!==4||busy||!gestureOn||!stream||gesturePending)return;
 gesturePending=true;
 try{
   const result=await request('/api/gesture',{image:cameraFrame(480)});
   if(stage!==4||busy||!gestureOn)return;
   const name=result.gesture||'None';const gated=gate.feed(name,result.score,performance.now());
   $('gestureName').textContent=(names[name]||name)+(gated.progress===1?' · 손을 내려 주세요':'');$('holdProgress').value=gated.progress;
   if(gated.event)dispatchGesture(gated.event);
 }catch(e){gestureOn=false;gate.reset();$('gestureToggle').textContent='제스처 켜기';notice('제스처 인식 실패: '+e.message,true);}
 finally{gesturePending=false;}
}
function toggleGestures(){
 if(!stream)return notice('웹캠을 먼저 켜 주세요.',true);
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
async function importBook(event){try{const file=event.target.files[0];if(!file)return;if(file.size>100000)throw Error('레시피 파일은 100KB 이하여야 합니다.');const data=normalizeRecipe(JSON.parse(await file.text()));if(!validRecipe(data))throw Error('올바른 레시피 JSON 파일이 아닙니다.');recipe=normalizeRecipe(data);showStage(4);page=0;timerMode=false;if(!timer.running){timer.set(0);timerPageKey='';timerSource='설정 대기';}renderBook();renderMode();save();notice('저장한 레시피북을 불러왔습니다.');}catch(e){notice(e.message,true);}finally{event.target.value='';}}
$('cameraStart').onclick=startCamera;$('cameraStop').onclick=stopCamera;$('capture').onclick=capture;$('recommend').onclick=recommend;
$('previous').onclick=()=>movePage(-1);$('next').onclick=()=>movePage(1);$('gestureToggle').onclick=toggleGestures;$('timerMode').onclick=enterTimer;
$('startTimer').onclick=()=>timerAction('start');$('pauseTimer').onclick=()=>timerAction('pause');$('resetTimer').onclick=()=>timerAction('reset');$('plusTimer').onclick=()=>timerAction('adjust',60);$('minusTimer').onclick=()=>timerAction('adjust',-60);
$('setTimer').onclick=()=>{const min=Number($('minutes').value),sec=Number($('seconds').value);if(!Number.isInteger(min)||!Number.isInteger(sec)||min<0||sec<0||sec>59||min*60+sec>86400)return notice('0~24시간 범위로 분과 초를 입력하세요.',true);timer.set(min*60+sec);timerSource='직접 설정';timerPageKey=stepKey();save();renderTimer();};
$('exportBook').onclick=exportBook;$('importBook').onclick=()=>$('importFile').click();$('importFile').onchange=importBook;
$('ingredients').oninput=()=>{resetReview();save();};$('request').onchange=()=>{menus=[];renderMenus();save();};
$('reviewIngredients').onchange=()=>{reviewed=$('reviewIngredients').checked;setBusy(busy);};
$('loadCurrentTimer').onclick=()=>{if(loadStepTimer()){timerMode=true;renderMode();}};
$('backButton').onclick=()=>{if(!busy){showStage(Math.max(1,stage-1));notice(stage===1?'재료를 다시 촬영할 수 있습니다.':stage===2?'재료와 요청을 수정한 뒤 다시 추천받으세요.':'다른 메뉴를 선택하세요.');}};
$('manualEntry').onclick=()=>showStage(2);
$('retryMenus').onclick=recommend;
document.addEventListener('visibilitychange',()=>{gate.reset();if(document.hidden){$('holdProgress').value=0;}else renderTimer();});
setInterval(()=>{if(!document.hidden)gestureLoop();},150);
setInterval(()=>{if(timer.tick()){alarm();notice('⏰ 타이머 완료: '+timerSource);save();}renderTimer();},200);
async function initialize(){
 restore();showStage(1);configureVoice();prepareStepTimer();renderBook();renderMode();syncInputs();renderTimer();setBusy(false);
 try{const health=await request('/api/health');token=health.csrf;demo=health.demo;$('modeBadge').textContent=demo?'DEMO · 고정 예시':'LOCAL AI v1.2.0 · 내 PC에서 실행';
 const missing=Object.entries(health.models).filter(([,value])=>!value.exists).map(([key])=>key);
 notice(demo?'DEMO 모드입니다. 촬영·추천·생성 결과는 고정 예시이며 실제 모델 추론이 아닙니다. 제스처에는 실제 모델이 필요합니다.':missing.length?'모델 파일 확인 필요: '+missing.join(', ')+' · source/README.md를 확인하세요.':'준비되었습니다. 재료를 촬영하거나 직접 입력하세요.',!demo&&missing.length>0);
 }catch(e){notice('서버 연결 실패: '+e.message,true);}
}
initialize();
