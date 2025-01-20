document.addEventListener("DOMContentLoaded", () => {
  const CONFIG = {
    LEFT_MARGIN_PERCENT: 6,
    RIGHT_MARGIN_PERCENT: 9,
    PROGRESS_BAR_UPDATE_INTERVAL: 20,
  };

  const audioPlayers = document.querySelectorAll(".custom-audio-player");

  audioPlayers.forEach((player) => {
    const audioSrc = player.dataset.audioSrc;
    const imageSrc = player.dataset.imageSrc;

    // Create audio
    const audioEl = document.createElement("audio");
    audioEl.src = audioSrc;
    audioEl.preload = "metadata";
    player.appendChild(audioEl);

    // Create wrapper + image
    const wrapper = document.createElement("div");
    wrapper.style.position = "relative";
    player.appendChild(wrapper);

    const img = document.createElement("img");
    img.src = imageSrc;
    img.style.width = "100%";
    img.style.borderRadius = "8px";
    wrapper.appendChild(img);

    // Vertical progress bar
    const indicator = document.createElement("div");
    Object.assign(indicator.style, {
      position: "absolute",
      top: "0",
      bottom: "5%", // slightly above bottom
      left: CONFIG.LEFT_MARGIN_PERCENT + "%",
      width: "3px",
      background: "rgba(0,0,0,0.5)",
      pointerEvents: "none",
      borderRadius: "2px",
    });
    wrapper.appendChild(indicator);

    // Controls overlay
    const overlay = document.createElement("div");
    Object.assign(overlay.style, {
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

    // Icons
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
          <path d="M12 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 22a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/>
        </svg>
      `,
    };

    // Helper: style an icon button
    const styleIconBtn = (btn) => {
      Object.assign(btn.style, {
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

    // Create controls
    const playBtn = document.createElement("button");
    styleIconBtn(playBtn);
    playBtn.innerHTML = icons.play;
    overlay.appendChild(playBtn);

    const progress = document.createElement("input");
    progress.type = "range";
    progress.min = "0";
    progress.max = "100";
    progress.value = "0";
    Object.assign(progress.style, {
      flex: "1",
      margin: "0 0.5rem",
      verticalAlign: "middle",
    });
    overlay.appendChild(progress);

    const dotsBtn = document.createElement("button");
    styleIconBtn(dotsBtn);
    dotsBtn.innerHTML = icons.dots;
    overlay.appendChild(dotsBtn);

    // Dots menu
    const menu = document.createElement("div");
    Object.assign(menu.style, {
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
      display: "inline-block",
    });
    wrapper.appendChild(menu);

    const styleMenuBtn = (btn) => {
      Object.assign(btn.style, {
        background: "none",
        border: "none",
        cursor: "pointer",
        color: "white",
        fontSize: "14px",
        textAlign: "left",
        width: "100%",
        padding: "6px 12px",
      });
      btn.addEventListener("mouseover", () => (btn.style.background = "rgba(255,255,255,0.2)"));
      btn.addEventListener("mouseout", () => (btn.style.background = "none"));
    };

    const dlBtn = document.createElement("button");
    dlBtn.textContent = "Download Audio";
    styleMenuBtn(dlBtn);
    menu.appendChild(dlBtn);

    const infoBtn = document.createElement("button");
    infoBtn.textContent = "Info";
    styleMenuBtn(infoBtn);
    menu.appendChild(infoBtn);

    // Toggle overlay
    wrapper.addEventListener("mouseenter", () => (overlay.style.visibility = "visible"));
    wrapper.addEventListener("mouseleave", () => (overlay.style.visibility = "hidden"));

    // Play/Pause
    playBtn.addEventListener("click", () => {
      audioEl.paused ? audioEl.play() : audioEl.pause();
    });
    audioEl.addEventListener("play", () => (playBtn.innerHTML = icons.pause));
    audioEl.addEventListener("pause", () => (playBtn.innerHTML = icons.play));

    // Update bar
    let intervalId = null;
    const updateProgress = () => {
      if (!audioEl.duration) return;
      const frac = audioEl.currentTime / audioEl.duration;
      const pc = frac * 100;
      progress.value = pc;
      setBarPosition(pc);
    };

    function setBarPosition(percentage) {
      const leftPos =
        CONFIG.LEFT_MARGIN_PERCENT +
        (percentage * (100 - CONFIG.LEFT_MARGIN_PERCENT - CONFIG.RIGHT_MARGIN_PERCENT)) / 100;
      indicator.style.left = leftPos + "%";
    }

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
      setBarPosition(progress.value);
    });

    // Spectrogram click => seek + play
    wrapper.addEventListener("click", (e) => {
      if (menu.style.visibility === "visible") return;
      if (overlay.contains(e.target)) return;
      if (!audioEl.duration) return;

      const r = wrapper.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
      const pc = x * 100;
      progress.value = pc;
      audioEl.currentTime = (pc / 100) * audioEl.duration;
      setBarPosition(pc);
      audioEl.play();
    });

    // Dots menu toggle
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

    // Download Audio
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
      let size = "unknown";
      let enc = "unknown";
      try {
        const head = await fetch(audioSrc, { method: "HEAD" });
        if (head.ok) {
          const cl = head.headers.get("content-length");
          if (cl) {
            const kb = parseInt(cl, 10) / 1024;
            size = kb >= 1024 ? (kb / 1024).toFixed(2) + " MB" : kb.toFixed(2) + " KB";
          }
          const ct = head.headers.get("content-type");
          if (ct) {
            const parts = ct.split("/");
            if (parts[1]) enc = parts[1].toUpperCase();
          }
        }
      } catch {}

      const dur = audioEl.duration ? audioEl.duration.toFixed(2) + " seconds" : "unknown";
      alert(`Duration: ${dur}\nSize: ${size}\nEncoding: ${enc}`);

      menuOpen = false;
      menu.style.visibility = "hidden";
    });
  });
});
