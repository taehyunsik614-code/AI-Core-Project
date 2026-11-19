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
});
