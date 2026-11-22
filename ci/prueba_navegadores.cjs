const { chromium, firefox, webkit } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = 'http://127.0.0.1:8100/';
  for (const [name, engine, viewport] of [['Chromium',chromium,{width:1440,height:900}],['Firefox',firefox,{width:1024,height:768}],['WebKit móvil',webkit,{width:390,height:844}]]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage({viewport});
      const errors=[];page.on('pageerror', e=>errors.push(e.message));
      await page.goto(base);
      await page.locator('#scenes button').first().waitFor();
      await page.selectOption('#role','josue');
      await page.getByRole('button',{name:'Diap. 5'}).click();
      assert.match(await page.locator('#sceneTitle').innerText(), /recepción/);
      try{await page.waitForFunction(()=>{const v=document.getElementById('slides');return v.readyState>=2 && v.currentTime>=105;},null,{timeout:30000});}
      catch(e){console.error(name,await page.locator('#slides').evaluate(v=>({src:v.currentSrc,tiempo:v.currentTime,estado:v.readyState,error:v.error?.message,seekable:v.seekable.length})));throw e;}
      await page.click('#rehearse');
      try{await page.waitForFunction(()=>document.getElementById('message').textContent==='Ensayo en curso.',null,{timeout:25000,polling:200});}
      catch(e){console.error(name,await page.locator('#message').innerText(),await page.locator('#slides').evaluate(v=>({visibility:document.visibilityState,src:v.currentSrc,tiempo:v.currentTime,estado:v.readyState,pausado:v.paused,dim:[v.videoWidth,v.videoHeight],error:v.error?.message})));throw e;}
      await page.waitForFunction(()=>document.getElementById('time').textContent==='0:01');
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.click('#stop');
      assert(await page.locator('#record').isVisible());
      assert.deepEqual(errors,[]);
      console.log(name+' · reproducción de las diapositivas, guía sincronizada, ensayo y ancho correcto.');
    }finally{await browser.close();}
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
