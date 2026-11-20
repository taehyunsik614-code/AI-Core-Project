const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const code = fs.readFileSync(require.resolve('../static/app.js'),'utf8');
const setup = code.slice(code.indexOf('function setupPiVoice()'),code.indexOf('async function initialize('));
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('Pi utterance dispatch, duplicate suppression, corrections and stage navigation',async()=>{
  const nodes={}, get=id=>nodes[id]??={value:''};
  let poll, seen=[], confirmed, oledPage, action;
  const frame={session:'a',seq:0,text:'',status:'준비'};
  const env={stage:2,page:1,menus:[],recipe:{steps:[{instruction:'씻기'},{instruction:'볶기'}]},
    deviceOwner:'test',OWNER_KEY:'key',localStorage:{getItem:()=>'test'},$:get,
    busy:false,setInterval:fn=>poll=fn,bookPart:0,getIngredients:()=>get('ingredients').value.split(', '),
    prepareStepTimer(){},renderBook(){},renderTimer(){},save(){},syncDevice:()=>{oledPage=env.page;},
    recommend:()=>{confirmed=env.getIngredients();},request:async(path,data)=>{
      if(path.endsWith('poll'))return {...frame};
      seen.push(data);return {tool:action==='none'?'describe':'move',args:{action,old:'감자',new:'양파'}};
    }};
  get('reviewIngredients').onchange=()=>{};
  get('ingredients').oninput=()=>{};
  get('ingredients').value='감자, 달걀';
  get('notice').textContent='메뉴 추천';
  vm.runInNewContext(setup+';setupPiVoice()',env);
  await tick();
  async function say(text,a){action=a;frame.seq++;frame.text=text;await poll();await tick();}
  await say('감자가 아니라 양파야','replace');
  assert.equal(get('ingredients').value,'양파, 달걀');
  await poll();assert.equal(seen.length,1);
  env.busy=true;await say('추천해 줘','recommend');assert.equal(seen.length,1);
  env.busy=false;await poll();await tick();assert.deepEqual(confirmed,['양파','달걀']);
  env.stage=4;await say('다음 단계','next');assert.equal(oledPage,2);
  await say('다음 단계','next');assert.equal(env.page,2);
  await say('지금 뭐 해야 해?','none');assert.match(get('piVoiceStatus').textContent,/볶기/);
  action='previous';get('piCommand').value='이전 단계';get('piCommandForm').onsubmit({preventDefault(){}});
  await tick();assert.equal(seen.at(-1).source,'device');assert.equal(oledPage,1);
  frame.text_only=true;get('piCommandForm').querySelector=()=>({});
  const calls=seen.length;
  await say('다음 단계로 넘어가지고.');assert.equal(oledPage,2);
  await poll();assert.equal(env.page,2);
  await say('이전 단계');assert.equal(oledPage,1);
  await poll();assert.equal(env.page,1);
  await say('다음 단계');assert.equal(oledPage,2);
  await say('다음 단계');assert.equal(env.page,2);
  env.stage=2;await say('이전 단계');assert.equal(env.page,2);
  assert.equal(seen.length,calls);
});

test('DAY3 typed ask, spoken answer, timeout retry, recipe timer and duplicate guard',async()=>{
 const nodes={},get=id=>nodes[id]??={value:''};
 let poll, displayed=0, fail=false, asked=[];
 const frame={session:'one',seq:0,text:'',status:'준비',camera_ready:true,llm_ready:true};
 const env={stage:4,page:2,menus:[],recipe:{title:'예시',steps:Array.from({length:4},()=>({instruction:'버무리세요',timer_seconds:60}))},
   deviceOwner:'owner',OWNER_KEY:'owner',localStorage:{getItem:()=>'owner'},$:get,busy:false,setInterval:f=>poll=f,
   prepareStepTimer(){},renderBook(){},renderTimer(){},save(){},syncDevice:()=>{displayed=env.page;},
   request:async(path,payload)=>{
    if(path.endsWith('poll'))return {...frame};
    asked.push(payload);
    if(fail)throw Error('기기 시간 초과');
    if(payload.text==='두 단계 이동해 줘')return {tool:'ask',args:{},pending:{steps:2,guess:'next'},message:'다음으로 갈까요?'};
    if(payload.text==='얼마나 기다려?')return {tool:'describe',args:{topic:'time'}};
    return {tool:'move',args:{direction:'next',steps:payload.pending.steps}};
   }};
 get('commandMode').value='kitchen';
 vm.runInNewContext(setup+';setupPiVoice()',env);await tick();
 async function type(text){get('piCommand').value=text;get('piCommandForm').onsubmit({preventDefault(){}});await tick();}
 await type('두 단계 이동해 줘');assert.equal(env.page,2);
 fail=true;frame.seq++;frame.text='응';await poll();await tick();assert.equal(env.page,2);
 fail=false;frame.seq++;await poll();await tick();assert.equal(displayed,4);
 assert.equal(asked.at(-1).source,'voice');assert.equal(asked.at(-1).history.length,2);
 const length=asked.length;await poll();assert.equal(asked.length,length);
 await type('얼마나 기다려?');assert.match(get('piVoiceStatus').textContent,/1분/);
 assert.equal(asked.at(-1).history.length,0);
});
