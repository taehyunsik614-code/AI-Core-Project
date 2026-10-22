/* Pure state machines shared by the browser and node tests. */
(function(root){
'use strict';
class Timer {
  constructor(data={}){
    this.duration=Number.isFinite(data.duration)?Math.max(0,Math.min(86400,data.duration)):0;
    this.remaining=Number.isFinite(data.remaining)?Math.max(0,Math.min(86400,data.remaining)):this.duration;
    this.deadline=Number.isFinite(data.deadline)?data.deadline:null;
    this.running=!!data.running && this.deadline!==null;
    this.finished=!!data.finished;
  }
  left(now=Date.now()){return this.running?Math.max(0,(this.deadline-now)/1000):this.remaining;}
  set(seconds){this.duration=Math.max(0,Math.min(86400,Math.round(seconds)));this.remaining=this.duration;this.deadline=null;this.running=false;this.finished=false;}
  start(now=Date.now()){if(this.running || this.remaining<=0)return;this.deadline=now+this.remaining*1000;this.running=true;this.finished=false;}
  pause(now=Date.now()){if(!this.running)return;this.remaining=this.left(now);this.running=false;this.deadline=null;}
  reset(){this.set(this.duration);}
  adjust(delta,now=Date.now()){
    const seconds=Math.max(0,Math.min(86400,Math.round(this.left(now))+delta));
    this.set(seconds); // Editing always pauses, making the changed value reviewable.
  }
  tick(now=Date.now()){
    if(this.running && this.left(now)<=0){this.running=false;this.remaining=0;this.deadline=null;this.finished=true;return true;}
    return false;
  }
  snapshot(){return {duration:this.duration,remaining:this.remaining,deadline:this.deadline,running:this.running,finished:this.finished};}
}
class GestureGate {
  constructor(hold=850,release=300){this.hold=hold;this.release=release;this.reset();}
  reset(){this.candidate=null;this.since=0;this.latched=false;this.firedPose=null;this.neutralSince=null;this.last=null;}
  feed(name,score,now){
    // A stream interruption must never complete a hold.
    if(this.last!==null && now-this.last>650){this.candidate=null;this.since=now;}
    this.last=now;
    if(!name || name==='None' || score<0.65){
      this.candidate=null;
      if(this.neutralSince===null)this.neutralSince=now;
      if(now-this.neutralSince>=this.release)this.latched=false;
      return {event:null,progress:0};
    }
    this.neutralSince=null;
    if(this.latched && name===this.firedPose)return {event:null,progress:1};
    if(name!==this.candidate){this.candidate=name;this.since=now;}
    const progress=Math.min(1,(now-this.since)/this.hold);
    if(progress>=1){this.latched=true;this.firedPose=name;return {event:name,progress};}
    return {event:null,progress};
  }
}
// Match durations in generated and legacy recipe text. Separate actions are not summed.
function durationFromText(text){
  const pattern=/(\d+(?:\.\d+)?)\s*(?:[~～〜–-]\s*(\d+(?:\.\d+)?))?\s*(시간|hours?|hrs?|분|minutes?|mins?|초|seconds?|secs?)(?:\s*(반))?/gi;
  const matches=[...String(text||'').matchAll(pattern)];
  let total=0,previous=null,lastScale=0;
  for(const m of matches){
    const unit=m[3].toLowerCase(),scale=unit==='시간'||/^(hour|hr)/.test(unit)?3600:unit==='분'||unit.startsWith('min')?60:1;
    const value=Number(m[2]||m[1])*scale+(m[4]?scale/2:0);
    if(!previous)total=value;
    else{const gap=text.slice(previous.index+previous[0].length,m.index).trim();
      if(/^[~～〜–-]$/.test(gap))total=Math.max(total,value);
      else if(!gap&&scale<lastScale)total+=value;
      else break;
    }
    previous=m;lastScale=scale;
  }
  return Math.max(0,Math.min(86400,Math.round(total)));
}
function normalizeRecipe(value){
  if(!value||!Array.isArray(value.steps))return value;
  return {...value,steps:value.steps.map(step=>{
    if(!step||typeof step!=='object')return step;
    const seconds=durationFromText(step.instruction);
    const raw=typeof step.timer_seconds==='string'&&/^\d+$/.test(step.timer_seconds.trim())?Number(step.timer_seconds):step.timer_seconds;
    return {...step,timer_seconds:seconds||raw||0};
  })};
}
const timeText=s=>{s=Math.max(0,Math.ceil(s));const h=Math.floor(s/3600);return (h?h+':':'')+String(Math.floor(s/60)%60).padStart(2,'0')+':'+String(s%60).padStart(2,'0');};
const api={Timer,GestureGate,timeText,durationFromText,normalizeRecipe};
if(typeof module!=='undefined' && module.exports)module.exports=api;
else root.KitchenCore=api;
})(globalThis);
