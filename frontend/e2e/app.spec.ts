import {test,expect} from '@playwright/test';

test('founder interview simulation, clarification, stop and history',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 await page.getByRole('button',{name:'Zum Startup-Interview'}).click();
 await expect(page.getByRole('heading',{name:'Deine Idee. Im Mittelpunkt.'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Interview starten'})).toBeDisabled();
 await page.screenshot({path:'../.local/screenshots/interview-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'Text-Testlauf'}).click();
 await expect(page.getByText('Lokale Simulation ohne KI und Sprachausgabe.',{exact:false})).toBeVisible();
 await page.getByRole('checkbox',{name:'Antwort als vage testen'}).check();
 await page.getByRole('textbox',{name:'Testantwort',exact:true}).fill('Wir bauen etwas Innovatives.');
 await page.getByRole('button',{name:'Testantwort senden'}).click();
 await expect(page.getByText('Unter welchem Namen tretet ihr auf?',{exact:true})).toBeVisible();
 await page.getByRole('checkbox',{name:'Antwort als vage testen'}).uncheck();
 await page.getByRole('textbox',{name:'Testantwort',exact:true}).fill('Wir heißen Lumio und bauen Energiemanagement für kleine Unternehmen.');
 await page.getByRole('button',{name:'Testantwort senden'}).click();
 await expect(page.getByText('In welcher Branche seid ihr tätig?',{exact:true})).toBeVisible();
 await page.screenshot({path:'../.local/screenshots/interview-active.png',fullPage:true});
 await page.getByRole('button',{name:'Gespräch beenden'}).click();
 await expect(page.getByText('Vorzeitig beendet',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Gesprächsverlauf',exact:true}).click();
 await expect(page.locator('.history-row').first()).toBeVisible();
 expect(errors).toEqual([]);
});

test('admin saves config and can inspect responsive layout',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Admin-Bereich öffnen'}).click();
 await page.getByRole('button',{name:'Agent konfigurieren',exact:true}).click();
 await page.getByLabel('Agentname',{exact:true}).fill('Mira');
 await page.getByRole('button',{name:'Version veröffentlichen'}).click();
 await expect(page.getByText('Neue Konfiguration veröffentlicht.',{exact:false})).toBeVisible();
 await expect(page.getByText('ELEVENLABS_API_KEY',{exact:true})).toBeVisible();
 await page.screenshot({path:'../.local/screenshots/admin-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Interview',exact:true}).click();
 await expect(page.getByRole('button',{name:'Mikrofon testen'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await page.screenshot({path:'../.local/screenshots/interview-mobile.png',fullPage:true});
});

test('complete interview produces a confirmed result',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Zum Startup-Interview'}).click();
 await page.getByRole('button',{name:'Text-Testlauf'}).click();
 const answers=[['Lumio',''],['Wir entwickeln SaaS.','SaaS'],['Wir sparen kleinen Firmen Zeit beim Energiemanagement.',''],['Kleine Unternehmen mit mehreren Standorten.',''],['Anna entwickelt, Ben verantwortet Vertrieb.',''],['Unser Produkt zeigt Stromverbrauch und Einsparungen.',''],['Ein MVP ist bei Pilotkunden im Einsatz.','MVP'],['12 zahlende Kunden im September, 2400 EUR Monatsumsatz.',''],['Excel ist die Alternative; wir automatisieren die Auswertung.',''],['Wir planen keine Finanzierungsrunde.','Nein'],['Ein Folgegespräch nächste Woche.','']];
 for(const [answer,choice] of answers){
  await page.getByRole('textbox',{name:'Testantwort',exact:true}).fill(answer);
  if(choice)await page.getByLabel('Zugeordnete Kategorie').selectOption(choice);
  await page.getByRole('button',{name:'Testantwort senden'}).click();
  await expect(page.getByRole('textbox',{name:'Testantwort',exact:true})).toHaveValue('');
 }
 await expect(page.getByRole('button',{name:'Zusammenfassung bestätigen'})).toBeVisible();
 await page.getByRole('button',{name:'Zusammenfassung bestätigen'}).click();
 await expect(page.getByText('Abgeschlossen',{exact:true})).toBeVisible();
 await expect(page.getByText('Danke! Dein Gesprächsergebnis ist gespeichert.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Auswertung & Transkript',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Vollständiges Transkript'})).toBeVisible();
 await expect(page.getByText('Noch kein Zielprofil mit Kriterien hinterlegt.')).toBeVisible();
 await expect(page.getByText('11 von 11 relevanten Pflichtangaben geklärt.')).toBeVisible();
 await page.getByLabel('Transkript durchsuchen').fill('Excel');
 await expect(page.locator('.transcript-entry.user')).toHaveCount(1);
 await page.getByLabel('Transkript durchsuchen').fill('');
 await page.screenshot({path:'../.local/screenshots/report-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await page.screenshot({path:'../.local/screenshots/report-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'Interview',exact:true}).click();
 const download=page.waitForEvent('download');await page.getByTitle('Ergebnis als JSON herunterladen').click();expect((await download).suggestedFilename()).toMatch(/startup-interview-.*\.json/);
});

test('denied microphone permission is shown without starting a session',async({page})=>{
 await page.addInitScript(()=>{Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:()=>Promise.reject(new DOMException('Mikrofonzugriff verweigert.','NotAllowedError'))});});
 await page.goto('/');await page.getByRole('button',{name:'Zum Startup-Interview'}).click();
 await page.getByRole('button',{name:'Mikrofon testen'}).click();
 await expect(page.getByRole('alert')).toContainText('Mikrofonzugriff verweigert');
 await expect(page.getByRole('button',{name:'Text-Testlauf'})).toBeEnabled();
});

test('configured match shows weighted score with linked evidence',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Admin-Bereich öffnen'}).click();
 await page.getByRole('button',{name:'Agent konfigurieren',exact:true}).click();
 await page.getByLabel('Kriterium hinzufügen').selectOption('sector');
 await page.locator('.match-rule').filter({has:page.getByRole('heading',{name:'Sektor',exact:true})}).getByLabel('Gewicht (1–10)').fill('3');
 await page.getByLabel('Kriterium hinzufügen').selectOption('stage');
 const stage=page.locator('.match-rule').filter({has:page.getByRole('heading',{name:'Entwicklungsphase',exact:true})});
 await stage.getByLabel('Idee',{exact:true}).uncheck();await stage.getByLabel('MVP',{exact:true}).check();
 await page.getByRole('button',{name:'Version veröffentlichen'}).click();
 await expect(page.getByText('Neue Konfiguration veröffentlicht.',{exact:false})).toBeVisible();
 await page.getByRole('button',{name:'Interview',exact:true}).click();
 await page.getByRole('button',{name:'Text-Testlauf'}).click();
 for(const [goal,text,choice] of [['startup_name','Lumio',''],['sector','SaaS','SaaS'],['stage','Wir haben eine Idee.','Idee']]){
  await page.getByLabel('Antwortziel im Test').selectOption(goal);
  await page.getByRole('textbox',{name:'Testantwort',exact:true}).fill(text);
  if(choice)await page.getByLabel('Zugeordnete Kategorie').selectOption(choice);
  await page.getByRole('button',{name:'Testantwort senden'}).click();
  await expect(page.getByRole('textbox',{name:'Testantwort',exact:true})).toHaveValue('');
 }
 await page.getByRole('button',{name:'Gespräch beenden'}).click();
 await page.getByRole('button',{name:'Auswertung & Transkript',exact:true}).click();
 await expect(page.locator('.score-card').first().locator('strong')).toHaveText('75');
 await expect(page.locator('.score-card').nth(1).locator('strong')).toHaveText('100');
 await page.getByRole('button',{name:'Beleg ansehen'}).first().click();
 await expect(page.locator('.transcript-entry.user').filter({hasText:'SaaS'})).toBeInViewport();
 await page.screenshot({path:'../.local/screenshots/match-desktop.png',fullPage:true});
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Transkript als Text'}).click();
 expect((await download).suggestedFilename()).toMatch(/transkript-.*\.txt/);
 // Clear only this isolated test server's preferences for repeatable tests.
 const config=await (await page.request.get('/api/admin/config')).json();config.match_profile.rules=[];
 expect((await page.request.put('/api/admin/config',{data:config,headers:{'X-Requested-With':'founder-app'}})).ok()).toBeTruthy();
});
