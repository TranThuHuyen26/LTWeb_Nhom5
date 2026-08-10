(function(){
  let currentAudio = null;

  function mapLangCode(lang){
    const raw = String(lang || 'en-US').trim();
    const low = raw.toLowerCase();
    if(!raw) return 'en-US';
    if(low === 'en' || low.startsWith('en-')) return raw.includes('-') ? raw : 'en-US';
    if(low === 'ja' || low.startsWith('ja-')) return raw.includes('-') ? raw : 'ja-JP';
    if(low === 'ko' || low.startsWith('ko-')) return raw.includes('-') ? raw : 'ko-KR';
    if(low === 'fr' || low.startsWith('fr-')) return raw.includes('-') ? raw : 'fr-FR';
    if(low === 'vi' || low.startsWith('vi-')) return raw.includes('-') ? raw : 'vi-VN';
    return raw.includes('-') ? raw : 'en-US';
  }

  function browserSpeak(text, lang, rate){
    const cleaned = String(text || '').trim();
    if(!cleaned || !('speechSynthesis' in window)) return Promise.resolve(false);
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(cleaned);
    u.lang = mapLangCode(lang);
    u.rate = typeof rate === 'number' ? rate : 0.88;
    return new Promise(resolve => {
      u.onend = () => resolve(true);
      u.onerror = () => resolve(false);
      window.speechSynthesis.speak(u);
    });
  }

  async function play(text, opts){
    const cleaned = String(text || '').trim();
    const options = opts || {};
    if(!cleaned) return false;
    const language = mapLangCode(options.language || options.language_code || options.lang || 'en-US');
    try{
      const r = await fetch('/api/pronounce', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          text: cleaned,
          ipa: options.ipa || '',
          language: language,
        })
      });
      const d = await r.json();
      if(r.ok && d.ok && d.audio_base64){
        if(currentAudio){
          currentAudio.pause();
          currentAudio.currentTime = 0;
        }
        currentAudio = new Audio(`data:${d.mime_type || 'audio/wav'};base64,${d.audio_base64}`);
        await currentAudio.play();
        return true;
      }
    } catch (e) {
      // Fall through to browser speech.
    }
    return browserSpeak(cleaned, language, options.rate);
  }

  window.LVPronunciation = {
    mapLangCode,
    browserSpeak,
    play,
    speak: play,
  };
})();
