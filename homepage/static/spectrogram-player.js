document.addEventListener("DOMContentLoaded", () => {
  const CONFIG = {
    LEFT_MARGIN_PERCENT: 6,
    RIGHT_MARGIN_PERCENT: 9,
    PROGRESS_BAR_UPDATE_INTERVAL: 20,
  };

  // Helper: merges style objects into an element's style
  const applyStyles = (elem, styles) => {
    Object.assign(elem.style, styles);
  };

  // Helper: style for icon buttons
  const styleIconBtn = (btn) => {
    applyStyles(btn, {
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
  };

  // Helper: style for menu buttons
  const styleMenuBtn = (btn) => {
    applyStyles(btn, {
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
    btn.addEventListener("mouseover", () => (btn.style.background = "rgba(255,255,255,0.2)"));
    btn.addEventListener("mouseout", () => (btn.style.background = "none"));
  };

  // SVG icons
  const icons = {
    play: `
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="white" viewBox="0 0 24 24">
        <path d="M8 5v14l11-7z"/>
      </svg>
    `,
    pause: `
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="white" viewBox="0 0 24 24">
        <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
      </svg>
    `,
    dots: `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 14a2 2 0 1 0 0-4 
                 2 2 0 0 0 0 4zM12 22a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/>
      </svg>
    `,
  };

  // For each custom-audio-player:
  document.querySelectorAll(".custom-audio-player").forEach((player) => {
    const audioSrc = player.dataset.audioSrc;
    const imageSrc = player.dataset.imageSrc;

    // Create <audio>
    const audioEl = document.createElement("audio");
    audioEl.src = audioSrc;
    audioEl.preload = "metadata";
    player.appendChild(audioEl);

    // Main wrapper
    const wrapper = document.createElement("div");
    applyStyles(wrapper, { position: "relative" });
    player.appendChild(wrapper);

    // Spectrogram image
    const img = document.createElement("img");
    img.src = imageSrc;
    applyStyles(img, {
      width: "100%",
      borderRadius: "8px",
    });
    wrapper.appendChild(img);

    // Vertical indicator
    const indicator = document.createElement("div");
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
    wrapper.appendChild(indicator);

    // Controls overlay
    const overlay = document.createElement("div");
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
      WebkitBackdropFilter: "blur(8px)",
      visibility: "hidden",
    });
    wrapper.appendChild(overlay);

    // Play/Pause button
    const playBtn = document.createElement("button");
    styleIconBtn(playBtn);
    playBtn.innerHTML = icons.play;
    overlay.appendChild(playBtn);

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

    // 3-dots button
    const dotsBtn = document.createElement("button");
    styleIconBtn(dotsBtn);
    dotsBtn.innerHTML = icons.dots;
    overlay.appendChild(dotsBtn);

    // 3-dots menu container
    const menu = document.createElement("div");
    applyStyles(menu, {
      position: "absolute",
      right: "10px",
      bottom: "15%",
      background: "rgba(0,0,0,0.5)",
      backdropFilter: "blur(8px)",
      WebkitBackdropFilter: "blur(8px)",
      color: "white",
      borderRadius: "6px",
      padding: "0.5rem",
      visibility: "hidden",
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-end",
      minWidth: "160px",
    });
    wrapper.appendChild(menu);

    // Info button
    const infoBtn = document.createElement("button");
    infoBtn.textContent = "Info";
    styleMenuBtn(infoBtn);
    infoBtn.style.alignSelf = "flex-end";
    menu.appendChild(infoBtn);

    // Download button
    const dlBtn = document.createElement("button");
    dlBtn.textContent = "Download";
    styleMenuBtn(dlBtn);
    dlBtn.style.alignSelf = "flex-end";
    menu.appendChild(dlBtn);

    // Gain container
    const gainContainer = document.createElement("div");
    applyStyles(gainContainer, {
      display: "flex",
      alignItems: "center",
      padding: "4px 0",
      borderTop: "1px solid rgba(255,255,255,0.2)",
      width: "100%",
      justifyContent: "flex-end",
    });
    menu.appendChild(gainContainer);

    // Gain label
    const gainLabel = document.createElement("div");
    gainLabel.textContent = "Gain:";
    applyStyles(gainLabel, {
      marginRight: "8px",
      fontSize: "14px",
      color: "#cccccc",
      flexShrink: "0",
    });
    gainContainer.appendChild(gainLabel);

    // Gains
    const gainOptions = ["Off", "x2", "x4", "x8"];
    const gainValues = { Off: 1, x2: 2, x4: 4, x8: 8 };
    let activeGain = "Off";
    let audioCtx, gainNode, sourceNode;

    // Prepare gain context if needed
    const initGainContext = () => {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        sourceNode = audioCtx.createMediaElementSource(audioEl);
        gainNode = audioCtx.createGain();
        gainNode.gain.value = gainValues[activeGain];
        sourceNode.connect(gainNode).connect(audioCtx.destination);
      }
    };

    // Toggle gain style
    const setActiveGain = (key) => {
      if (key === activeGain) return;
      activeGain = key;
      initGainContext();
      gainNode.gain.value = gainValues[key] || 1;
      gainButtons.forEach((b) => {
        b.style.textDecoration = b.dataset.gain === key ? "underline" : "none";
        b.style.textDecorationColor = b.dataset.gain === key ? "white" : "";
      });
    };

    // Gain Buttons
    const gainButtons = [];
    gainOptions.forEach((opt) => {
      const b = document.createElement("button");
      b.textContent = opt;
      b.dataset.gain = opt;
      styleMenuBtn(b);
      applyStyles(b, {
        marginRight: "6px",
        flex: "1",
        border: "none",
        padding: "6px 0",
        textAlign: "center",
      });
      b.addEventListener("click", () => setActiveGain(opt));
      gainContainer.appendChild(b);
      gainButtons.push(b);
    });

    // Initialize gain
    setActiveGain(activeGain);

    // Overlay events
    wrapper.addEventListener("mouseenter", () => (overlay.style.visibility = "visible"));
    wrapper.addEventListener("mouseleave", () => (overlay.style.visibility = "hidden"));

    // Play/Pause logic
    playBtn.addEventListener("click", () => {
      audioEl.paused ? audioEl.play() : audioEl.pause();
    });
    audioEl.addEventListener("play", () => (playBtn.innerHTML = icons.pause));
    audioEl.addEventListener("pause", () => (playBtn.innerHTML = icons.play));

    // Progress updates
    let intervalId = null;
    const updateProgress = () => {
      if (!audioEl.duration) return;
      const frac = audioEl.currentTime / audioEl.duration;
      const pc = frac * 100;
      progress.value = pc;
      const leftPos = CONFIG.LEFT_MARGIN_PERCENT + (pc * (100 - CONFIG.LEFT_MARGIN_PERCENT - CONFIG.RIGHT_MARGIN_PERCENT)) / 100;
      indicator.style.left = leftPos + "%";
    };
    audioEl.addEventListener("play", () => {
      intervalId = setInterval(updateProgress, CONFIG.PROGRESS_BAR_UPDATE_INTERVAL);
    });
    audioEl.addEventListener("pause", () => clearInterval(intervalId));
    audioEl.addEventListener("ended", () => clearInterval(intervalId));

    // Progress bar seeking
    progress.addEventListener("input", () => {
      if (!audioEl.duration) return;
      const frac = parseFloat(progress.value) / 100;
      audioEl.currentTime = frac * audioEl.duration;
      updateProgress();
    });

    // Spectrogram click => seek + play
    wrapper.addEventListener("click", (e) => {
      if (menu.style.visibility === "visible" || overlay.contains(e.target) || !audioEl.duration) return;
      const rect = wrapper.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const pc = Math.max(0, Math.min(1, x)) * 100;
      progress.value = pc;
      audioEl.currentTime = (pc / 100) * audioEl.duration;
      updateProgress();
      audioEl.play();
    });

    // Menu toggle
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

    // Download
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

    // Info
    infoBtn.addEventListener("click", async () => {
      let size = "unknown", enc = "unknown", sampleRate = "unknown";
      let channels = "unknown", bitDepth = "unknown";
      try {
        const resp = await fetch(audioSrc, { method: "HEAD" });
        if (resp.ok) {
          const cl = resp.headers.get("content-length");
          if (cl) {
            const sizeKB = parseInt(cl, 10) / 1024;
            size = sizeKB >= 1024 ? `${(sizeKB / 1024).toFixed(2)} MB` : `${sizeKB.toFixed(2)} KB`;
          }
          const ct = resp.headers.get("content-type");
          if (ct) enc = ct.split("/")[1]?.toUpperCase() || "unknown";
        }
        // Decode audio data
        const audioData = await fetch(audioSrc).then((r) => r.arrayBuffer());
        const decoded = await new (window.AudioContext || window.webkitAudioContext)().decodeAudioData(audioData);
        sampleRate = decoded.sampleRate;
        channels = decoded.numberOfChannels;
        // Bit depth placeholder
        bitDepth = "16 bits";
      } catch {}
      const duration = audioEl.duration ? `${audioEl.duration.toFixed(2)} seconds` : "unknown";

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
