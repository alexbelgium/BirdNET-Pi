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

  document.querySelectorAll(".custom-audio-player").forEach((player) => {
    const audioSrc = player.dataset.audioSrc;
    const imageSrc = player.dataset.imageSrc;

    const audioEl = document.createElement("audio");
    audioEl.src = audioSrc;
    audioEl.preload = "metadata";
    player.appendChild(audioEl);

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

    const gainContainer = menu.appendChild(document.createElement("div"));
    applyStyles(gainContainer, {
      display: "flex",
      alignItems: "center",
      padding: "4px 0",
      borderTop: "1px solid rgba(255,255,255,0.2)",
      width: "100%",
      justifyContent: "flex-end",
    });

    const gainLabel = gainContainer.appendChild(document.createElement("div"));
    gainLabel.textContent = "Gain:";
    applyStyles(gainLabel, {
      marginRight: "8px",
      fontSize: "14px",
      color: "#cccccc",
      flexShrink: "0",
    });

    const gainOptions = ["Off", "x2", "x4", "x8"];
    const gainValues = { Off: 1, x2: 2, x4: 4, x8: 8 };
    let activeGain = "Off";
    let audioCtx, gainNode, sourceNode;

    const initGainContext = () => {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        sourceNode = audioCtx.createMediaElementSource(audioEl);
        gainNode = audioCtx.createGain();
        gainNode.gain.value = gainValues[activeGain];
        sourceNode.connect(gainNode).connect(audioCtx.destination);
      }
    };

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
        textAlign: "right",
        width: "100%",
        padding: "6px 12px",
        margin: "2px 0",
        borderRadius: "4px",
      });
      applyStyles(b, {
        marginRight: "6px",
        flex: "1",
        border: "none",
        padding: "6px 0",
        textAlign: "center",
      });
      b.addEventListener("click", () => setActiveGain(opt));
      gainButtons.push(b);
    });

    setActiveGain(activeGain);

    wrapper.addEventListener("mouseenter", () => (overlay.style.visibility = "visible"));
    wrapper.addEventListener("mouseleave", () => (overlay.style.visibility = "hidden"));

    playBtn.addEventListener("click", () => {
      audioEl.paused ? audioEl.play() : audioEl.pause();
    });
    audioEl.addEventListener("play", () => (playBtn.innerHTML = icons.pause));
    audioEl.addEventListener("pause", () => (playBtn.innerHTML = icons.play));

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

    progress.addEventListener("input", () => {
      if (!audioEl.duration) return;
      const frac = parseFloat(progress.value) / 100;
      audioEl.currentTime = frac * audioEl.duration;
      updateProgress();
    });

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

    infoBtn.addEventListener("click", async () => {
      let size = "unknown", enc = "unknown", sampleRate = "unknown", channels = "unknown", bitDepth = "unknown";
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
        const audioData = await fetch(audioSrc).then((r) => r.arrayBuffer());
        const decoded = await new (window.AudioContext || window.webkitAudioContext)().decodeAudioData(audioData);
        sampleRate = decoded.sampleRate;
        channels = decoded.numberOfChannels;
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
