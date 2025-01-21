document.addEventListener("DOMContentLoaded", () => {
  const CONFIG = {
    LEFT_MARGIN_PERCENT: 6,
    RIGHT_MARGIN_PERCENT: 9,
    PROGRESS_BAR_UPDATE_INTERVAL: 20,
  };

  const applyStyles = (elem, styles) => Object.assign(elem.style, styles);

  const styleButton = (btn, styles) => {
    applyStyles(btn, styles);
    btn.addEventListener("mouseover", () => (btn.style.background = "rgba(255,255,255,0.2)"));
    btn.addEventListener("mouseout", () => (btn.style.background = "none"));
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
    // If localStorage is blocked, fallback to defaults
    savedGain = "Off";
    savedFilter = "Off";
  }
  console.log("Saved Gain:", savedGain, "Saved Filter:", savedFilter);

  document.querySelectorAll(".custom-audio-player").forEach((player) => {
    const audioSrc = player.dataset.audioSrc;
    const imageSrc = player.dataset.imageSrc;

    // =============== Create Audio Element ===============
    const audioEl = document.createElement("audio");
    audioEl.src = audioSrc;
    audioEl.preload = "metadata";
    player.appendChild(audioEl);

    // =============== Wrapper & Styles ===============
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
      width: "3px",
      background: "rgba(0,0,0,0.5)",
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
      background: "rgba(0,0,0,0.5)",
      backdropFilter: "blur(8px)",
      visibility: "hidden",
    });

    const playBtn = overlay.appendChild(document.createElement("button"));
    applyStyles(playBtn, {
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
    });
    playBtn.innerHTML = icons.play;

    const progress = overlay.appendChild(document.createElement("input"));
    progress.type = "range";
    progress.value = "0";
    progress.min = "0";
    progress.max = "100";
    applyStyles(progress, {
      flex: "1",
      margin: "0 0.5rem",
      verticalAlign: "middle",
    });

    const dotsBtn = overlay.appendChild(document.createElement("button"));
    applyStyles(dotsBtn, {
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
    });
    dotsBtn.innerHTML = icons.dots;

    // =============== Menu ===============
    const menu = wrapper.appendChild(document.createElement("div"));
    applyStyles(menu, {
      position: "absolute",
      right: "10px",
      bottom: "15%",
      background: "rgba(0,0,0,0.5)",
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
    const infoBtn = menu.appendChild(document.createElement("button"));
    infoBtn.textContent = "Info";
    styleButton(infoBtn, {
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
    });

    const dlBtn = menu.appendChild(document.createElement("button"));
    dlBtn.textContent = "Download";
    styleButton(dlBtn, {
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
    });

    // =============== Lazy AudioContext / Nodes ===============
    let audioCtx = null;
    let sourceNode = null;
    let gainNode = null;
    let filterNode = null;

    // Gain
    const gainOptions = ["Off", "x2", "x4", "x8"];
    const gainValues = { Off: 1, x2: 2, x4: 4, x8: 8 };
    let activeGain = gainOptions.includes(savedGain) ? savedGain : "Off";

    // Filter
    const filterOptions = ["Off", "250", "500", "1000"];
    let activeFilterOption = filterOptions.includes(savedFilter) ? savedFilter : "Off";

    // Create the container for Gains
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

    const gainButtons = [];
    gainOptions.forEach((opt) => {
      const b = gainContainer.appendChild(document.createElement("button"));
      b.textContent = opt;
      b.dataset.gain = opt;
      styleButton(b, {
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
      });
      b.addEventListener("click", () => setActiveGain(opt));
      gainButtons.push(b);
    });

    // Create the container for Filters
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

    const filterButtons = [];
    filterOptions.forEach((opt) => {
      const b = filterContainer.appendChild(document.createElement("button"));
      b.textContent = opt;
      b.dataset.filter = opt;
      styleButton(b, {
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
      });
      b.addEventListener("click", () => setActiveFilter(opt));
      filterButtons.push(b);
    });

    // AudioContext init
    function initAudioContext() {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        sourceNode = audioCtx.createMediaElementSource(audioEl);
        gainNode = audioCtx.createGain();
        gainNode.gain.value = gainValues[activeGain] || 1;
        // Connect default chain
        if (activeFilterOption !== "Off") {
          filterNode = audioCtx.createBiquadFilter();
          filterNode.type = "highpass";
          filterNode.frequency.value = parseFloat(activeFilterOption);
          sourceNode.connect(filterNode).connect(gainNode).connect(audioCtx.destination);
        } else {
          sourceNode.connect(gainNode).connect(audioCtx.destination);
        }
      }
    }

    function rebuildAudioChain() {
      if (!audioCtx) return;
      sourceNode.disconnect();
      gainNode.disconnect();
      if (filterNode) filterNode.disconnect();

      if (activeFilterOption !== "Off") {
        if (!filterNode) {
          filterNode = audioCtx.createBiquadFilter();
          filterNode.type = "highpass";
        }
        filterNode.frequency.value = parseFloat(activeFilterOption);
        sourceNode.connect(filterNode).connect(gainNode).connect(audioCtx.destination);
      } else {
        if (filterNode) {
          filterNode.disconnect();
          filterNode = null;
        }
        sourceNode.connect(gainNode).connect(audioCtx.destination);
      }
    }

    // GAIN
    function setActiveGain(key) {
      activeGain = key;
      if (activeGain !== "Off") {
        initAudioContext();
        gainNode.gain.value = gainValues[activeGain];
      } else if (audioCtx && gainNode) {
        // "Off" means no extra gain => set to 1
        gainNode.gain.value = 1;
      }
      // Update underline
      gainButtons.forEach((b) => {
        b.style.textDecoration = b.dataset.gain === activeGain ? "underline" : "none";
      });
      // Save in localStorage
      try {
        localStorage.setItem("customAudioPlayerGain", activeGain);
      } catch (e) {
        console.warn("Could not access localStorage:", e);
      }
      // Rebuild audio chain to apply changes
      rebuildAudioChain();
    }

    // FILTER
    function setActiveFilter(value) {
      activeFilterOption = value;
      if (activeFilterOption !== "Off") {
        initAudioContext();
        if (!filterNode) {
          filterNode = audioCtx.createBiquadFilter();
          filterNode.type = "highpass";
        }
        filterNode.frequency.value = parseFloat(activeFilterOption);
      } else {
        if (filterNode) {
          filterNode.disconnect();
          filterNode = null;
        }
      }
      // Update underline
      filterButtons.forEach((b) => {
        b.style.textDecoration = b.dataset.filter === activeFilterOption ? "underline" : "none";
      });
      // Save in localStorage
      try {
        localStorage.setItem("customAudioPlayerFilter", activeFilterOption);
      } catch (e) {
        console.warn("Could not access localStorage:", e);
      }
      // Rebuild audio chain to apply changes
      rebuildAudioChain();
    }

    // Helper to do underline for OFF if needed
    function underlineDefaults() {
      gainButtons.forEach((b) => {
        b.style.textDecoration = b.dataset.gain === activeGain ? "underline" : "none";
      });
      filterButtons.forEach((b) => {
        b.style.textDecoration = b.dataset.filter === activeFilterOption ? "underline" : "none";
      });
    }

    // If saved settings are not "Off", activate them. Otherwise underline "Off".
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

    // =============== Hover Show/Hide Overlay ===============
    wrapper.addEventListener("mouseenter", () => (overlay.style.visibility = "visible"));
    wrapper.addEventListener("mouseleave", () => (overlay.style.visibility = "hidden"));

    // =============== Play/Pause Button ===============
    playBtn.addEventListener("click", () => {
      initAudioContext(); // Initialize AudioContext within user interaction
      if (audioEl.paused) {
        audioEl.play();
      } else {
        audioEl.pause();
      }
    });
    audioEl.addEventListener("play", () => (playBtn.innerHTML = icons.pause));
    audioEl.addEventListener("pause", () => (playBtn.innerHTML = icons.play));

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
    wrapper.addEventListener("click", (e) => {
      // If menu is open or user clicked on controls, skip
      if (menu.style.visibility === "visible" || overlay.contains(e.target) || !audioEl.duration) {
        return;
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

    // =============== Download Handler ===============
    dlBtn.addEventListener("click", async () => {
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
    });

    // =============== Info Handler ===============
    infoBtn.addEventListener("click", async () => {
      let size = "unknown",
        enc = "unknown",
        sampleRate = "unknown",
        channels = "unknown",
        bitDepth = "unknown";
      try {
        // HEAD request for content-length and content-type
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

        // Optionally parse actual audio data for sampleRate, channels, etc.
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
    });
  });
});
