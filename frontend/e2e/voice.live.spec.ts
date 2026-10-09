import {test,expect} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';

test.use({launchOptions:{args:[
 '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
 '--use-file-for-fake-audio-capture='+path.resolve('../.local/browser-microphone.wav'),
 '--autoplay-policy=no-user-gesture-required'
]}});
test('live provider voice roundtrip with synthetic microphone',async({page})=>{
 test.skip(process.env.RUN_LIVE_VOICE!=='1','Explicit opt-in: real provider charges; synthetic fixture required.');
 test.setTimeout(90000);
 let interviewId='';
 page.on('response',async r=>{
  if(r.request().method()==='POST'&&r.url().endsWith('/api/interviews')&&r.ok())interviewId=(await r.json()).id;
 });
 await page.goto('/');
 await page.getByRole('button',{name:'Zum Startup-Interview'}).click();
 await expect(page.getByRole('button',{name:'Interview starten'})).toBeEnabled();
 try{
  await page.getByRole('button',{name:'Interview starten'}).click();
  await expect(page.getByText('Live verbunden',{exact:true})).toBeVisible({timeout:35000});
  await expect.poll(async()=>{
   if(!interviewId)return false;
   const r=await page.request.get('/api/interviews/'+interviewId);const item=await r.json();
   return item.goals?.startup_name?.status==='answered'&&item.transcript.filter((t:{role:string})=>t.role==='assistant').length>=2;
  },{timeout:45000,intervals:[1000]}).toBeTruthy();
  const item=await (await page.request.get('/api/interviews/'+interviewId)).json();
  const audio=await page.locator('audio').evaluateAll(nodes=>nodes.map(n=>({seconds:n.currentTime,paused:n.paused,readyState:n.readyState})));
  expect(audio.some(a=>a.seconds>1&&!a.paused)).toBeTruthy();
  expect(item.goals.startup_name.quote.toLowerCase()).toContain(item.goals.startup_name.value.toLowerCase());
  // Proper-name spelling is reported as an accuracy metric, not hidden or
  // accepted as an alias. The transport test requires grounded extraction and
  // correctly recognized common words; name accuracy needs human confirmation.
  const recognized=item.transcript.filter((t:{role:string})=>t.role==='user').map((t:{text:string})=>t.text.toLowerCase()).join(' ');
  expect(recognized).toContain('software');
  expect(recognized).toContain('unternehmen');
  const report={passed:true,synthetic_microphone:true,interview_id:interviewId,
   name_spelling_exact:item.goals.startup_name.value.toLowerCase()==='solar',
   user_turns:item.transcript.filter((t:{role:string})=>t.role==='user').length,
   assistant_turns:item.transcript.filter((t:{role:string})=>t.role==='assistant').length,
   audio_playback:audio,metrics:item.metrics};
  fs.writeFileSync('../.local/live-voice-result.json',JSON.stringify(report,null,2));
  await page.screenshot({path:'../.local/screenshots/live-voice.png',fullPage:true});
 }finally{
  if(interviewId)await page.request.post('/api/interviews/'+interviewId+'/stop',{headers:{'X-Requested-With':'founder-app'}});
 }
});
