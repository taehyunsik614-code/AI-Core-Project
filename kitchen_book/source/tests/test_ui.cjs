const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KITCHEN_BROWSER||undefined,args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']});
 const page=await browser.newPage({viewport:{width:1366,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.KITCHEN_TEST_URL||'http://127.0.0.1:8765');await page.waitForFunction(()=>document.querySelector('#modeBadge').textContent.includes('DEMO'));
 const stage=async n=>{for(let i=1;i<=4;i++)assert.equal(await page.locator('#stage'+i).isVisible(),i===n);assert.equal(await page.locator('#backButton').isVisible(),n!==1);};
 await stage(1);await page.click('#cameraStart');await page.waitForFunction(()=>document.querySelector('video').videoWidth>0);await page.click('#capture');await page.waitForFunction(()=>document.querySelector('#ingredients').value.includes('달걀'));await stage(2);
 await page.click('#backButton');await stage(1);await page.click('#manualEntry');await stage(2);
 await page.fill('#ingredients','달걀, 토마토, 양파');await page.check('#reviewIngredients');await page.click('#recommend');await page.waitForSelector('.menu-card');await stage(3);
 await page.locator('.menu-card').first().click();await page.waitForSelector('#stage4:not([hidden])');await stage(4);assert.equal(await page.locator('#gestureCameraSlot video').count(),1);
 await page.click('#next');await page.click('#next');await page.click('#startTimer');await page.click('#previous');assert.match(await page.locator('#timerState').innerText(),/작동 중/);
 await page.route('**/api/gesture',r=>r.fulfill({json:{gesture:'Thumb_Up',score:.99}}));
 await page.click('#gestureToggle');await page.waitForTimeout(1600);assert.match(await page.locator('#pageLabel').innerText(),/3 \/ /);
 await page.click('#backButton');await stage(3);assert.equal(await page.locator('#gestureToggle').innerText(),'제스처 켜기');
 await page.locator('.menu-card').first().click();await page.waitForSelector('#stage4:not([hidden])');await stage(4);
 await page.click('#backButton');await page.click('#backButton');await stage(2);await page.fill('#ingredients','달걀');assert.equal(await page.locator('#recommend').isDisabled(),true);await page.check('#reviewIngredients');await page.click('#recommend');await page.waitForSelector('.menu-card');await stage(3);
 for(const width of [1024,800,390]){await page.setViewportSize({width,height:800});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow at '+width);}
 assert.deepEqual(errors,[]);console.log('PASS: 4 stages, back navigation, camera relocation, edit invalidation, menu reselection, timer, gesture, responsive menu layout.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
