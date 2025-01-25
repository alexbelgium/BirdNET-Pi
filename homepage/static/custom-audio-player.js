function initCustomAudioPlayers(){
  // ---------------- Configuration ----------------
  const CONFIG = { LEFT_MARGIN_PERCENT: 6, RIGHT_MARGIN_PERCENT: 9, PROGRESS_INTERVAL: 50 };

  const icons = {
    play: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="white"><path d="M8 5v14l11-7z"/></svg>`,
    pause: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="white"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`,
    dots: `<svg width="24" height="24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M12 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 22a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/></svg>`
  };

  // Options with their numeric multipliers
  const gainOptions = ["OPROGRESS_BAR_UPDATE_INTERVALff","x2","x4","x8","x16"];
  const gainValues = {Off:1,x2:2,x4:4,x8:8,x16:16};
  const filterOptions = ["Off","250","500","1000"];

  // Safe localStorage helpers
  const safeGet = (key, fb) => { try{ return localStorage.getItem(key) || fb; } catch(_){ return fb; } };
  const safeSet = (key,val)=> { try{ localStorage.setItem(key,val); } catch(_){} };
  const savedGain = safeGet("customAudioPlayerGain","Off");
  const savedFilter = safeGet("customAudioPlayerFilter","Off");

  // Helper: apply multiple style properties at once
  const applyStyles = (elem,styles) => Object.assign(elem.style, styles);

  // Helper: create a reusable button with text or HTML
  function createButton(parent,{ text="", html="", styles={}, data={}, onClick=null }){
    const b=document.createElement("button");
    b.type="button";
    if(text) b.textContent = text;
    if(html) b.innerHTML = html;
    // Assign styles
    applyStyles(b, styles);
    // Simple hover effect inline
    b.addEventListener("mouseover", () => (b.style.background = "rgba(255,255,255,0.2)"));
    b.addEventListener("mouseout",  () => (b.style.background = "none"));
    // Data attributes if needed
    Object.entries(data).forEach(([k,v]) => { b.dataset[k] = v; });
    // Click event
    if(onClick) b.addEventListener("click", onClick);
    parent.appendChild(b);
    return b;
  }

  // ---------------- Main player initialization ----------------
  document.querySelectorAll(".custom-audio-player").forEach(player=>{
    // 1. Collect basic data from attributes
    const audioSrc = player.dataset.audioSrc;
    const imgSrc   = player.dataset.imageSrc;

    // 2. Create and append audio element
    const audioEl = document.createElement("audio");
    audioEl.src = audioSrc;
    audioEl.preload = "metadata";
    // External volume control calls for livestream (if used)
    audioEl.setAttribute("onplay","setLiveStreamVolume(0)");
    audioEl.setAttribute("onended","setLiveStreamVolume(1)");
    audioEl.setAttribute("onpause","setLiveStreamVolume(1)");
    player.appendChild(audioEl);

    // 3. Main wrapper + background image
    const wrapper = document.createElement("div");
    applyStyles(wrapper,{ position:"relative" });
    player.appendChild(wrapper);

    const img = document.createElement("img");
    img.src = imgSrc;
    applyStyles(img,{ width:"100%", borderRadius:"8px" });
    wrapper.appendChild(img);

    // 4. Progress indicator (vertical line over the image)
    const indicator = document.createElement("div");
    applyStyles(indicator,{
      position:"absolute", top:"0", bottom:"5%",
      left: CONFIG.LEFT_MARGIN_PERCENT+"%", width:"2px",
      background:"black", pointerEvents:"none", borderRadius:"2px"
    });
    wrapper.appendChild(indicator);

    // 5. Overlay (bottom bar) for play, progress, menu
    const overlay = document.createElement("div");
    applyStyles(overlay,{
      position:"absolute", left:"0", bottom:"0",
      width:"100%", height:"14.6%", display:"flex",
      alignItems:"center", justifyContent:"space-between",
      padding:"0 10px", borderRadius:"0 0 8px 8px",
      background:"rgba(0,0,0,0.3)", backdropFilter:"blur(1px)",
      visibility:"visible"
    });
    wrapper.appendChild(overlay);

    // ---- Web Audio chain references ----
    let audioCtx=null, sourceNode=null, gainNode=null, filterNode=null;

    // ---- Track active user selections for gain/filter ----
    let activeGain = gainOptions.includes(savedGain) ? savedGain : "Off";
    let activeFilter = filterOptions.includes(savedFilter) ? savedFilter : "Off";

    // Create or resume an AudioContext on demand
    async function initAudioContext(){
      if(!audioCtx){
        // Make new AudioContext
        audioCtx = new (window.AudioContext||window.webkitAudioContext)();
        sourceNode = audioCtx.createMediaElementSource(audioEl);
        gainNode = audioCtx.createGain();
        gainNode.gain.value = 1;
        sourceNode.connect(gainNode).connect(audioCtx.destination);
      }
      // Resume if suspended (auto-play policies, etc.)
      if(audioCtx.state==="suspended") await audioCtx.resume();
    }

    // Reconnect nodes if filter changes
    function rebuildAudioChain(){
      if(!audioCtx) return;
      sourceNode.disconnect(); 
      gainNode.disconnect(); 
      if(filterNode) filterNode.disconnect();
      // If we have a filterNode, chain: source -> filter -> gain -> destination
      // If not, just source -> gain -> destination
      if(filterNode) sourceNode.connect(filterNode).connect(gainNode);
      else           sourceNode.connect(gainNode);
      gainNode.connect(audioCtx.destination);
    }

    // -------- Gain setting function --------
    async function setActiveGain(val){
      activeGain = val;
      if(val!=="Off"){
        await initAudioContext();
        gainNode.gain.value = gainValues[val];
      } else if(gainNode) {
        gainNode.gain.value=1;
      }
      // Update underline in the menu for the selected option
      gainButtons.forEach(b => {
        b.style.textDecoration = (b.dataset.gain===val)?"underline":"none";
      });
      safeSet("customAudioPlayerGain", val);
    }

    // -------- HighPass filter setting function --------
    async function setActiveFilter(val){
      activeFilter = val;
      if(val!=="Off"){
        await initAudioContext();
        if(!filterNode){
          filterNode = audioCtx.createBiquadFilter();
          filterNode.type="highpass";
        }
        filterNode.frequency.value = parseFloat(val);
      } else if(filterNode){
        filterNode.disconnect();
        filterNode = null;
      }
      rebuildAudioChain();
      filterButtons.forEach(b=>{
        b.style.textDecoration = (b.dataset.filter===val)?"underline":"none";
      });
      safeSet("customAudioPlayerFilter", val);
    }

    // 6. Create play/pause button
    const playBtn = createButton(overlay, {
      html: icons.play,
      styles:{
        background:"none",border:"none",cursor:"pointer",
        width:"36px",height:"36px",display:"flex",
        alignItems:"center",justifyContent:"center",
        marginRight:"0.6rem",padding:"0"
      },
      onClick: async()=>{
        await initAudioContext();
        audioEl.paused ? audioEl.play() : audioEl.pause();
      }
    });

    // 7. Create progress bar (range input)
    const progress = document.createElement("input");
    Object.assign(progress,{ type:"range", value:0, min:0, max:100 });
    applyStyles(progress,{ flex:"1", margin:"0 0.5rem" });
    overlay.appendChild(progress);

    // 8. Menu "dots" button
    const dotsBtn = createButton(overlay, {
      html: icons.dots,
      styles:{
        background:"none",border:"none",cursor:"pointer",
        width:"36px",height:"36px",display:"flex",
        alignItems:"center",justifyContent:"center",
        marginRight:"0.6rem",padding:"0"
      }
    });

    // 9. Menu container
    const menu = document.createElement("div");
    applyStyles(menu,{
      position:"absolute", right:"10px", bottom:"15%",
      background:"rgba(0,0,0,0.3)", backdropFilter:"blur(8px)",
      color:"white", borderRadius:"6px", padding:"0.5rem",
      visibility:"hidden", display:"flex", flexDirection:"column",
      alignItems:"flex-end", minWidth:"160px"
    });
    wrapper.appendChild(menu);

    let menuOpen=false;
    dotsBtn.addEventListener("click", e=>{
      e.stopPropagation();
      menuOpen=!menuOpen;
      menu.style.visibility=menuOpen?"visible":"hidden";
    });
    document.addEventListener("click", e=>{
      // close if clicked outside the menu
      if(!menu.contains(e.target) && e.target!==dotsBtn){
        menuOpen=false; menu.style.visibility="hidden";
      }
    });

    // 10. Info button
    createButton(menu, {
      text:"Info",
      styles:{
        background:"none",border:"none",cursor:"pointer",
        color:"white",fontSize:"14px",textAlign:"right",
        width:"100%",padding:"6px 12px",margin:"2px 0",borderRadius:"4px"
      },
      onClick: async()=>{
        // Attempt to fetch HEAD for size and type
        let size="unknown",enc="unknown",sampleRate="unknown",channels="unknown";
        try{
          const headResp=await fetch(audioSrc,{method:"HEAD"});
          if(headResp.ok){
            const cl=headResp.headers.get("content-length");
            const ct=headResp.headers.get("content-type");
            if(cl){
              const kb=parseInt(cl,10)/1024;
              size=(kb>=1024)?(kb/1024).toFixed(2)+" MB":kb.toFixed(2)+" KB";
            }
            if(ct) enc=ct.split("/")[1]?.toUpperCase()||"unknown";
          }
          // Fetch entire file to decode (to get sample rate/channels)
          const audioData=await fetch(audioSrc).then(r=>r.arrayBuffer());
          const decCtx=new (window.AudioContext||window.webkitAudioContext)();
          const decoded=await decCtx.decodeAudioData(audioData);
          sampleRate=decoded.sampleRate; channels=decoded.numberOfChannels;
        }catch(_){}
        const dur = audioEl.duration?audioEl.duration.toFixed(2)+" s":"unknown";
        alert(`Duration: ${dur}
Type: ${enc}
Size: ${size}
Sampling Rate: ${sampleRate} Hz
Channels: ${channels}`);
        menuOpen=false; menu.style.visibility="hidden";
      }
    });

    // 11. Download button
    createButton(menu, {
      text:"Download",
      styles:{
        background:"none",border:"none",cursor:"pointer",
        color:"white",fontSize:"14px",textAlign:"right",
        width:"100%",padding:"6px 12px",margin:"2px 0",borderRadius:"4px"
      },
      onClick: async()=>{
        try{
          const blob=await fetch(audioSrc).then(r=>r.blob());
          const url=URL.createObjectURL(blob);
          const a=document.createElement("a");
          a.href=url;
          a.download=audioSrc.split("/").pop() || "audio_file";
          document.body.appendChild(a); a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }catch(_){ alert("Failed to download audio."); }
        menuOpen=false; menu.style.visibility="hidden";
      }
    });

    // 12. Helper function to create a sub-section (Gain / Filter)
    function createOptionSection(labelText){
      const c=document.createElement("div");
      applyStyles(c,{
        display:"flex",alignItems:"center",padding:"4px 0",
        borderTop:"1px solid rgba(255,255,255,0.2)",width:"100%",
        justifyContent:"flex-end",flexWrap:"wrap"
      });
      const lbl=document.createElement("div");
      lbl.textContent=labelText;
      applyStyles(lbl,{marginRight:"8px",fontSize:"14px",color:"#ccc",flexShrink:"0"});
      c.appendChild(lbl); menu.appendChild(c);
      return c;
    }

    // 13. Gain & Filter option sections
    const gainSection   = createOptionSection("Gain:");
    const filterSection = createOptionSection("HighPass (Hz):");

    // 14. Create gain buttons
    const gainButtons = gainOptions.map(opt =>
      createButton(gainSection,{
        text:opt,
        data:{gain:opt},
        styles:{
          background:"none",border:"none",cursor:"pointer",
          color:"white",fontSize:"14px",textAlign:"center",
          width:"auto",padding:"6px 8px",margin:"2px 4px",borderRadius:"4px"
        },
        onClick:()=>setActiveGain(opt)
      })
    );

    // 15. Create filter buttons
    const filterButtons = filterOptions.map(opt =>
      createButton(filterSection,{
        text:opt,
        data:{filter:opt},
        styles:{
          background:"none",border:"none",cursor:"pointer",
          color:"white",fontSize:"14px",textAlign:"center",
          width:"auto",padding:"6px 8px",margin:"2px 4px",borderRadius:"4px"
        },
        onClick:()=>setActiveFilter(opt)
      })
    );

    // Initialize gain/filter from saved values or default
    setActiveGain(activeGain);
    setActiveFilter(activeFilter);

    // ---------------- Progress tracking w/ setInterval ----------------
    let intervalId=null; // store reference to the setInterval

    function updateProgress(){
      if(!audioEl.duration)return;
      const frac = audioEl.currentTime / audioEl.duration;
      const pc = frac*100;
      progress.value = pc;
      const widthFactor = 100 - CONFIG.LEFT_MARGIN_PERCENT - CONFIG.RIGHT_MARGIN_PERCENT;
      indicator.style.left = CONFIG.LEFT_MARGIN_PERCENT + (pc*widthFactor/100) + "%";
    }
    function clearProgressInterval(){
      if(intervalId){ clearInterval(intervalId); intervalId=null; }
    }

    // ---- Audio events ----
    audioEl.addEventListener("play", ()=>{
      overlay.style.visibility="hidden";
      playBtn.innerHTML=icons.pause;
      intervalId=setInterval(updateProgress,CONFIG.PROGRESS_INTERVAL);
    });
    audioEl.addEventListener("pause", ()=>{
      overlay.style.visibility="visible";
      playBtn.innerHTML=icons.play;
      clearProgressInterval();
    });
    audioEl.addEventListener("ended", ()=>{
      clearProgressInterval();
      // optionally reset or show overlay
      overlay.style.visibility="visible";
      playBtn.innerHTML=icons.play;
    });

    // -- Manual seeking via progress bar --
    progress.addEventListener("input", ()=>{
      if(!audioEl.duration)return;
      audioEl.currentTime = (progress.value/100)*audioEl.duration;
      updateProgress();
    });

    // -- Clicking on the image to seek & play --
    wrapper.addEventListener("click", async e=>{
      // If clicking on menu or overlay, ignore
      if(menu.style.visibility==="visible" || overlay.contains(e.target) || !audioEl.duration) return;
      await initAudioContext();
      const rect=wrapper.getBoundingClientRect();
      const x   = Math.max(0, Math.min(1, (e.clientX-rect.left)/rect.width));
      progress.value = x*100;
      audioEl.currentTime = x*audioEl.duration;
      updateProgress();
      audioEl.play();
    });

    // -- Overlay show/hide by hover or touch --
    player.addEventListener("mouseenter", ()=>{ overlay.style.visibility="visible"; });
    wrapper.addEventListener("mouseleave", ()=>{
      // Hide only if audio is playing
      if(!audioEl.paused) overlay.style.visibility="hidden";
    });
    wrapper.addEventListener("mousemove", ()=>{
      // Show if playing
      if(!audioEl.paused) overlay.style.visibility="visible";
    });
    document.addEventListener("touchstart",(ev)=>{
      // Show overlay if user touches inside wrapper
      overlay.style.visibility = wrapper.contains(ev.target)?"visible":"hidden";
    });
  });
}

// Initialize once DOM is ready
document.addEventListener("DOMContentLoaded", initCustomAudioPlayers);
