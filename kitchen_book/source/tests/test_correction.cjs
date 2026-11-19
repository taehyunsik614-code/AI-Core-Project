// Exercise the shipped capture handler with controlled camera and inference adapters.
const {readFileSync}=require('node:fs');
const {runInNewContext}=require('node:vm');
const assert=require('node:assert/strict');
const {test}=require('node:test');
const path=require('node:path');
const app=readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const capture=app.slice(app.indexOf('async function capture()'),app.indexOf('async function recommend()'));
for(const [label,target,names,expected] of [
 ['replace selected',{index:1},['감자'],'달걀, 감자'],
 ['append missing',{index:null},['감자'],'달걀, 양파, 감자'],
 ['preserve on ambiguity',{index:0},[],'달걀, 양파'],
 ['preserve on error',{index:0},null,'달걀, 양파'],
 ['full scan',null,['대파'],'대파']]){
 test(label,async()=>{
   const elements={scanMode:{value:'quick'},ingredients:{value:'달걀, 양파'}};
   const get=id=>elements[id]??={};
   const env={busy:false,captureTarget:target,$:get,demo:false,cameraFrame:()=>'',showStage(){},resetReview(){},setTarget(){},save(){},notice(){},rebuildTargets(){},renderEvidence(){},evidenceTexts:[],
     aiJob:async(kind,payload)=>{
       assert.equal(payload.scan,target?'single':'quick');
       if(!names)throw Error('camera error');
       return {ingredients:names,uncertain:[]};
     }};
   await runInNewContext(capture+';capture()',env);
   assert.equal(get('ingredients').value,expected);
 });
}
test('fresh visit opens capture and clears a stale OLED step',async()=>{
 const init=app.slice(app.indexOf('async function initialize()'),app.indexOf("$('resumeBook').onclick"));
 const sync=app.slice(app.indexOf('async function syncDevice()'),app.indexOf('let timer=new Timer()'));
 const states=[];
 const memory=new Map();
 const element={options:[{},{}]};
 const env={oledBitmap:()=> 'frame',stage:4,recipe:{steps:[1,2,3,4]},page:4,timer:{finished:true,left:()=>20},timerMode:false,
   piConfigured:false,token:'',sendingState:false,deviceReady:false,lastDeviceState:'',lastSyncTime:0,
   deviceOwner:'current',OWNER_KEY:'owner',STORE:'recipe',demo:false,$:()=>element,
   localStorage:{setItem:(k,v)=>memory.set(k,v),getItem:k=>memory.get(k)},
   setupPiVoice(){},configureVoice(){},prepareStepTimer(){},renderBook(){},renderMode(){},syncInputs(){},renderTimer(){},setBusy(){},notice(){},
   showStage:n=>{env.stage=n;},
   request:async(path,payload)=>{if(payload){states.push(JSON.parse(JSON.stringify(payload)));return payload;}return {device:'pi',csrf:'token',demo:false,models:{}};}
 };
 await runInNewContext(sync+init+';initialize()',env);
 assert.equal(env.stage,1);
 assert.deepEqual(states,[{stage:1,mode:'idle',page:0,total:0,seconds:0}]);
});
test('OLED labels follow workflow and cooking step while timer runs',()=>{
 const renderer=app.slice(app.indexOf('function oledBitmap('),app.indexOf('async function syncDevice()'));
 const labels=[];
 const ctx={fillText:t=>labels.push(t),getImageData:()=>({data:new Uint8Array(8192*4)})};
 const env={document:{createElement:()=>({getContext:()=>ctx})},btoa,timeText:()=> '02:00'};
 for(let stage=1;stage<=4;stage++)
   runInNewContext(renderer+';oledBitmap('+stage+',"재료 볶기",2,5,"running",120)',env);
 assert.deepEqual(labels,['01 재료 촬영','02 재료 확인','03 메뉴 추천','04 요리 시작','2/5','재료 볶기','타이머 02:00']);
});
