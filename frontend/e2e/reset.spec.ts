import {test,expect} from '@playwright/test';

for(const fail of [false,true]){
 test(`demo reset ${fail?'reports failed stop without claiming reset':'stops interview and clears state'}`,async({page})=>{
  let stopped=0;const ids:string[]=[];
  await page.route('**/api/**',async route=>{
   const request=route.request(),path=new URL(request.url()).pathname;
   if(path==='/api/bootstrap')return route.fulfill({json:{user:{role:'founder'},local_demo:true,voice_ready:false,missing:[],agent:{name:'Mira',max_minutes:15},topics:[]}});
   if(path.endsWith('/stop')){stopped++;return route.fulfill(fail?{status:503,json:{error:{message:'Speichern nicht erreichbar'}}}:{json:{status:'incomplete'}});}
   if(path==='/api/interviews'&&request.method()==='POST'){
    const id=request.postDataJSON().request_id;ids.push(id);
    return route.fulfill({json:{id,status:'active',mode:'simulation',planner_version:1,created_at:new Date().toISOString(),config:{name:'Mira',version:1,topics:[]},topics:{},transcript:[{id:'old',role:'user',text:'Alter Firmenname',timestamp:new Date().toISOString()}]}});
   }
   return route.fulfill({json:[]});
  });
  await page.goto('/');await page.getByRole('button',{name:'Text-Testlauf'}).click();
  await expect(page.getByText('Alter Firmenname',{exact:true})).toBeVisible();
  await page.getByRole('textbox',{name:'Testantwort',exact:true}).fill('Alter Entwurf');
  await page.getByRole('button',{name:'Demo zurücksetzen'}).click();
  if(fail){
   await expect(page.getByRole('alert')).toContainText('Speichern nicht erreichbar');
   await expect(page.getByText('Alter Firmenname',{exact:true})).toBeVisible();
  }else{
   await expect(page.getByText('Hier entsteht eure Unterhaltung.')).toBeVisible();
   await expect(page.getByText('Alter Firmenname',{exact:true})).toHaveCount(0);
   await page.getByRole('button',{name:'Text-Testlauf'}).click();
   await expect(page.getByRole('textbox',{name:'Testantwort',exact:true})).toHaveValue('');
   expect(ids).toHaveLength(2);expect(ids[0]).not.toBe(ids[1]);
  }
  expect(stopped).toBe(1);
 });
}

test('demo reset is absent outside local demo mode',async({page})=>{
 await page.route('**/api/**',route=>route.fulfill({json:route.request().url().endsWith('/bootstrap')?{user:{role:'founder'},local_demo:false,voice_ready:false,missing:[],agent:{name:'Mira',max_minutes:15},topics:[]}:[]}));
 await page.goto('/');await expect(page.getByRole('button',{name:'Interview starten'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Demo zurücksetzen'})).toHaveCount(0);
});
