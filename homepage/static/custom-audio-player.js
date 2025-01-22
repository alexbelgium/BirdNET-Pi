function initCustomAudioPlayers() {
  const CONFIG = {
    LEFT_MARGIN_PERCENT: 6,
    RIGHT_MARGIN_PERCENT: 9,
    PROGRESS_BAR_UPDATE_INTERVAL: 20,
  };

  const icons = {
    play: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="white" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>`,
    pause: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="white" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`,
    dots: `<svg width="24" height="24" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M12 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 22a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/></svg>`,
  };

  // Attempt to get saved settings from localStorage, fallback to "Off"
  let savedGain = "Off";
  let savedFilter = "Off";
  try {
    savedGain = localStorage.getItem("customAudioPlayerGain") || "Off";
    savedFilter = localStorage.getItem("customAudioPlayerFilter") || "Off";
  } catch (e) {
    savedGain = "Off";
    savedFilter = "Off";
  }

  // =============== Style Helpers ===============
  const applyStyles = (elem, styles) => Object.assign(elem.style, styles);

  // Buttons typically share these hover behaviors
  const styleButton = (btn, styles = {}) => {
    applyStyles(btn, styles);
    btn.addEventListener("mouseover", () => (btn.style.background = "rgba(255,255,255,0.2)"));
    btn.addEventListener("mouseout", () => (btn.style.background = "none"));
  };

  // Quick helper to create & style a button in one go
  const createButton = (parent, { 
    text = "", 
    html = "", 
    styles = {}, 
    data = {}, 
    onClick = null 
  } = {}) => {
    const btn = document.createElement("button");
    btn.type = "button";
    if (text) btn.textContent = text;
    if (html) btn.innerHTML = html;
    Object.entries(data).forEach(([k, v]) => (btn.dataset[k] = v));
    styleButton(btn, styles);
    if (onClick) {
      btn.addEventListener("click", onClick);
    }
    parent.appendChild(btn);
    return btn;
  };

  // Common icon button style
  const iconBtnStyle = {
    background: "none",
    border: "none",
    cursor: "pointer",
    width: "36px",
    height: "36px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "0",
    marginRight: "0.6rem",
  };

  // Common text button style
  const textBtnStyle = {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "white",
    fontSize: "14px",
    textAlign: "right",
    width: "100%",
    padding: "6px 12px",
    margin: "2px 0",
    borderRadius: "4px",
  };

  // Smaller option button style (for Gain/Filter buttons)
  const optionBtnStyle = {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "white",
    fontSize: "14px",
    textAlign: "center",
    width: "auto",
    padding: "6px 8px",
    margin: "2px 4px",
    borderRadius: "4px",
  };

  // =============== Main Query Selector ===============
  document.querySelectorAll(".custom-audio-player").forEach((player) => {
    const audioSrc = player.dataset.audioSrc;
    const imageSrc = player.dataset.imageSrc;

    // =============== Create Audio Element ===============
    const audioEl = document.createElement("audio");
    audioEl.src = audioSrc;
    audioEl.preload = "metadata";
    audioEl.setAttribute("onplay", "setLiveStreamVolume(0)");
    audioEl.setAttribute("onended", "setLiveStreamVolume(1)");
    audioEl.setAttribute("onpause", "setLiveStreamVolume(1)");
    player.appendChild(audioEl);

    // =============== Wrapper & Image ===============
    const wrapper = player.appendChild(document.createElement("div"));
    applyStyles(wrapper, { position: "relative" });

    const img = wrapper.appendChild(document.createElement("img"));
    img.src = imageSrc;
    applyStyles(img, { width: "100%", borderRadius: "8px" });

    const indicator = wrapper.appendChild(document.createElement("div"));
    applyStyles(indicator, {
      position: "absolute",
      top: "0",
      bottom: "5%",
      left: `${CONFIG.LEFT_MARGIN_PERCENT}%`,
      width: "2px",
      background: "rgba(0,0,0)",
      pointerEvents: "none",
      borderRadius: "2px",
    });

    const overlay = wrapper.appendChild(document.createElement("div"));
    applyStyles(overlay, {
      position: "absolute",
      left: "0",
      bottom: "0",
      width: "100%",
      height: "15%",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "0 10px",
      borderRadius: "0 0 8px 8px",
      background: "rgba(0,0,0,0.3)",
      backdropFilter: "blur(1px)",
      visibility: "visible",
    });

    // =============== Create Overlay Buttons & Progress ===============
    // Play/Pause
    const playBtn = createButton(overlay, {
      html: icons.play,
      styles: iconBtnStyle,
      onClick: async () => {
        if (audioCtx && audioCtx.state === "suspended") {
          await audioCtx.resume();
        }
        audioEl.paused ? audioEl.play() : audioEl.pause();
      },
    });

    // Progress bar
    const progress = document.createElement("input");
    progress.type = "range";
    progress.value = "0";
    progress.min = "0";
    progress.max = "100";
    applyStyles(progress, {
      flex: "1",
      margin: "0 0.5rem",
      verticalAlign: "middle",
    });
    overlay.appendChild(progress);

    // Dots (menu toggle)
    const dotsBtn = createButton(overlay, {
      html: icons.dots,
      styles: iconBtnStyle,
    });

    // =============== Menu ===============
    const menu = wrapper.appendChild(document.createElement("div"));
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
      minWidth: "160px",
    });

    // =============== Info & Download Buttons ===============
    const infoBtn = createButton(menu, {
      text: "Info",
      styles: textBtnStyle,
      onClick: async () => {
        let size = "unknown",
          enc = "unknown",
          sampleRate = "unknown",
          channels = "unknown",
          bitDepth = "unknown";
        try {
          const resp = await fetch(audioSrc, { method: "HEAD" });
          if (resp.ok) {
            const cl = resp.headers.get("content-length");
            if (cl) {
              const sizeKB = parseInt(cl, 10) / 1024;
              size =
                sizeKB >= 1024
                  ? `${(sizeKB / 1024).toFixed(2)} MB`
                  : `${sizeKB.toFixed(2)} KB`;
            }
            const ct = resp.headers.get("content-type");
            if (ct) enc = ct.split("/")[1]?.toUpperCase() || "unknown";
          }

          // Decode for more info
          const audioData = await fetch(audioSrc).then((r) => r.arrayBuffer());
          const decCtx = new (window.AudioContext || window.webkitAudioContext)();
          const decoded = await decCtx.decodeAudioData(audioData);
          sampleRate = decoded.sampleRate;
          channels = decoded.numberOfChannels;
          bitDepth = "16 bits"; // typical guess
        } catch {}
        const duration = audioEl.duration ? `${audioEl.duration.toFixed(2)} s` : "unknown";

        alert(`Duration: ${duration}
Type: ${enc}
Size: ${size}
Sampling Rate: ${sampleRate} Hz
Channels: ${channels}
Bit Depth: ${bitDepth}`);

        menuOpen = false;
        menu.style.visibility = "hidden";
      },
    });

    const dlBtn = createButton(menu, {
      text: "Download",
      styles: textBtnStyle,
      onClick: async () => {
        try {
          const blob = await fetch(audioSrc).then((r) => r.blob());
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = audioSrc.split("/").pop() || "audio_file";
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        } catch {
          alert("Failed to download audio.");
        }
      },
    });

    // =============== Lazy AudioContext / Nodes ===============
    let audioCtx = null;
    let sourceNode = null;
    let gainNode = null;
    let filterNode = null;

    // Gain
    const gainOptions = ["Off", "x2", "x4", "x8", "x16"];
    const gainValues = { Off: 1, x2: 2, x4: 4, x8: 8, x16:16 };
    let activeGain = gainOptions.includes(savedGain) ? savedGain : "Off";

    // Filter
    const filterOptions = ["Off", "250", "500", "1000"];
    let activeFilterOption = filterOptions.includes(savedFilter) ? savedFilter : "Off";

    // Create Gain Container
    const gainContainer = menu.appendChild(document.createElement("div"));
    applyStyles(gainContainer, {
      display: "flex",
      alignItems: "center",
      padding: "4px 0",
      borderTop: "1px solid rgba(255,255,255,0.2)",
      width: "100%",
      justifyContent: "flex-end",
      flexWrap: "wrap",
    });
    const gainLabel = gainContainer.appendChild(document.createElement("div"));
    gainLabel.textContent = "Gain:";
    applyStyles(gainLabel, {
      marginRight: "8px",
      fontSize: "14px",
      color: "#cccccc",
      flexShrink: "0",
    });

    // Create Filter Container
    const filterContainer = menu.appendChild(document.createElement("div"));
    applyStyles(filterContainer, {
      display: "flex",
      alignItems: "center",
      padding: "4px 0",
      borderTop: "1px solid rgba(255,255,255,0.2)",
      width: "100%",
      justifyContent: "flex-end",
      flexWrap: "wrap",
    });
    const filterLabel = filterContainer.appendChild(document.createElement("div"));
    filterLabel.textContent = "HighPass (Hz):";
    applyStyles(filterLabel, {
      marginRight: "8px",
      fontSize: "14px",
      color: "#cccccc",
      flexShrink: "0",
    });

    // Helper to initialize audio context
    function initAudioContext() {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        sourceNode = audioCtx.createMediaElementSource(audioEl);
        gainNode = audioCtx.createGain();
        gainNode.gain.value = 1; // default
        sourceNode.connect(gainNode).connect(audioCtx.destination);
      }
    }

    // Helper to re-wire filter node
    function rebuildAudioChain() {
      if (!audioCtx) return;
      sourceNode.disconnect();
      gainNode.disconnect();
      if (filterNode) filterNode.disconnect();

      if (filterNode) {
        sourceNode.connect(filterNode);
        filterNode.connect(gainNode);
      } else {
        sourceNode.connect(gainNode);
      }
      gainNode.connect(audioCtx.destination);
    }

    // Gain
    const setActiveGain = (key) => {
      activeGain = key;
      if (activeGain !== "Off") {
        initAudioContext();
        gainNode.gain.value = gainValues[activeGain];
      } else if (audioCtx) {
        gainNode.gain.value = 1;
      }
      gainButtons.forEach((b) => {
        b.style.textDecoration = (b.dataset.gain === activeGain) ? "underline" : "none";
      });
      try {
        localStorage.setItem("customAudioPlayerGain", activeGain);
      } catch(e) {}
    };

    // Filter
    const setActiveFilter = (value) => {
      activeFilterOption = value;
      if (activeFilterOption !== "Off") {
        initAudioContext();
        if (!filterNode) {
          filterNode = audioCtx.createBiquadFilter();
          filterNode.type = "highpass";
        }
        filterNode.frequency.value = parseFloat(activeFilterOption);
        rebuildAudioChain();
      } else {
        if (filterNode) {
          filterNode.disconnect();
          filterNode = null;
          rebuildAudioChain();
        }
      }
      filterButtons.forEach((b) => {
        b.style.textDecoration = (b.dataset.filter === activeFilterOption) ? "underline" : "none";
      });
      try {
        localStorage.setItem("customAudioPlayerFilter", activeFilterOption);
      } catch(e) {}
    };

    // Gain & Filter Buttons
    const gainButtons = gainOptions.map((opt) => 
      createButton(gainContainer, {
        text: opt,
        data: { gain: opt },
        styles: optionBtnStyle,
        onClick: () => setActiveGain(opt),
      })
    );
    const filterButtons = filterOptions.map((opt) =>
      createButton(filterContainer, {
        text: opt,
        data: { filter: opt },
        styles: optionBtnStyle,
        onClick: () => setActiveFilter(opt),
      })
    );

    // Underline the initially active options
    function underlineDefaults() {
      gainButtons.forEach((b) => {
        b.style.textDecoration = b.dataset.gain === activeGain ? "underline" : "none";
      });
      filterButtons.forEach((b) => {
        b.style.textDecoration = b.dataset.filter === activeFilterOption ? "underline" : "none";
      });
    }

    // Apply saved settings or "Off"
    if (activeGain !== "Off") {
      setActiveGain(activeGain);
    } else {
      underlineDefaults();
    }
    if (activeFilterOption !== "Off") {
      setActiveFilter(activeFilterOption);
    } else {
      underlineDefaults();
    }

    // =============== Play/Pause Listeners ===============
    audioEl.addEventListener("play", () => {
      overlay.style.visibility = "hidden"; // Hide overlay during playback
      playBtn.innerHTML = icons.pause;
    });
    audioEl.addEventListener("pause", () => {
      overlay.style.visibility = "visible"; // Show overlay when paused
      playBtn.innerHTML = icons.play;
    });

    // =============== Progress Bar ===============
    let intervalId = null;
    const updateProgress = () => {
      if (!audioEl.duration) return;
      const frac = audioEl.currentTime / audioEl.duration;
      const pc = frac * 100;
      progress.value = pc;
      const leftPos =
        CONFIG.LEFT_MARGIN_PERCENT +
        (pc * (100 - CONFIG.LEFT_MARGIN_PERCENT - CONFIG.RIGHT_MARGIN_PERCENT)) / 100;
      indicator.style.left = leftPos + "%";
    };

    audioEl.addEventListener("play", () => {
      intervalId = setInterval(updateProgress, CONFIG.PROGRESS_BAR_UPDATE_INTERVAL);
    });
    audioEl.addEventListener("pause", () => clearInterval(intervalId));
    audioEl.addEventListener("ended", () => clearInterval(intervalId));

    progress.addEventListener("input", () => {
      if (!audioEl.duration) return;
      const frac = parseFloat(progress.value) / 100;
      audioEl.currentTime = frac * audioEl.duration;
      updateProgress();
    });

    // =============== Click Seek on the Image ===============
    wrapper.addEventListener("click", async (e) => {
      // If menu is open or user clicked overlay elements, skip
      if (menu.style.visibility === "visible" || overlay.contains(e.target) || !audioEl.duration) {
        return;
      }
      // Resume AudioContext if suspended
      if (audioCtx && audioCtx.state === "suspended") {
        await audioCtx.resume();
      }
      const rect = wrapper.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const pc = Math.max(0, Math.min(1, x)) * 100;
      progress.value = pc;
      audioEl.currentTime = (pc / 100) * audioEl.duration;
      updateProgress();
      audioEl.play();
    });

    // =============== Menu Open/Close ===============
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

    // =============== Hover & Touch for Overlay ===============
    wrapper.addEventListener("mouseenter", () => (overlay.style.visibility = "visible"));
    wrapper.addEventListener("mouseleave", () => (overlay.style.visibility = "hidden"));

    document.addEventListener("touchstart", (event) => {
      if (!wrapper.contains(event.target)) {
        // Hide overlay if the touch is outside the wrapper
        overlay.style.visibility = "hidden";
      } else {
        // Show overlay if the touch is inside the wrapper
        overlay.style.visibility = "visible";
      }
    });
  });
}

// Run once at DOMContentLoaded
document.addEventListener("DOMContentLoaded", initCustomAudioPlayers);
