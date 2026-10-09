import {useEffect,useRef,useState} from 'react';
import {Headphones,Square} from 'lucide-react';

export function MicrophoneTest({disabled=false}:{disabled?:boolean}){
 const [state,setState]=useState<'idle'|'permission'|'testing'|'done'|'error'>('idle');
 const [level,setLevel]=useState(0),[heard,setHeard]=useState(false),[error,setError]=useState('');
 // A generation token also invalidates a permission request that resolves after cancellation.
 const cleanup=useRef<()=>void>(()=>{}),generation=useRef(0);
 useEffect(()=>()=>{++generation.current;cleanup.current();},[]);
 function stop(){++generation.current;cleanup.current();setLevel(0);setState('done');}
 async function begin(){
  const attempt=++generation.current;
  cleanup.current();setHeard(false);setLevel(0);setError('');setState('permission');
  let stream:MediaStream|undefined,context:AudioContext|undefined,source:MediaStreamAudioSourceNode|undefined;
  let frame=0,timer:ReturnType<typeof setTimeout>|undefined;
  // Use one cleanup path for stop, timeout, errors, and component unmount.
  const release=()=>{cancelAnimationFrame(frame);clearTimeout(timer);source?.disconnect();stream?.getTracks().forEach(t=>t.stop());if(context&&context.state!=='closed')void context.close().catch(()=>{});};
  cleanup.current=release;
  try{
   context=new AudioContext();
   await context.resume();
   // An earlier stop or unmount must not reactivate capture when an awaited operation finishes.
   if(attempt!==generation.current){release();return;}
   stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
   // An earlier stop or unmount must not reactivate capture when an awaited operation finishes.
   if(attempt!==generation.current){release();return;}
   const analyser=context.createAnalyser();analyser.fftSize=1024;
   source=context.createMediaStreamSource(stream);source.connect(analyser);
   // Deliberately no connection to speakers, recorder, or network.
   const samples=new Float32Array(analyser.fftSize);
   setState('testing');
   const update=()=>{
    if(attempt!==generation.current)return;
    analyser.getFloatTimeDomainData(samples);
    // RMS measures input energy, not speech recognition or microphone intelligibility.
    const rms=Math.sqrt(samples.reduce((sum,x)=>sum+x*x,0)/samples.length);
    setLevel(Math.min(100,Math.round(rms*500)));
    // Latch signal detection for the final result, even if the user is silent when the test ends.
    if(rms>0.01)setHeard(true);
    frame=requestAnimationFrame(update);
   };
   update();timer=setTimeout(stop,15000);
  }catch(e){
   release();
   if(attempt!==generation.current)return;
   setError(e instanceof Error?e.message:'Das Mikrofon konnte nicht geöffnet werden.');setState('error');
  }
 }
 const running=state==='testing'||state==='permission';
 return <div className="microphone-test">
  <button className="text-button" disabled={disabled&&!running} onClick={running?stop:begin}>
   {running?<Square size={15}/>:<Headphones size={15}/>}{running?'Mikrofontest beenden':'Mikrofon testen'}
  </button>
  {state!=='idle'&&<div className="microphone-panel">
   <p role="status">{state==='permission'?'Bitte erlaube den Mikrofonzugriff im Browser.':state==='testing'?'Sag kurz etwas – der Balken zeigt deinen Mikrofonpegel.':state==='done'?(heard?'Test beendet. Ein Audiosignal wurde erkannt. Du kannst das Interview starten.':'Kein Audiosignal erkannt. Prüfe dein Mikrofon und ob es stummgeschaltet ist.'):'Mikrofontest nicht möglich.'}</p>
   {state==='testing'&&<><div className="microphone-meter" role="meter" aria-label="Mikrofonpegel" aria-valuemin={0} aria-valuemax={100} aria-valuenow={level}><div style={{width:level+'%'}}/></div><span>{heard?'Audiosignal erkannt':'Noch kein Audiosignal erkannt'}</span></>}
   {state==='error'&&<p role="alert">{error}</p>}
   <small>{running?'Nur lokal: keine Übertragung oder Aufnahme. Der Test endet nach 15 Sekunden automatisch.':'Das Mikrofon ist für den Test freigegeben.'}</small>
  </div>}
 </div>;
}
