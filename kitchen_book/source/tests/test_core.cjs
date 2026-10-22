const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Timer,GestureGate,timeText}=require('../static/core.js');
test('timer start/pause/resume/reset and absolute deadline',()=>{
 const t=new Timer();t.set(180);t.start(1000);assert.equal(t.left(61000),120);t.start(61000);assert.equal(t.left(61000),120);
 t.pause(61000);assert.equal(t.left(999999),120);t.start(70000);assert.equal(t.left(100000),90);
 assert.equal(t.tick(190001),true);assert.equal(t.tick(190002),false);assert.equal(t.finished,true);t.reset();assert.equal(t.left(),180);assert.equal(t.finished,false);
});
test('adjustment pauses and supports one-second through 24-hour limits',()=>{
 const t=new Timer();t.set(10);t.start(0);t.adjust(1,5000);assert.equal(t.left(),6);assert.equal(t.running,false);t.adjust(-300);assert.equal(t.left(),0);t.adjust(999999);assert.equal(t.left(),86400);
});
test('timer survives serialization and page state changes',()=>{
 const t=new Timer();t.set(60);t.start(1000);const copy=new Timer(JSON.parse(JSON.stringify(t.snapshot())));assert.equal(copy.left(31000),30);assert.equal(copy.tick(62000),true);assert.equal(timeText(3601),'1:00:01');
});
test('gesture fires once, requires neutral hand release, and rejects low confidence',()=>{
 const gate=new GestureGate();let events=[];
 for(let n=0;n<=2000;n+=100){const r=gate.feed('Thumb_Up',.9,n);if(r.event)events.push(r.event);}
 assert.deepEqual(events,['Thumb_Up']);
 // Switching directly to a different recognized pose is deliberately not a release.
 assert.equal(gate.feed('Victory',.95,2100).event,null);
 gate.feed('None',0,2200);gate.feed('None',0,2600);
 for(let n=2700;n<=3700;n+=100){const r=gate.feed('Victory',.9,n);if(r.event)events.push(r.event);}
 assert.deepEqual(events,['Thumb_Up','Victory']);
 gate.reset();for(let n=0;n<2000;n+=100)assert.equal(gate.feed('Thumb_Up',.4,n).event,null);
});
test('inference interruption cannot satisfy a hold',()=>{
 const gate=new GestureGate();gate.feed('Thumb_Up',1,0);gate.feed('Thumb_Up',1,400);
 assert.equal(gate.feed('Thumb_Up',1,3000).event,null);assert.equal(gate.feed('Thumb_Up',1,3400).event,null);
});

test('legacy recipe duration fallback matches Python corpus',()=>{
 const {durationFromText,normalizeRecipe}=require('../static/core.js');
 const cases=require('./duration_cases.json');
 for(const [text,expected] of cases)assert.equal(durationFromText(text),expected,text);
 const old={title:'요리',steps:[{title:'볶기',instruction:'3분간 볶습니다.'},{title:'혼합',instruction:'섞습니다.',timer_seconds:'30'}]};
 const fixed=normalizeRecipe(old);
 assert.equal(fixed.steps[0].timer_seconds,180);assert.equal(fixed.steps[1].timer_seconds,30);
 assert.equal(old.steps[0].timer_seconds,undefined); // source object is untouched
});

test('stable different pose works without lowering the hand; held pose never repeats',()=>{
 const gate=new GestureGate();let events=[];
 for(let n=0;n<2100;n+=100){const name=n<1000?'Thumb_Up':'Victory';const r=gate.feed(name,.99,n);if(r.event)events.push(r.event);}
 assert.deepEqual(events,['Thumb_Up','Victory']);
 for(let n=2100;n<4000;n+=100)assert.equal(gate.feed('Victory',.99,n).event,null);
});
