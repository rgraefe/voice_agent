import {MicrophoneTest} from './MicrophoneTest';
import {GoalEditor,MatchEditor} from './GoalEditor';
import {InterviewReport} from './InterviewReport';
import {useEffect,useRef,useState} from 'react';
import {Room,RoomEvent,Track,ConnectionState} from 'livekit-client';
import {ArrowUpRight,ArrowRight,AudioLines,Check,CheckCircle2,ChevronRight,Clock3,Download,History as HistoryIcon,LogOut,Mic,MicOff,Play,Plus,Settings2,ShieldCheck,Square,Volume2,X,Copy,Radio,MessageSquare} from 'lucide-react';
import {api,date,statusLabel,type Bootstrap,type Config,type History,type Interview} from './api';

// Demo shortcuts only; the editable Voice-ID field still supports other provider voices.
const demoVoices = [
 {name:'Sarah',id:'EXAVITQu4vr4xnSDxMaL'},
 {name:'Bella',id:'hpp4J3VqNfWAUOO0d1Us'},
 {name:'Matilda',id:'XrExE9yKIg1WjnnlVkGX'},
 {name:'Jessica',id:'cgSgspJ2msm6clMCkdW9'},
];

function App(){
 const [boot,setBoot]=useState<Bootstrap|null>(null),[page,setPage]=useState('interview'),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [current,setCurrent]=useState<Interview|null>(null),[history,setHistory]=useState<History[]>([]),[config,setConfig]=useState<Config|null>(null);
 const [busy,setBusy]=useState(false),[password,setPassword]=useState(''),[invite,setInvite]=useState(''),[connection,setConnection]=useState('idle'),[muted,setMuted]=useState(false),[liveText,setLiveText]=useState(''),[agentSpeaking,setAgentSpeaking]=useState(false);
 const [simulationGoal,setSimulationGoal]=useState(''),[choice,setChoice]=useState(''),[number,setNumber]=useState('');
 const [agentReady,setAgentReady]=useState(false);
 const [text,setText]=useState(''),[vague,setVague]=useState(false),[previewBusy,setPreviewBusy]=useState(false),[previewError,setPreviewError]=useState('');
 const room=useRef<Room|null>(null),audioArea=useRef<HTMLDivElement>(null),bottom=useRef<HTMLDivElement>(null),closing=useRef(false),previewAudio=useRef<HTMLAudioElement|null>(null);
 const configFile=useRef<HTMLInputElement>(null);
 // Invalidate in-flight connection attempts when a session is stopped or reset.
 const connectionAttempt=useRef(0);
 const agentTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const previewURL=useRef(''),currentRef=useRef<Interview|null>(null);
 // Async event handlers can read the latest interview without capturing an outdated render.
 currentRef.current=current;
 const refresh=async()=>setBoot(await api<Bootstrap>('/bootstrap'));
 useEffect(()=>{refresh().catch(e=>setError(e.message));const params=new URLSearchParams(location.hash.slice(1));const token=params.get('invite');if(token){setInvite(token);historyReplace();}},[]);
 // Remove the invitation token from the address bar after reading it into local state.
 function historyReplace(){window.history.replaceState(null,'',location.pathname);}
 useEffect(()=>{if(!boot?.user)return;api<History[]>('/interviews').then(setHistory).catch(e=>setError(e.message));if(boot.user.role==='admin')api<Config>('/admin/config').then(setConfig).catch(e=>setError(e.message));},[boot?.user?.role,page]);
 // Persisted backend state drives the transcript and progress while a voice session is connected.
 useEffect(()=>{if(!current || connection==='idle')return;const timer=setInterval(()=>api<Interview>('/interviews/'+current.id).then(setCurrent).catch(e=>setError(e.message)),1500);return()=>clearInterval(timer);},[current?.id,connection]);
 useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[current?.transcript.length,liveText]);
 useEffect(()=>()=>{if(agentTimer.current)clearTimeout(agentTimer.current);room.current?.disconnect();previewAudio.current?.pause();if(previewURL.current)URL.revokeObjectURL(previewURL.current);},[]);
 // Centralize action state and user-facing errors; handlers supply the actual operation.
 const perform=async(fn:()=>Promise<void>)=>{setBusy(true);setError('');try{await fn();}catch(e){setError(e instanceof Error?e.message:'Etwas ist schiefgelaufen.');}finally{setBusy(false);}};
 async function login(body:unknown){await perform(async()=>{await api('/login','POST',body);await refresh();setPassword('');setInvite('');});}
 // Voice and simulation share persistence, but only voice creates a WebRTC connection.
 async function start(mode:'voice'|'simulation'){
  await perform(async()=>{
   const attempt=++connectionAttempt.current;
   closing.current=false;setAgentReady(false);setLiveText('');setMuted(false);setPage('interview');
   const item=await api<Interview>('/interviews','POST',{mode,request_id:crypto.randomUUID()});setCurrent(item);
   if(mode==='simulation'){setConnection('idle');return;}
   setConnection('connecting');
   try{
    const access=await api<{url:string;token:string}>('/interviews/'+item.id+'/connection','POST');
    if(attempt!==connectionAttempt.current)return;
    const r=new Room({adaptiveStream:true,dynacast:true,audioCaptureDefaults:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});room.current=r;
    r.on(RoomEvent.ParticipantConnected,p=>{if(p.isAgent){setAgentReady(true);if(agentTimer.current)clearTimeout(agentTimer.current);}});
    // Attach remote audio to browser playback; detach elements when tracks disappear.
    r.on(RoomEvent.TrackSubscribed,(track)=>{if(track.kind===Track.Kind.Audio){const audio=track.attach();audioArea.current?.appendChild(audio);}});
    r.on(RoomEvent.TrackUnsubscribed,(track)=>track.detach().forEach(el=>el.remove()));
    r.on(RoomEvent.ConnectionStateChanged,(state)=>setConnection(state===ConnectionState.Connected?'connected':state));
    r.on(RoomEvent.ActiveSpeakersChanged,(speakers)=>setAgentSpeaking(speakers.some(p=>p.identity!==r.localParticipant.identity)));
    // Show interim recognition separately; persisted transcript entries come from the backend.
    r.on(RoomEvent.TranscriptionReceived,(segments)=>{setLiveText(segments.filter(s=>!s.final).map(s=>s.text).join(' '));});
    r.on(RoomEvent.Disconnected,()=>{if(agentTimer.current)clearTimeout(agentTimer.current);setAgentReady(false);setConnection('idle');setAgentSpeaking(false);setLiveText('');audioArea.current?.replaceChildren();
     if(!closing.current){setNotice('Die Verbindung wurde beendet. Der bisherige Gesprächsverlauf bleibt erhalten.');api<Interview>('/interviews/'+item.id+'/stop','POST').then(setCurrent).catch(e=>setError(e.message));}});
    await r.connect(access.url,access.token);if(attempt!==connectionAttempt.current){await r.disconnect();return;}await r.startAudio();if(attempt!==connectionAttempt.current){await r.disconnect();return;}await r.localParticipant.setMicrophoneEnabled(true);if(attempt!==connectionAttempt.current){r.localParticipant.audioTrackPublications.forEach(p=>p.track?.stop());await r.disconnect();return;}
    if([...r.remoteParticipants.values()].some(p=>p.isAgent)){setAgentReady(true);}else{
     // Room connection alone does not prove a worker joined; bound the wait for the agent.
     agentTimer.current=setTimeout(()=>{if(![...r.remoteParticipants.values()].some(p=>p.isAgent)){
      setError('Der Voice-Agent ist nicht erreichbar. Bitte prüfen, ob der Worker läuft, und erneut starten.');
      closing.current=true;r.localParticipant.audioTrackPublications.forEach(p=>p.track?.stop());r.disconnect();room.current=null;setConnection('idle');
      api<Interview>('/interviews/'+item.id+'/stop','POST').then(setCurrent).catch(e=>setError(e.message));
     }},30000);
    }
   }catch(e){closing.current=true;await room.current?.disconnect();room.current=null;setConnection('idle');await api<Interview>('/interviews/'+item.id+'/stop','POST').then(setCurrent);throw e;}
  });
 }
 async function stop(){
  ++connectionAttempt.current;
  // Stop capture before any network request, including slow or failed persistence.
  if(agentTimer.current)clearTimeout(agentTimer.current);setAgentReady(false);closing.current=true;room.current?.localParticipant.audioTrackPublications.forEach(p=>p.track?.stop());await room.current?.disconnect();room.current=null;setConnection('idle');setMuted(false);setAgentSpeaking(false);setLiveText('');
  if(current)await perform(async()=>setCurrent(await api<Interview>('/interviews/'+current.id+'/stop','POST')));
 }
 // Reload after a confirmed stop to discard pending UI work without deleting saved history.
 async function resetDemo(){
  if(!boot?.local_demo)return;
  await perform(async()=>{
   ++connectionAttempt.current;closing.current=true;
   if(agentTimer.current)clearTimeout(agentTimer.current);
   room.current?.localParticipant.audioTrackPublications.forEach(p=>p.track?.stop());
   await room.current?.disconnect();room.current=null;
   audioArea.current?.replaceChildren();previewAudio.current?.pause();
   setConnection('idle');setAgentReady(false);setAgentSpeaking(false);setLiveText('');
   if(current&&['active','review'].includes(current.status))
    await api('/interviews/'+current.id+'/stop','POST');
   // A full reload disposes pending callbacks, polling, audio tests and all form state.
   // The login cookie remains; the next start creates a new interview and room.
   window.location.reload();
  });
 }
 async function mute(){await perform(async()=>{await room.current?.localParticipant.setMicrophoneEnabled(muted);setMuted(!muted);});}
 async function sendSimulation(confirm=false){if(!current)return;await perform(async()=>{setCurrent(await api<Interview>('/interviews/'+current.id+'/simulation-turn','POST',{id:crypto.randomUUID(),text:confirm?'Ja, die Zusammenfassung stimmt.':text,clear:!vague,confirm,...(!confirm&&current.planner_version===2?{goal_key:simulationGoal||current.current_goal,choice_value:choice||null,number_value:number===''?null:Number(number)}:{})}));setText('');setChoice('');setNumber('');setSimulationGoal('');});}
 // Validate the current draft before export; server credentials are outside the Config schema.
 async function saveConfig(){if(!config)return;await perform(async()=>{
  const validated=await api<Config>('/admin/config/validate','POST',config);
  const url=URL.createObjectURL(new Blob([JSON.stringify(validated,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='agent-konfiguration.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  setNotice('Konfiguration als Datei gespeichert. Nicht veröffentlichte Einstellungen sind enthalten.');
 });}
 // Imported files replace the form draft only; publishing is a separate explicit action.
 async function loadConfig(file:File){await perform(async()=>{
  if(file.size>1_000_000)throw new Error('Die Konfigurationsdatei darf höchstens 1 MB groß sein.');
  let data:unknown;try{data=JSON.parse(await file.text());}catch{throw new Error('Die Datei enthält kein gültiges JSON. Bitte eine gespeicherte Agent-Konfiguration wählen.');}
  const validated=await api<Config>('/admin/config/validate','POST',data);
  setConfig(validated);setPreviewError('');setNotice('Konfiguration als Entwurf geladen. Bitte prüfen und mit „Version veröffentlichen“ aktivieren.');
 });}
 async function publish(){if(!config)return;await perform(async()=>{setConfig(await api<Config>('/admin/config','PUT',config));await refresh();setNotice('Neue Konfiguration veröffentlicht. Laufende Interviews behalten ihre Version.');});}
 // Preview the unsaved voice settings and release previous audio URLs to avoid leaks.
 async function preview(){if(!config)return;setPreviewBusy(true);setPreviewError('');try{previewAudio.current?.pause();if(previewURL.current)URL.revokeObjectURL(previewURL.current);const res=await fetch('/api/admin/voice-preview',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'founder-app'},body:JSON.stringify(config)});if(!res.ok){const e=await res.json();throw new Error(e.error.message);}previewURL.current=URL.createObjectURL(await res.blob());previewAudio.current=new Audio(previewURL.current);await previewAudio.current.play();}catch(e){setPreviewError((e as Error).message);}finally{setPreviewBusy(false);}}
 async function exportResult(){if(!current)return;await perform(async()=>{const data=await api('/interviews/'+current.id+'/export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='startup-interview-'+current.id+'.json';a.click();URL.revokeObjectURL(url);});}
 const set=(key:keyof Config,value:unknown)=>setConfig(c=>c?({...c,[key]:value}):c);
 // Review is still an active session: the founder may correct or confirm the spoken summary.
 const active=!!current&&['active','review'].includes(current.status);
 const topics=current?.config.topics||boot?.topics||[];
 const completed=current?Object.values(current.topics).filter(t=>t.status==='clear').length:0;
 const controlsDisabled=busy||connection!=='idle'||active;
 if(!boot)return <div className="loading"><AudioLines size={32}/><p>Dein Gesprächsraum wird vorbereitet …</p>{error&&<p role="alert">{error}</p>}</div>;
 return <div className="app-shell">
  <aside className="sidebar"><a href="#" className="brand" onClick={e=>{e.preventDefault();setPage('interview');}}><span className="brand-icon"><AudioLines size={21}/></span>founder<span className="brand-light">studio</span></a>
   <div className="workspace-label">DEIN GESPRÄCHSRAUM</div><nav aria-label="Hauptnavigation">
    <button className={page==='interview'?'nav-item selected':'nav-item'} onClick={()=>setPage('interview')}><AudioLines size={19}/>Interview<span className="nav-dot"/></button>
    <button className={page==='history'?'nav-item selected':'nav-item'} onClick={()=>setPage('history')}><HistoryIcon size={19}/>Gesprächsverlauf</button>
    {current&&<button className={page==='results'?'nav-item selected':'nav-item'} onClick={()=>setPage('results')}><CheckCircle2 size={19}/>Auswertung & Transkript</button>}
    {boot.user?.role==='admin'&&<><div className="nav-divider"/><div className="workspace-label">VERWALTUNG</div><button className={page==='admin'?'nav-item selected':'nav-item'} onClick={()=>setPage('admin')}><Settings2 size={19}/>Agent konfigurieren</button></>}
   </nav><div className="sidebar-bottom"><div className="small-orb"/><h4>Raum für große Ideen.</h4><p>Ein gutes Gespräch ist der Anfang von etwas Neuem.</p><div className="sidebar-foot"><span className="green-dot"/>Founder Studio · v0.1</div></div>
  </aside>
  <div className="main-shell"><header className="topbar"><div className="breadcrumb">Workspace<ChevronRight size={14}/><strong>{page==='admin'?'Agent konfigurieren':page==='history'?'Gesprächsverlauf':page==='results'?'Auswertung & Transkript':'Startup-Interview'}</strong></div><div className="top-right"><span className="pill subtle">{boot.local_demo?'Lokale Entwicklung':'Interview-Plattform'}</span>{boot.user&&<><span className="avatar">{boot.user.role==='admin'?'A':'F'}</span><button className="icon-button" title="Abmelden" disabled={active||busy} onClick={()=>perform(async()=>{await api('/logout','POST');setCurrent(null);setConfig(null);setPage('interview');await refresh();})}><LogOut size={17}/></button></>}</div></header>
  <main>{error&&<div className="banner error" role="alert"><span>{error}</span><button aria-label="Fehler schließen" onClick={()=>setError('')}><X size={16}/></button></div>}{notice&&<div className="banner success" role="status"><span>{notice}</span><button aria-label="Hinweis schließen" onClick={()=>setNotice('')}><X size={16}/></button></div>}
  {!boot.user?<section className="welcome"><span className="eyebrow">GUTE IDEEN VERDIENEN EIN GUTES GESPRÄCH</span><h1>Dein Startup.<br/><em>Deine Geschichte.</em></h1><p>Ein erstes Kennenlernen mit {boot.agent.name}. Persönlich, strukturiert und ganz in deinem Tempo.</p><div className="login-card"><h3>{invite?'Dein Interview wartet auf dich':boot.local_demo?'Bereit für dein Startup-Interview?':'Willkommen im Founder Studio'}</h3>{boot.local_demo&&!invite&&<div className="demo-login"><p>Öffne deinen Gesprächsraum, teste dein Mikrofon und starte anschließend das Interview.</p><button className="primary" disabled={busy} onClick={()=>login({demo_role:'founder'})}>Zum Startup-Interview<ArrowRight size={16}/></button><span>Hier auf diesem Rechner brauchst du kein Konto. Dein Gespräch und das Ergebnis werden gespeichert.</span><button className="text-button" disabled={busy} onClick={()=>login({demo_role:'admin'})}>Admin-Bereich öffnen<ArrowUpRight size={14}/></button></div>}{!boot.local_demo&&!invite&&<p>Als Startup öffnest du deinen persönlichen Einladungslink. Diesen erhältst du vom Veranstalter. Das Passwortfeld ist nur für Administratoren.</p>}{(!boot.local_demo||invite)&&<form onSubmit={e=>{e.preventDefault();login(invite?{invite}:{password});}}><label>{invite?'Einladungscode':'Administrator-Passwort'}<input type={invite?'text':'password'} value={invite||password} onChange={e=>invite?setInvite(e.target.value):setPassword(e.target.value)} autoComplete="current-password" placeholder="Zugang eingeben"/></label><button className="primary" disabled={busy||(!password&&!invite)}>Anmelden<ArrowRight size={16}/></button></form>}</div></section>:
  page==='admin'&&config?<>
   <div className="page-heading"><div><span className="eyebrow">AGENT STUDIO</span><h1>Ein Gespräch mit Charakter.</h1><p>Bestimme, wie dein Agent klingt und was er erfahren soll.</p></div><button className="primary" disabled={busy} onClick={publish}>Version veröffentlichen<ArrowUpRight size={17}/></button></div>
   <div className="config-file-actions"><button className="secondary" disabled={busy} onClick={saveConfig}>Konfiguration speichern</button><button className="secondary" disabled={busy} onClick={()=>configFile.current?.click()}>Konfiguration laden</button><input ref={configFile} type="file" accept=".json,application/json" hidden aria-label="Konfigurationsdatei" onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file)void loadConfig(file);}}/><p>Speichert alle Agent-Einstellungen als Datei. Geladene Einstellungen werden erst mit „Version veröffentlichen“ aktiv.</p></div>
   <div className="admin-grid"><section className="card settings-card"><div className="section-top"><h2>Persönlichkeit & Stimme</h2><span className="pill">Version {config.version}</span></div><div className="field-grid"><label>Agentname<input value={config.name} maxLength={40} onChange={e=>set('name',e.target.value)}/></label><label>Sprache<select value={config.language} onChange={e=>set('language',e.target.value)}><option value="de">Deutsch</option><option value="en">Englisch</option></select></label><label>Tonalität<select value={config.tone} onChange={e=>set('tone',e.target.value)}><option value="warm">Warm & wertschätzend</option><option value="professional">Sachlich & professionell</option><option value="curious">Neugierig & offen</option></select></label><label>Maximale Dauer<select value={config.max_minutes} onChange={e=>set('max_minutes',+e.target.value)}>{[10,15,20,30,45].map(n=><option key={n} value={n}>{n} Minuten</option>)}</select></label></div>
   <div className="settings-separator"/><label>Stimme auswählen<select value={demoVoices.some(v=>v.id===config.voice_id)?config.voice_id:''} onChange={e=>{set('voice_id',e.target.value);setPreviewError('');}}><option value="">Eigene Voice-ID</option>{demoVoices.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select></label><label>ElevenLabs Voice-ID<input value={config.voice_id} onChange={e=>set('voice_id',e.target.value)} placeholder="Voice-ID aus deiner ElevenLabs-Bibliothek"/></label><label>Sprachmodell<select value={config.tts_model} onChange={e=>set('tts_model',e.target.value)}><option value="eleven_flash_v2_5">Flash v2.5 · schnelle Antworten</option><option value="eleven_turbo_v2_5">Turbo v2.5 · alternative Stimmqualität</option></select></label>
   {[['stability','Stimmstabilität',0,1,0.05],['similarity','Stimmähnlichkeit',0,1,0.05],['speed','Sprechtempo',0.7,1.2,0.05],['pause_seconds','Minimale Gesprächspause',0.3,2,0.1]].map(([key,title,min,max,step])=><label className="slider-label" key={key}><span>{title}<b>{Number(config[key as keyof Config]).toFixed(2)}{key==='pause_seconds'?' s':''}</b></span><input aria-label={String(title)} type="range" min={min} max={max} step={step} value={config[key as keyof Config] as number} onChange={e=>set(key as keyof Config,+e.target.value)}/></label>)}<p className="fine-print">Ausdrucksverstärkung ist für niedrige Latenz deaktiviert. Höhere Stabilität kann gleichmäßiger, aber auch monotoner klingen.</p><button className="secondary wide" disabled={previewBusy||!config.voice_id} onClick={preview}><Volume2 size={17}/>{previewBusy?'Hörprobe wird geladen …':'Stimme probehören'}</button>{previewError&&<p className="banner error" role="alert">{previewError}</p>}<p className="fine-print">Hörproben verwenden die echte ElevenLabs-API und sind kostenpflichtig.</p></section>
   <div><GoalEditor config={config} onChange={setConfig}/><MatchEditor config={config} onChange={setConfig}/>
   <section className="card settings-card setup"><h3>Verbindung & Zugang</h3><p>{boot.voice_ready?'Alle benötigten Zugangsdaten und eine Stimme sind konfiguriert. Der Voice Worker muss zusätzlich laufen.':'Für echte Voice-Gespräche fehlen noch:'}</p>{boot.missing.map(m=><code key={m}>{m}</code>)}<p className="fine-print">Schlüssel werden ausschließlich auf dem Server hinterlegt.</p><button className="secondary" disabled={busy} onClick={()=>perform(async()=>{const result=await api<{url:string}>('/admin/invites','POST');await navigator.clipboard.writeText(result.url);setNotice('Einladungslink kopiert. Er ist sieben Tage gültig.');})}><Copy size={16}/>Startup einladen</button></section></div></div>
  </>:page==='history'?<>
   <div className="page-heading"><div><span className="eyebrow">GESPRÄCHSVERLAUF</span><h1>Jede Idee hat eine Geschichte.</h1><p>{boot.user.role==='admin'?'Alle Interviews und ihre Ergebnisse im Überblick.':'Deine bisherigen Gespräche, an einem Ort.'}</p></div><button className="secondary" onClick={()=>setPage('interview')}><Plus size={17}/>Zum Interview</button></div><section className="card history-card">{history.length===0?<div className="empty-state"><HistoryIcon size={32}/><h3>Hier beginnt deine Geschichte.</h3><p>Nach deinem ersten Interview findest du hier den Verlauf und das Ergebnis.</p></div>:history.map(h=><button key={h.id} className="history-row" disabled={active||busy} onClick={()=>perform(async()=>{setCurrent(await api<Interview>('/interviews/'+h.id));setPage(['completed','incomplete'].includes(h.status)?'results':'interview');})}><span className="history-icon"><MessageSquare size={20}/></span><span className="history-title"><strong>{h.title}</strong><small>{date(h.created_at)} · {h.mode==='simulation'?'Text-Testlauf':'Voice-Interview'} · Version {h.config_version}</small></span><span className="pill subtle">{statusLabel[h.status]}</span><ChevronRight size={18}/></button>)}</section>{active&&<p className="fine-print">Beende das aktuelle Interview, bevor du ein anderes öffnest.</p>}
  </>:page==='results'&&current?<InterviewReport item={current}/>:<>
   <div className="page-heading"><div><span className="eyebrow">LET’S TALK ABOUT YOUR NEXT BIG THING</span><h1>Deine Idee. <em>Im Mittelpunkt.</em></h1><p>Nimm dir einen Moment. Wir hören zu und stellen die richtigen Fragen.</p></div><span className="pill session-pill"><Clock3 size={14}/>{boot.agent.max_minutes} Min. Zeitrahmen</span></div>
   <div className="interview-grid"><div className="interview-left"><section className="card voice-card"><div className="voice-card-top"><span className="pill"><span className={connection==='connected'?'green-dot':'grey-dot'}/>{connection==='connected'?(agentReady?'Live verbunden':'Agent wird vorbereitet'):connection!=='idle'?'Verbindung wird aufgebaut':current?statusLabel[current.status]:'Bereit, wenn du es bist'}</span><span className="mini-label">{current?.mode==='simulation'?'TEXT-TESTLAUF':'VOICE INTERVIEW'}</span></div>
   <div className={'orb-wrap '+(agentSpeaking?'speaking':'')}><div className="orb-ring ring-one"/><div className="orb-ring ring-two"/><div className="orb"><div className="orb-light"/><AudioLines size={55} strokeWidth={1.1}/></div><div className="orb-caption"><span className="green-dot"/>{current?.config.name||boot.agent.name} · Dein Interview-Agent</div></div>
   <h2>{agentSpeaking?'Ich bin ganz bei dir.':connection==='connected'?(!agentReady?'Dein Agent kommt gleich dazu.':muted?'Dein Mikrofon ist stumm.':'Erzähl mir von deiner Idee.'):current?.status==='completed'?'Danke für deine Geschichte.':current?.mode==='simulation'?'Ein Blick in den Gesprächsablauf.':'Große Ideen beginnen mit einem Hallo.'}</h2>
   <p className="voice-description">{current?.mode==='simulation'?'Lokale Simulation ohne KI und Sprachausgabe. Du steuerst, ob eine Antwort als konkret oder vage gilt.':connection==='connected'?'Sprich ganz natürlich. Du kannst jederzeit unterbrechen oder eine Angabe korrigieren.':'Teste zuerst dein Mikrofon. Klicke dann auf „Interview starten“ und erlaube den Mikrofonzugriff. '+boot.agent.name+' begrüßt dich und stellt die erste Frage.'}</p>
   <div className="voice-controls">{active?<><button className="secondary" disabled={busy||current?.mode==='simulation'||connection==='idle'} onClick={mute}>{muted?<MicOff size={18}/>:<Mic size={18}/>} {muted?'Mikrofon an':'Stummschalten'}</button><button className="stop-button" onClick={stop}><Square size={15} fill="currentColor"/>Gespräch beenden</button></>:<button className="primary start-button" disabled={controlsDisabled||!boot.voice_ready} onClick={()=>start('voice')}><Mic size={18}/>Interview starten<ArrowRight size={18}/></button>}</div>
   {!active&&!boot.voice_ready&&<p className="configuration-note">Voice ist noch nicht eingerichtet.{boot.user.role==='admin'&&<button className="inline-link" onClick={()=>setPage('admin')}>Zugänge konfigurieren<ArrowUpRight size={13}/></button>}</p>}
   {!active&&<div className="voice-secondary"><MicrophoneTest disabled={busy}/>{boot.local_demo&&<button className="text-button" disabled={busy} onClick={()=>start('simulation')}>Text-Testlauf<ArrowUpRight size={14}/></button>}</div>}
   <div className="privacy-note"><ShieldCheck size={15}/><span>Transkript & Ergebnis werden gespeichert. Keine Audioaufzeichnung durch diese App.</span></div></section>
   <section className="card transcript-card"><div className="section-top"><h2>Das Gespräch</h2><span className="pill subtle">{current?.transcript.length||0} Beiträge</span></div><div className="transcript" aria-live="polite">{!current?.transcript.length?<div className="empty-transcript"><MessageSquare size={25}/><p>Hier entsteht eure Unterhaltung.</p><small>Deine Aussagen und die Antworten des Agents erscheinen während des Gesprächs.</small></div>:current.transcript.map(t=><div className={'message '+t.role} key={t.id}><span className="message-avatar">{t.role==='assistant'?(current.config.name[0]||'M'):'Du'}</span><div><div className="message-meta"><strong>{t.role==='assistant'?current.config.name:'Du'}</strong><time>{new Date(t.timestamp).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}</time>{t.interrupted&&<small>unterbrochen</small>}</div><p>{t.text}</p></div></div>)}{liveText&&<p className="interim">{liveText} …</p>}<div ref={bottom}/></div>
   {active&&current?.mode==='simulation'&&<div className="simulation-input">{current.planner_version===2&&<><label>Antwortziel im Test<select value={simulationGoal||current.current_goal||''} onChange={e=>{setSimulationGoal(e.target.value);setChoice('');setNumber('');}}><option value="">Ziel auswählen …</option>{current.config.goals.filter(g=>g.enabled).map(g=><option key={g.key} value={g.key}>{g.label}</option>)}</select></label>{(()=>{const g=current.config.goals.find(g=>g.key===(simulationGoal||current.current_goal));return g?.kind==='choice'?<label>Zugeordnete Kategorie<select value={choice} onChange={e=>{setChoice(e.target.value);if(!text)setText(e.target.value);}}><option value="">Bitte wählen …</option>{g.choices.map(c=><option key={c}>{c}</option>)}</select></label>:g?.kind==='number'?<label>Zahlenwert in {g.unit}<input type="number" value={number} onChange={e=>setNumber(e.target.value)}/></label>:null;})()}</>}<label className="check-label"><input type="checkbox" checked={vague} onChange={e=>setVague(e.target.checked)}/>Antwort als vage testen</label><form onSubmit={e=>{e.preventDefault();sendSimulation();}}><input aria-label="Testantwort" placeholder="Deine Testantwort …" value={text} maxLength={1400} onChange={e=>setText(e.target.value)}/><button className="primary" disabled={busy||!text.trim()} aria-label="Testantwort senden"><ArrowRight size={18}/></button></form>{current.status==='review'&&<button className="secondary wide" disabled={busy} onClick={()=>sendSimulation(true)}><Check size={16}/>Zusammenfassung bestätigen</button>}</div>}
   </section></div>
   <aside className="interview-right"><section className="card agenda"><div className="section-top"><h2>Unser roter Faden</h2><span className="mini-label">{completed} / 7</span></div><p>Ein Kennenlernen, kein Fragebogen.<br/>Du gibst das Tempo vor.</p><div className="progress"><div style={{width:(completed/7*100)+'%'}}/></div><ol>{topics.map((t,i)=>{const state=current?.topics[t.key];return <li key={t.key} className={state?.status==='clear'?'done':current?.current_topic===t.key?'current':''}><span className="step-circle">{state?.status==='clear'?<Check size={14}/>:i+1}</span><div><strong>{t.title}</strong><small>{state?statusLabel[state.status]:['Eure Idee und für wen sie da ist','Die Menschen hinter der Vision','Was ihr baut und wo ihr steht','Was ihr schon erreicht habt','Euer Platz im Markt','Kapital für die nächsten Schritte','Wie es weitergeht'][i]}</small></div>{current?.current_topic===t.key&&<span className="green-dot"/>}</li>;})}</ol></section>
   {current&&<section className="card results"><div className="section-top"><h2>Startup-Profil</h2><button className="icon-button" title="Ergebnis als JSON herunterladen" onClick={exportResult}><Download size={16}/></button></div>{Object.entries(current.topics).filter(([,s])=>s.value).length?Object.entries(current.topics).filter(([,s])=>s.value).map(([k,s])=><div className="result-item" key={k}><small>{topics.find(t=>t.key===k)?.title}<span>{statusLabel[s.status]}</span></small><p>{s.value}</p></div>):<p className="muted">Aus euren Antworten entsteht hier Schritt für Schritt ein strukturiertes Bild.</p>}<button className="secondary wide" onClick={()=>setPage('results')}>Auswertung & Transkript ansehen</button><div className="fine-print">{date(current.created_at)} · Konfiguration v{current.config.version}</div></section>}
   <div className="tip"><span className="tip-icon"><AudioLines size={20}/></span><div><h4>Ganz du selbst.</h4><p>Du brauchst keinen perfekten Pitch. Denkpausen und spontane Gedanken gehören dazu.</p></div></div></aside></div>
  </>}
  {boot.user&&boot.local_demo&&<div className="demo-reset"><button className="secondary" disabled={busy} onClick={resetDemo}>Demo zurücksetzen</button><p>Beendet das aktuelle Gespräch und leert die Ansicht. Das nächste Interview startet ohne bisherigen Gesprächskontext. Gespeicherte Gespräche bleiben in der Historie.</p></div>}
  <footer><span>FOUNDER STUDIO</span><span>Gute Gespräche. Klare nächste Schritte.</span></footer></main></div><div ref={audioArea} className="audio-area"/></div>;
}
export default App;
