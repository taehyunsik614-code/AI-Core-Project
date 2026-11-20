/* Run app.py --demo --port 8765, then node source/tests/test_ui.cjs.
   Requires Playwright. Camera and recognition results are simulated. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KITCHEN_BROWSER||undefined,args:[...JSON.parse(process.env.KITCHEN_BROWSER_ARGS||'[]'),'--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 try{
 const context=await browser.newContext({viewport:{width:1366,height:768},permissions:['camera'],acceptDownloads:true});
 const p=await context.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto(process.env.KITCHEN_TEST_URL||'http://127.0.0.1:8765');await p.waitForFunction(()=>document.querySelector('#modeBadge').textContent.includes('DEMO'));
 await p.locator('#cameraStart').click();await p.waitForFunction(()=>document.querySelector('#video').videoWidth>0);await p.locator('#capture').click();
 await p.waitForFunction(()=>document.querySelector('#ingredients').value.includes('달걀'));
 assert.equal(await p.locator('#stage2').isVisible(),true);assert.equal(await p.locator('#stage1').isVisible(),false);
 assert.equal(await p.locator('#recommend').isDisabled(),true);
 await p.locator('#reviewIngredients').check();await p.locator('#recommend').click();await p.locator('.menu-card').first().waitFor();
 assert.equal(await p.locator('#stage3').isVisible(),true);assert.equal(await p.locator('.menu-card').count(),3);
 await p.locator('.menu-select').first().click();await p.locator('#stage4').waitFor();
 await p.waitForFunction(()=>bookParts.length>0);
 // Navigate across any continuation pages to the first cooking step.
 while(await p.evaluate(()=>page===0))await p.locator('#next').click();
 assert.ok((await p.locator('#book').innerText()).includes('재료 손질'));
 let pose='None';await p.route('**/api/gesture',route=>route.fulfill({json:{gesture:pose,score:pose==='None'?0:.99}}));
 await p.locator('#gestureToggle').click();
 assert.equal(await p.evaluate(()=>$('gestureVideo').srcObject===$('video').srcObject),true);
 const gesture=async name=>{pose='None';await p.waitForTimeout(650);pose=name;await p.waitForTimeout(1400);pose='None';await p.waitForTimeout(600);};
 await gesture('Thumb_Up');assert.equal(await p.evaluate(()=>page),2);assert.equal(await p.locator('#clock').innerText(),'01:00');
 await gesture('Open_Palm');assert.equal(await p.locator('#gestureMode').innerText(),'타이머 모드');
 await gesture('Pointing_Up');assert.equal(await p.locator('#clock').innerText(),'02:00');
 await gesture('Thumb_Up');assert.ok((await p.locator('#timerState').innerText()).includes('작동 중'));
 await gesture('Thumb_Down');assert.ok((await p.locator('#timerState').innerText()).includes('일시정지'));
 const state=await p.evaluate(()=>({mode:timerMode,duration:timer.duration,page}));
 await gesture('Victory');await gesture('Closed_Fist');await gesture('ILoveYou');
 assert.deepEqual(await p.evaluate(()=>({mode:timerMode,duration:timer.duration,page})),state);
 await p.locator('#resetTimer').click();assert.equal(await p.locator('#clock').innerText(),'02:00');
 await p.locator('#minusTimer').click();assert.equal(await p.locator('#clock').innerText(),'01:00');
 await p.locator('#changeIncrement').click();assert.ok((await p.locator('#increment').innerText()).includes('5분'));
 await gesture('Open_Palm');assert.equal(await p.locator('#gestureMode').innerText(),'책 모드');
 await gesture('Pointing_Up');assert.equal(await p.locator('#gestureMode').innerText(),'타이머 모드');assert.equal(await p.locator('#clock').innerText(),'01:00');
 // Continuing to hold the index must not add time after changing mode.
 pose='None';await p.waitForTimeout(650);pose='Open_Palm';await p.waitForTimeout(1400);pose='Pointing_Up';await p.waitForTimeout(2600);
 assert.equal(await p.locator('#clock').innerText(),'01:00');pose='None';
 await p.locator('#gestureToggle').click();
 await p.locator('#manualTimer').click();await p.locator('#minutes').fill('0');await p.locator('#seconds').fill('4');await p.locator('#setTimer').click();
 assert.equal(await p.locator('#timerDialog').isVisible(),false);
 await p.locator('#startTimer').click();await p.locator('#next').click();assert.equal(await p.evaluate(()=>timer.running),true);
 await p.reload();await p.waitForFunction(()=>document.querySelector('#modeBadge').textContent.includes('DEMO'));
 assert.equal(await p.locator('#stage1').isVisible(),true);
 await p.locator('#resumeBook').click();
 assert.equal(await p.locator('#stage4').isVisible(),true);
 await p.waitForFunction(()=>document.querySelector('#timerState').textContent.includes('시간이 되었습니다'),null,{timeout:10000});
 const downloaded=p.waitForEvent('download');await p.locator('#exportBook').click();assert.equal((await downloaded).suggestedFilename(),'recipe-book.json');
 // No commands may run off the cooking screen; an in-flight reply is discarded.
 await p.evaluate(()=>{showStage(2);const before=page;dispatchGesture('Thumb_Up');if(page!==before)throw Error('hidden screen moved');});
 await p.locator('#ingredients').fill('수정한 재료');assert.equal(await p.locator('#reviewIngredients').isChecked(),false);assert.equal(await p.locator('#recommend').isDisabled(),true);
 assert.deepEqual(errors,[]);
 console.log('PASS: four-stage capture/review/menu/book flow; shared webcam; four gesture routes; retired poses ignored; held-pose mode safety; manual timer, pause/reset/adjust, persistence/expiry/download; editing invalidates review. Recognition is mocked.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
