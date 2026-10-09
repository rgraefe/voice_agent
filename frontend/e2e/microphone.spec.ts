import {test,expect} from '@playwright/test';

test.beforeEach(async({page})=>{
 await page.route('**/api/**',route=>route.fulfill({json:route.request().url().endsWith('/bootstrap')?
  {user:{role:'founder'},local_demo:true,voice_ready:false,missing:[],agent:{name:'Mira',language:'de',max_minutes:15},topics:[]}:[]}));
 await page.addInitScript(()=>{
  const w=window as any;w.micStopped=0;w.audioClosed=0;w.signal=0;
  Object.defineProperty(navigator.mediaDevices,'getUserMedia',{configurable:true,value:async()=>({getTracks:()=>[{stop:()=>w.micStopped++}]})});
  w.AudioContext=class{
   state='running';async resume(){}async close(){this.state='closed';w.audioClosed++;}
   createMediaStreamSource(){return {connect(){},disconnect(){}};}
   createAnalyser(){return {fftSize:1024,getFloatTimeDomainData(data:Float32Array){data.fill(w.signal);}};}
  };
 });
 await page.goto('/');
});

test('shows live input level and releases microphone when stopped',async({page})=>{
 await page.getByRole('button',{name:'Mikrofon testen',exact:true}).click();
 const meter=page.getByRole('meter',{name:'Mikrofonpegel'});
 await expect(meter).toHaveAttribute('aria-valuenow','0');
 await page.evaluate(()=>{(window as any).signal=0.08;});
 await expect(meter).toHaveAttribute('aria-valuenow','40');
 await expect(page.getByText('Audiosignal erkannt',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Mikrofontest beenden'}).click();
 await expect(meter).toHaveCount(0);
 expect(await page.evaluate(()=>[(window as any).micStopped,(window as any).audioClosed])).toEqual([1,1]);
});

test('silence times out without claiming a working signal',async({page})=>{
 await page.clock.install();
 await page.getByRole('button',{name:'Mikrofon testen',exact:true}).click();
 await expect(page.getByRole('meter')).toBeVisible();
 await page.clock.fastForward(15001);
 await expect(page.getByRole('status')).toContainText('Kein Audiosignal erkannt');
 expect(await page.evaluate(()=>(window as any).micStopped)).toBe(1);
});

test('navigation frees the microphone',async({page})=>{
 await page.getByRole('button',{name:'Mikrofon testen',exact:true}).click();
 await expect(page.getByRole('meter')).toBeVisible();
 await page.getByRole('button',{name:'Gesprächsverlauf',exact:true}).click();
 expect(await page.evaluate(()=>(window as any).micStopped)).toBe(1);
});

test('permission denial closes audio context and shows a useful error',async({page})=>{
 await page.evaluate(()=>{Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>{throw new Error('Mikrofonzugriff verweigert.');},configurable:true});});
 await page.getByRole('button',{name:'Mikrofon testen',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Mikrofonzugriff verweigert');
 expect(await page.evaluate(()=>(window as any).audioClosed)).toBe(1);
});
