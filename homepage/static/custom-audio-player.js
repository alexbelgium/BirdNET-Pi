function initCustomAudioPlayers() {
  // Configuration and Constants
  const CONFIG = { LEFT_MARGIN_PERCENT: 6, RIGHT_MARGIN_PERCENT: 9, PROGRESS_INTERVAL: 50 };
  const icons = {
    play: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="white"><path d="M8 5v14l11-7z"/></svg>`,
    pause: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="white"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`,
    dots: `<svg width="24" height="24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M12 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 22a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/></svg>`
  };
  const gainOptions = ["Off", "x2", "x4", "x8", "x16"];
  const gainValues = { Off: 1, x2: 2, x4: 4, x8: 8, x16: 16 };
  const highpassOptions = ["Off", "250", "500", "1000"];
  const lowpassOptions = ["Off", "2000", "4000", "8000"];

  // LocalStorage Helpers
  const safeGet = (key, fb) => { try { return localStorage.getItem(key) || fb; } catch (_) { return fb; } };
  const safeSet = (key, val) => { try { localStorage.setItem(key, val); } catch (_) { } };
  const savedGain = safeGet("customAudioPlayerGain", "Off");
  const savedLowpass = safeGet("customAudioPlayerLowpass", "Off");
  const savedHighpass = safeGet("customAudioPlayerHighpass", "Off");

  // Reusable Style Objects
  const ICON_BUTTON_STYLES = { /* ... existing styles ... */ };
  const MENU_OPTION_STYLES = { /* ... existing styles ... */ };
  const FILTER_BUTTON_STYLES = { /* ... existing styles ... */ };

  // Helper Functions
  const applyStyles = (elem, styles) => Object.assign(elem.style, styles);

  function createButton(parent, { text = "", html = "", styles = {}, data = {}, onClick = null }) {
    const b = document.createElement("button");
    b.type = "button";
    if (text) b.textContent = text;
    if (html) b.innerHTML = html;
    applyStyles(b, styles);
    b.addEventListener("mouseover", () => (b.style.background = "rgba(255,255,255,0.2)"));
    b.addEventListener("mouseout", () => (b.style.background = "none"));
    Object.entries(data).forEach(([k, v]) => { b.dataset[k] = v; });
    if (onClick) b.addEventListener("click", onClick);
    parent.appendChild(b);
    return b;
  }

  // Shared AudioContext
  let sharedAudioContext = null;
  async function getSharedAudioContext() {
    if (!sharedAudioContext) {
      sharedAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (sharedAudioContext.state === 'suspended') {
      await sharedAudioContext.resume();
    }
    return sharedAudioContext;
  }

  // Initialize Audio Players When They Enter Viewport
  const observerCallback = (entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const player = entry.target;
        initializePlayer(player);
        observer.unobserve(player);
      }
    });
  };

  const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
  };

  const observer = new IntersectionObserver(observerCallback, observerOptions);

  document.querySelectorAll(".custom-audio-player").forEach(player => {
    observer.observe(player);
  });

  // Function to Initialize a Single Player
  async function initializePlayer(player) {
    const audioSrc = player.dataset.audioSrc;
    const imgSrc = player.dataset.imageSrc;

    // Create Audio Element
    const audioEl = document.createElement("audio");
    audioEl.src = audioSrc;
    audioEl.preload = "metadata";
    player.appendChild(audioEl);

    // Create and Connect Audio Nodes
    const audioCtx = await getSharedAudioContext();
    const sourceNode = audioCtx.createMediaElementSource(audioEl);
    const gainNode = audioCtx.createGain();
    gainNode.gain.value = 1;
    sourceNode.connect(gainNode).connect(audioCtx.destination);

    // Create Player UI
    const wrapper = document.createElement("div");
    applyStyles(wrapper, { position: "relative" });
    player.appendChild(wrapper);

    const img = document.createElement("img");
    img.src = imgSrc;
    applyStyles(img, { width: "100%", borderRadius: "8px" });
    wrapper.appendChild(img);

    // Progress Indicator
    const indicator = document.createElement("div");
    applyStyles(indicator, {
      position: "absolute",
      top: "0",
      bottom: "5%",
      left: `${CONFIG.LEFT_MARGIN_PERCENT}%`,
      width: "2px",
      background: "black",
      pointerEvents: "none",
      borderRadius: "2px"
    });
    wrapper.appendChild(indicator);

    // Overlay for Controls
    const overlay = document.createElement("div");
    applyStyles(overlay, {
      position: "absolute",
      left: "0",
      bottom: "0",
      width: "100%",
      height: "14.6%",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "0 10px",
      borderRadius: "0 0 8px 8px",
      background: "rgba(0,0,0,0.3)",
      backdropFilter: "blur(1px)",
      visibility: "visible"
    });
    wrapper.appendChild(overlay);

    // Create Play/Pause Button
    const playBtn = createButton(overlay, {
      html: icons.play,
      styles: ICON_BUTTON_STYLES,
      onClick: () => {
        if (audioEl.paused) {
          audioEl.play().catch(error => {
            console.error("Playback failed:", error);
          });
        } else {
          audioEl.pause();
        }
      }
    });

    // Create Progress Bar
    const progress = document.createElement("input");
    progress.type = "range";
    progress.value = 0;
    progress.min = 0;
    progress.max = 100;
    applyStyles(progress, { flex: "1", margin: "0 0.5rem" });
    overlay.appendChild(progress);

    // Create Menu Button
    const dotsBtn = createButton(overlay, {
      html: icons.dots,
      styles: ICON_BUTTON_STYLES
    });

    // Create Menu Container
    const menu = document.createElement("div");
    applyStyles(menu, {
      position: "absolute",
      right: "10px",
      bottom: "15%",
      background: "rgba(0,0,0,0.3)",
      backdropFilter: "blur(8px)",
      color: "white",
      borderRadius: "6px",
      padding: "0.5rem",
      visibility: "hidden",
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-end",
      minWidth: "160px"
    });
    wrapper.appendChild(menu);

    let menuOpen = false;
    dotsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      menuOpen = !menuOpen;
      menu.style.visibility = menuOpen ? "visible" : "hidden";
    });

    document.addEventListener("click", (e) => {
      if (!menu.contains(e.target) && e.target !== dotsBtn) {
        menuOpen = false;
        menu.style.visibility = "hidden";
      }
    });

    // Create Info Button
    createButton(menu, {
      text: "Info",
      styles: MENU_OPTION_STYLES,
      onClick: async () => {
        let size = "unknown", enc = "unknown", sampleRate = "unknown", channels = "unknown";
        try {
          const headResp = await fetch(audioSrc, { method: "HEAD" });
          if (headResp.ok) {
            const cl = headResp.headers.get("content-length");
            const ct = headResp.headers.get("content-type");
            if (cl) {
              const kb = parseInt(cl, 10) / 1024;
              size = (kb >= 1024) ? (kb / 1024).toFixed(2) + " MB" : kb.toFixed(2) + " KB";
            }
            if (ct) enc = ct.split("/")[1]?.toUpperCase() || "unknown";
          }
          const audioData = await fetch(audioSrc).then(r => r.arrayBuffer());
          const decCtx = new (window.AudioContext || window.webkitAudioContext)();
          const decoded = await decCtx.decodeAudioData(audioData);
          sampleRate = decoded.sampleRate;
          channels = decoded.numberOfChannels;
        } catch (_) { }
        const dur = audioEl.duration ? `${audioEl.duration.toFixed(2)} s` : "unknown";
        alert(`Duration: ${dur}\nType: ${enc}\nSize: ${size}\nSampling Rate: ${sampleRate} Hz\nChannels: ${channels}`);
        menuOpen = false;
        menu.style.visibility = "hidden";
      }
    });

    // Create Download Button
    createButton(menu, {
      text: "Download",
      styles: MENU_OPTION_STYLES,
      onClick: async () => {
        try {
          const blob = await fetch(audioSrc).then(r => r.blob());
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = audioSrc.split("/").pop() || "audio_file";
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        } catch (_) {
          alert("Failed to download audio.");
        }
        menuOpen = false;
        menu.style.visibility = "hidden";
      }
    });

    // Create Option Sections (Gain, HighPass, LowPass)
    function createOptionSection(labelText) {
      const section = document.createElement("div");
      applyStyles(section, {
        display: "flex",
        alignItems: "center",
        padding: "4px 0",
        borderTop: "1px solid rgba(255,255,255,0.2)",
        width: "100%",
        justifyContent: "flex-end",
        flexWrap: "wrap"
      });
      const label = document.createElement("div");
      label.textContent = labelText;
      applyStyles(label, { marginRight: "8px", fontSize: "14px", color: "#ccc", flexShrink: "0" });
      section.appendChild(label);
      menu.appendChild(section);
      return section;
    }

    const gainSection = createOptionSection("Gain:");
    const highpassSection = createOptionSection("HighPass (Hz):");
    const lowpassSection = createOptionSection("LowPass (Hz):");

    // Create Gain Buttons
    const gainButtons = gainOptions.map(opt =>
      createButton(gainSection, {
        text: opt,
        data: { gain: opt },
        styles: FILTER_BUTTON_STYLES,
        onClick: () => setActiveGain(opt)
      })
    );

    // Create LowPass Buttons
    const lowpassButtons = lowpassOptions.map(opt =>
      createButton(lowpassSection, {
        text: opt,
        data: { lowpass: opt },
        styles: FILTER_BUTTON_STYLES,
        onClick: () => setActiveLowpass(opt)
      })
    );

    // Create HighPass Buttons
    const highpassButtons = highpassOptions.map(opt =>
      createButton(highpassSection, {
        text: opt,
        data: { highpass: opt },
        styles: FILTER_BUTTON_STYLES,
        onClick: () => setActiveHighpass(opt)
      })
    );

    // Initialize Gain and Filters
    setActiveGain(savedGain);
    setActiveLowpass(savedLowpass);
    setActiveHighpass(savedHighpass);

    // Progress Tracking
    let intervalId = null;

    function updateProgress() {
      if (!audioEl.duration) return;
      const frac = audioEl.currentTime / audioEl.duration;
      const pc = frac * 100;
      progress.value = pc;
      const widthFactor = 100 - CONFIG.LEFT_MARGIN_PERCENT - CONFIG.RIGHT_MARGIN_PERCENT;
      indicator.style.left = `${CONFIG.LEFT_MARGIN_PERCENT + (pc * widthFactor / 100)}%`;
    }

    function clearProgressInterval() {
      if (intervalId) { clearInterval(intervalId); intervalId = null; }
    }

    // Audio Event Listeners
    audioEl.addEventListener("play", () => {
      overlay.style.visibility = "hidden";
      playBtn.innerHTML = icons.pause;
      intervalId = setInterval(updateProgress, CONFIG.PROGRESS_INTERVAL);
    });

    audioEl.addEventListener("pause", () => {
      overlay.style.visibility = "visible";
      playBtn.innerHTML = icons.play;
      clearProgressInterval();
    });

    audioEl.addEventListener("ended", () => {
      clearProgressInterval();
      overlay.style.visibility = "visible";
      playBtn.innerHTML = icons.play;
    });

    // Manual Seeking
    progress.addEventListener("input", () => {
      if (!audioEl.duration) return;
      audioEl.currentTime = (progress.value / 100) * audioEl.duration;
      updateProgress();
    });

    // Image Click to Seek & Play
    wrapper.addEventListener("click", async (e) => {
      if (menu.style.visibility === "visible" || overlay.contains(e.target) || !audioEl.duration) return;
      await getSharedAudioContext();
      const rect = wrapper.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      progress.value = x * 100;
      audioEl.currentTime = x * audioEl.duration;
      updateProgress();
      audioEl.play().catch(error => {
        console.error("Playback failed:", error);
      });
    });

    // Overlay Show/Hide
    player.addEventListener("mouseenter", () => { overlay.style.visibility = "visible"; });
    wrapper.addEventListener("mouseleave", () => {
      if (!audioEl.paused) overlay.style.visibility = "hidden";
    });
    wrapper.addEventListener("mousemove", () => {
      if (!audioEl.paused) overlay.style.visibility = "visible";
    });
    document.addEventListener("touchstart", (ev) => {
      overlay.style.visibility = wrapper.contains(ev.target) ? "visible" : "hidden";
    });

    // Gain Setting Function
    async function setActiveGain(val) {
      if (val !== "Off") {
        await getSharedAudioContext();
        gainNode.gain.value = gainValues[val];
      } else {
        gainNode.gain.value = 1;
      }
      gainButtons.forEach(b => {
        b.style.textDecoration = (b.dataset.gain === val) ? "underline" : "none";
      });
      safeSet("customAudioPlayerGain", val);
    }

    // HighPass Setting Function
    async function setActiveHighpass(val) {
      if (val !== "Off") {
        await getSharedAudioContext();
        if (!player.highpassNode) {
          player.highpassNode = audioCtx.createBiquadFilter();
          player.highpassNode.type = "highpass";
          sourceNode.connect(player.highpassNode).connect(gainNode);
        }
        player.highpassNode.frequency.value = parseFloat(val);
      } else {
        if (player.highpassNode) {
          sourceNode.disconnect(player.highpassNode);
          player.highpassNode.disconnect();
          player.highpassNode = null;
          sourceNode.connect(gainNode);
        }
      }
      highpassButtons.forEach(b => {
        b.style.textDecoration = (b.dataset.highpass === val) ? "underline" : "none";
      });
      safeSet("customAudioPlayerHighpass", val);
    }

    // LowPass Setting Function
    async function setActiveLowpass(val) {
      if (val !== "Off") {
        await getSharedAudioContext();
        if (!player.lowpassNode) {
          player.lowpassNode = audioCtx.createBiquadFilter();
          player.lowpassNode.type = "lowpass";
          sourceNode.connect(player.lowpassNode).connect(gainNode);
        }
        player.lowpassNode.frequency.value = parseFloat(val);
      } else {
        if (player.lowpassNode) {
          sourceNode.disconnect(player.lowpassNode);
          player.lowpassNode.disconnect();
          player.lowpassNode = null;
          sourceNode.connect(gainNode);
        }
      }
      lowpassButtons.forEach(b => {
        b.style.textDecoration = (b.dataset.lowpass === val) ? "underline" : "none";
      });
      safeSet("customAudioPlayerLowpass", val);
    }
  }
}

document.addEventListener("DOMContentLoaded", initCustomAudioPlayers);
