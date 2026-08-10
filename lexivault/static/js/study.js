function applyT(t){document.documentElement.setAttribute('data-theme',t);const i=document.getElementById('ti');if(i)i.textContent=t==='dark'?'🌙':'☀️';localStorage.setItem('lv_t',t);}
function togT(){applyT(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark');}
function speak(word,lang){if(window.LVPronunciation)return window.LVPronunciation.play(word,{language:lang,rate:.85});if(!('speechSynthesis' in window))return;window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(word);u.lang=lang==='ja'?'ja-JP':lang==='ko'?'ko-KR':'en-US';u.rate=.85;window.speechSynthesis.speak(u);}
function toast(msg,type='ok'){const t=document.createElement('div');t.className=`toast toast-${type}`;t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.classList.add('show'),10);setTimeout(()=>{t.classList.remove('show');setTimeout(()=>t.remove(),300);},2500);}
async function saveScore(game,did,score,dur){
  const r=await fetch('/api/save_score',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({game,deck_id:did,score,duration:dur})});
  const d=await r.json();return d.ok?d:{};
}
function shuffle(a){return [...a].sort(()=>Math.random()-.5);}
function getWrongs(words,correct,n=3){return shuffle(words.filter(w=>w.meaning!==correct.meaning)).slice(0,n);}
