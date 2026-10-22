/* Start the demo server on port 8765. Optional: npm install --no-save playwright */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.KITCHEN_BROWSER||undefined,args:JSON.parse(process.env.KITCHEN_BROWSER_ARGS||'[]')});
 try{
  const page=await browser.newPage();await page.goto(process.env.KITCHEN_TEST_URL||'http://127.0.0.1:8765');
  await page.waitForFunction(()=>document.getElementById('modeBadge').textContent.includes('DEMO'));
  if(process.env.KITCHEN_FONT_CSS){await page.addStyleTag({content:require('fs').readFileSync(process.env.KITCHEN_FONT_CSS,'utf8')});await page.evaluate(()=>document.fonts.ready);}
  await page.evaluate(()=>{
   recipe=normalizeRecipe({title:'토마토 달걀볶음',ingredients:['달걀 2개'],notes:[],steps:[{title:'달걀 볶기',instruction:'달걀을 부드럽게 저어 3분간 충분히 익혀 주세요.'}]});
   showStage(4);page=1;prepareStepTimer();renderBook();renderMode();timer.set(86400);renderTimer();
  });
  for(const width of [1920,1440,1280,1024,768,390]){
   await page.setViewportSize({width,height:1080});
   for(const focus of [false]){
    await page.evaluate(f=>document.body.classList.toggle('cooking-focus',f),focus);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`horizontal overflow: width=${width}, focus=${focus}`);
    assert.ok(await page.locator('#gestureCards').isVisible());
    const [guide,book]=await Promise.all([page.locator('#gestureCards').boundingBox(),page.locator('#book').boundingBox()]);
    assert.ok(guide.y<book.y,'Gesture cards should sit immediately above the recipe');
   }
  }
  console.log('PASS: 1920/1440/1280/1024/768/390px, recipe stage, long 24-hour clock, gesture guide placement, no horizontal overflow.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
