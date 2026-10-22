/* Optional functional DOM test. Start the demo server on 8765.
   npm install --no-save jsdom
   node source/tests/test_dom.cjs
   No real camera, inference, browser rendering or speech is tested here. */
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const origin=process.env.KITCHEN_TEST_URL||'http://127.0.0.1:8765';
const jpeg=fs.readFileSync(path.join(__dirname,'camera_fixture.jpg')).toString('base64');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const wait=async(fn)=>{for(let i=0;i<150;i++){if(fn())return;await sleep(50);}throw Error('Timed out waiting for DOM condition');};
(async()=>{
 const errors=[];let pose='None';
 const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',e=>errors.push(e.message));
 const dom=await JSDOM.fromURL(origin,{resources:'usable',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole,beforeParse(w){
   w.scrollTo=()=>{};
   w.fetch=(url,options)=>url==='/api/gesture'?Promise.resolve({ok:true,json:async()=>({gesture:pose,score:pose==='None'?0:.99})}):fetch(new URL(url,origin),options);
   w.HTMLMediaElement.prototype.play=async function(){};
   Object.defineProperties(w.HTMLVideoElement.prototype,{videoWidth:{get:()=>640},videoHeight:{get:()=>480}});
   Object.defineProperty(w.navigator,'mediaDevices',{value:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}],getVideoTracks:()=>[{addEventListener(){}}]})}});
   w.HTMLCanvasElement.prototype.getContext=()=>({drawImage(){}});
   w.HTMLCanvasElement.prototype.toDataURL=()=>('data:image/jpeg;base64,'+jpeg);
   w.AudioContext=class{constructor(){this.state='running';this.currentTime=0;this.destination={};}createOscillator(){return {frequency:{value:0},connect(){},start(){},stop(){}};}createGain(){return {gain:{value:0},connect(){}};}};
 }});
 try{
 const w=dom.window,$=id=>w.document.getElementById(id);
 await wait(()=>$('modeBadge').textContent.includes('DEMO'));
 $('cameraStart').click();await wait(()=>!$('capture').disabled);$('capture').click();
 await wait(()=>$('ingredients').value.includes('달걀'));
 assert.equal($('recommend').disabled,true);$('reviewIngredients').click();$('recommend').click();await wait(()=>w.document.querySelectorAll('.menu-card').length===3);
 w.document.querySelector('.menu-card').click();await wait(()=>$('book').textContent.includes('재료와 분량'));
 $('next').click();assert.ok($('book').textContent.includes('재료 손질'));
 $('gestureToggle').click();
 // Exercise the actual poll -> gate -> dispatcher -> UI pipeline.
 const show=async name=>{pose='None';await sleep(650);pose=name;await sleep(1300);pose='None';await sleep(600);};
 await show('Thumb_Up');assert.ok($('book').textContent.includes('달걀 볶기'));assert.equal($('clock').textContent,'01:00');
 await show('Victory');assert.equal($('gestureMode').textContent,'타이머 모드');assert.equal($('clock').textContent,'01:00');
 await show('Pointing_Up');assert.equal($('clock').textContent,'02:00');
 await show('Open_Palm');assert.equal($('clock').textContent,'01:00');
 await show('Thumb_Up');assert.ok($('timerState').textContent.includes('작동 중'));
 await show('Thumb_Down');assert.ok($('timerState').textContent.includes('일시정지'));
 await show('Closed_Fist');assert.equal($('clock').textContent,'01:00');
 await show('ILoveYou');assert.ok($('increment').textContent.includes('5분'));
 await show('Victory');assert.equal($('gestureMode').textContent,'책 모드');
 await show('Thumb_Up');assert.ok($('book').textContent.includes('토마토 볶기'));
 await show('Closed_Fist');assert.equal($('clock').textContent,'03:00');assert.equal($('gestureMode').textContent,'타이머 모드');
 $('gestureToggle').click();
 $('minutes').value='0';$('seconds').value='3';$('setTimer').click();$('startTimer').click();$('previous').click();
 const saved=JSON.parse(w.localStorage.getItem('handsfree-kitchen-v1'));assert.equal(saved.timer.running,true);
 // Restore saved data through the app's restore path, retaining the absolute end time.
 w.restore();await wait(()=>$('timerState').textContent.includes('시간이 되었습니다'));
 assert.ok($('notice').textContent.includes('타이머 완료'));
 const pageBefore=$('pageLabel').textContent;
 $('next').click();assert.notEqual($('pageLabel').textContent,pageBefore);
 // Regression: legacy/model recipe has explicit minutes but no timer field.
 w.eval(`recipe=normalizeRecipe({title:'회귀 검사',ingredients:['재료'],notes:[],steps:[{title:'볶기',instruction:'3분간 볶습니다.'},{title:'섞기',instruction:'골고루 섞습니다.'},{title:'끓이기',instruction:'2분 끓입니다.',timer_seconds:0}]});page=0;timer.set(0);timerPageKey='';timerMode=false;renderBook();renderMode();`);
 $('next').click();assert.equal($('clock').textContent,'03:00');
 $('timerMode').click();$('startTimer').click();$('next').click();
 assert.ok($('timerState').textContent.includes('작동 중'));assert.ok($('timerSource').textContent.includes('볶기'));
 $('pauseTimer').click();$('startTimer').click();assert.ok($('timerSource').textContent.includes('볶기'));$('pauseTimer').click();$('next').click();assert.equal($('clock').textContent,'02:00');
 $('previous').click();assert.equal($('clock').textContent,'00:00');
 w.eval('timerMode=false;renderMode();dispatchGesture("Closed_Fist");');
 assert.equal($('gestureMode').textContent,'타이머 모드');
 w.dispatchGesture('Pointing_Up');assert.equal($('clock').textContent,'05:00');
 w.dispatchGesture('Thumb_Up');assert.ok($('timerState').textContent.includes('작동 중'));w.dispatchGesture('Thumb_Down');
 // Larger guide is structurally beside the book, with mode-specific labels.
 assert.equal($('gestureCards').closest('.book-area'),$('book').closest('.book-area'));
 assert.equal($('gestureCards').children.length,7);
 const checkStage=n=>{for(let i=1;i<=4;i++)assert.equal($('stage'+i).hidden,i!==n);};
 checkStage(4);assert.equal($('video').closest('#gestureCameraSlot').id,'gestureCameraSlot');
 $('backButton').click();checkStage(3);assert.equal($('gestureToggle').textContent,'제스처 켜기');
 w.document.querySelector('.menu-card').click();await wait(()=>!$('stage4').hidden);checkStage(4);
 $('backButton').click();$('backButton').click();checkStage(2);
 $('backButton').click();checkStage(1);assert.equal($('backButton').hidden,true);
 $('manualEntry').click();checkStage(2);
 $('ingredients').value='수정한 재료';$('ingredients').dispatchEvent(new w.Event('input'));
 assert.equal($('reviewIngredients').checked,false);assert.equal($('recommend').disabled,true);
 assert.deepEqual(errors,[]);
 console.log('PASS: DOM initialization, fake webcam capture, menu/recipe jobs, seven gesture routes through polling, step timer loading by fist, timer expiry/persistence, page navigation. Rendering and physical recognition not tested.');
 }finally{dom.window.close();}
})().catch(e=>{console.error(e);process.exit(1);});
