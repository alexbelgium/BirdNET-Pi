function initCustomAudioPlayers() {
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

  // Keep track of all player wrappers for global event handling
  const playerWrappers = [];

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

    // =============== Wrapper & Styles ===============
    const wrapper = player.appendChild(document.createElement("div"));
    applyStyles(wrapper, { position: "relative" });
    playerWrappers.push(wrapper); // Add to the wrappers array

    const img = wrapper.appendChild(document.createElement("img"));
    img.src = imageSrc;
    applyStyles(img, { width: "100%", borderRadius: "8px", cursor: "pointer" });

    const indicator = wrapper.appendChild(document.createElement("div"));
    applyStyles(indicator, {
      position: "absolute",
      top: "0",
      bottom: "5%",
      left: `${CONFIG.LEFT_MARGIN_PERCENT}%`,
      width: "2px",
      background: "rgba(0,0,0)", // Solid color; adjust opacity if needed
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
      background: "rgba(0,0,0,0.6)", // Increased opacity for better visibility
      backdropFilter: "blur(2px)",
      visibility: "hidden", // Initially hidden
      opacity: "0",
      transition: "visibility 0s, opacity 0.3s linear",
      zIndex: "1", // Ensure overlay is above other elements
    });

    // =============== Play/Pause Button ===============
    const playBtn = overlay.appendChild(document.createElement("button"));
    playBtn.type = "button";
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

    // Event listener for play/pause
    playBtn.addEventListener("click", async (e) => {
      e.stopPropagation(); // Prevent event from bubbling to wrapper or document
      if (audioCtx && audioCtx.state === "suspended") {
        await audioCtx.resume();
      }
      audioEl.paused ? audioEl.play() : audioEl.pause();
      // Optionally, toggle overlay visibility on play/pause
      // toggleOverlay();
    });
    audioEl.addEventListener("play", () => (playBtn.innerHTML = icons.pause));
    audioEl.addEventListener("pause", () => (playBtn.innerHTML = icons.play));

    // =============== Progress Bar ===============
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

    const indicatorUpdate = () => {
      if (!audioEl.duration) return;
      const frac = audioEl.currentTime / audioEl.duration;
      const pc = frac * 100;
      progress.value = pc;
      const leftPos =
        CONFIG.LEFT_MARGIN_PERCENT +
        (pc * (100 - CONFIG.LEFT_MARGIN_PERCENT - CONFIG.RIGHT_MARGIN_PERCENT)) / 100;
      indicator.style.left = leftPos + "%";
    };

    let intervalId = null;
    const updateProgress = () => {
      indicatorUpdate();
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
      indicatorUpdate();
    });

    // =============== Dots Button and Menu ===============
    const dotsBtn = overlay.appendChild(document.createElement("button"));
    dotsBtn.type = "button";
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
      background: "rgba(0,0,0,0.8)", // Increased opacity for better visibility
      backdropFilter: "blur(8px)",
      color: "white",
      borderRadius: "6px",
      padding: "0.5rem",
      visibility: "hidden",
      opacity: "0",
      transition: "visibility 0s, opacity 0.3s linear",
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-end",
      minWidth: "160px",
      zIndex: "2", // Ensure menu is above overlay
    });

    // Function to show menu
    const showMenu = () => {
      menu.style.visibility = "visible";
      menu.style.opacity = "1";
    };

    // Function to hide menu
    const hideMenu = () => {
      menu.style.opacity = "0";
      setTimeout(() => {
        menu.style.visibility = "hidden";
      }, 300); // Match the transition duration
    };

    // Toggle menu visibility
    let menuOpen = false;
    dotsBtn.addEventListener("click", (e) => {
      e.stopPropagation(); // Prevent event from bubbling to document
      menuOpen = !menuOpen;
      if (menuOpen) {
        showMenu();
      } else {
        hideMenu();
      }
    });

    // =============== Info & Download Buttons ===============
    const infoBtn = menu.appendChild(document.createElement("button"));
    infoBtn.type = "button";
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
    dlBtn.type = "button";
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
      b.addEventListener("click", (e) => {
        e.stopPropagation(); // Prevent event from bubbling to menu
        setActiveGain(opt);
      });
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
      b.addEventListener("click", (e) => {
        e.stopPropagation(); // Prevent event from bubbling to menu
        setActiveFilter(opt);
      });
      filterButtons.push(b);
    });

    // AudioContext init
    function initAudioContext() {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        sourceNode = audioCtx.createMediaElementSource(audioEl);
        gainNode = audioCtx.createGain();
        gainNode.gain.value = 1; // default, updated below
        // connect default chain
        sourceNode.connect(gainNode).connect(audioCtx.destination);
      }
    }

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

    // GAIN
    function setActiveGain(key) {
      activeGain = key;
      if (activeGain !== "Off") {
        initAudioContext();
        gainNode.gain.value = gainValues[activeGain];
      } else if (audioCtx) {
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
      } catch (e) {}
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
        rebuildAudioChain();
      } else {
        if (filterNode) {
          filterNode.disconnect();
          filterNode = null;
          rebuildAudioChain();
        }
      }
      // Update underline
      filterButtons.forEach((b) => {
        b.style.textDecoration = b.dataset.filter === activeFilterOption ? "underline" : "none";
      });
      // Save
      try {
        localStorage.setItem("customAudioPlayerFilter", activeFilterOption);
      } catch (e) {}
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
      // This call sets underline & loads the module
      setActiveGain(activeGain);
    } else {
      underlineDefaults();
    }

    if (activeFilterOption !== "Off") {
      setActiveFilter(activeFilterOption);
    } else {
      underlineDefaults();
    }

    // =============== Click Seek on the Image ===============
    wrapper.addEventListener("click", async (e) => {
      // If menu is open or user clicked on controls, skip
      if (
        menu.style.visibility === "visible" ||
        overlay.contains(e.target) ||
        !audioEl.duration
      ) {
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
      indicatorUpdate();
      audioEl.play();

      // Show overlay when seeking
      showOverlay();
    });

    // =============== Menu Open/Close ===============
    // Menu toggle is already handled above

    // =============== Download Handler ===============
    dlBtn.addEventListener("click", async (e) => {
      e.stopPropagation(); // Prevent event from bubbling to menu
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
      hideMenu();
    });

    // =============== Info Handler ===============
    infoBtn.addEventListener("click", async (e) => {
      e.stopPropagation(); // Prevent event from bubbling to menu
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

      hideMenu();
    });

    // =============== Overlay Visibility Handling for Both Mouse and Touch ===============
    // Function to show overlay
    const showOverlay = () => {
      overlay.style.visibility = "visible";
      overlay.style.opacity = "1";
    };

    // Function to hide overlay
    const hideOverlay = () => {
      overlay.style.opacity = "0";
      setTimeout(() => {
        overlay.style.visibility = "hidden";
      }, 300); // Match the transition duration
    };

    // Toggle overlay visibility
    const toggleOverlay = () => {
      if (overlay.style.visibility === "visible") {
        hideOverlay();
      } else {
        showOverlay();
      }
    };

    // =============== Event Listeners for Mouse and Touch ===============
    // Mouse Events
    wrapper.addEventListener("mouseenter", () => {
      showOverlay();
    });
    wrapper.addEventListener("mouseleave", () => {
      hideOverlay();
    });

    // Touch Events
    wrapper.addEventListener("touchstart", (e) => {
      // Prevent multiple toggles on touch devices
      toggleOverlay();
      // Prevent default to avoid triggering click events
      e.preventDefault();
    });

    // Prevent touch events from triggering mouse events
    overlay.addEventListener("touchstart", (e) => {
      e.stopPropagation();
    });
    playBtn.addEventListener("touchstart", (e) => {
      e.stopPropagation();
    });
    dotsBtn.addEventListener("touchstart", (e) => {
      e.stopPropagation();
    });
    menu.addEventListener("touchstart", (e) => {
      e.stopPropagation();
    });

    // Ensure clicks on the image toggle the overlay
    img.addEventListener("click", (e) => {
      e.stopPropagation(); // Prevent event from bubbling to document
      toggleOverlay();
    });

    // Ensure touches on the image toggle the overlay
    img.addEventListener("touchstart", (e) => {
      e.stopPropagation(); // Prevent event from bubbling to document
      toggleOverlay();
    });
  });

  // =============== Global Event Listener to Hide Overlays When Clicking or Touching Outside ===============
  // Function to hide all overlays
  const hideAllOverlays = () => {
    playerWrappers.forEach((wrapper) => {
      const overlay = wrapper.querySelector("div > div"); // Assuming overlay is the first div inside wrapper
      if (overlay) {
        overlay.style.opacity = "0";
        overlay.style.visibility = "hidden";
      }
      // Also hide all menus
      const menu = wrapper.querySelector("div > div > div"); // Assuming menu is a child of overlay
      if (menu) {
        menu.style.opacity = "0";
        menu.style.visibility = "hidden";
      }
    });
  };

  // Click outside to hide overlays
  document.addEventListener("click", (e) => {
    playerWrappers.forEach((wrapper) => {
      if (!wrapper.contains(e.target)) {
        const overlay = wrapper.querySelector("div > div"); // Adjust selector as needed
        if (overlay) {
          overlay.style.opacity = "0";
          overlay.style.visibility = "hidden";
        }
        // Hide menus as well
        const menu = wrapper.querySelector("div > div > div"); // Adjust selector as needed
        if (menu) {
          menu.style.opacity = "0";
          menu.style.visibility = "hidden";
        }
      }
    });
  });

  // Touch outside to hide overlays
  document.addEventListener("touchstart", (e) => {
    playerWrappers.forEach((wrapper) => {
      if (!wrapper.contains(e.target)) {
        const overlay = wrapper.querySelector("div > div"); // Adjust selector as needed
        if (overlay) {
          overlay.style.opacity = "0";
          overlay.style.visibility = "hidden";
        }
        // Hide menus as well
        const menu = wrapper.querySelector("div > div > div"); // Adjust selector as needed
        if (menu) {
          menu.style.opacity = "0";
          menu.style.visibility = "hidden";
        }
      }
    });
  });
}
// Run once at DOMContentLoaded
document.addEventListener("DOMContentLoaded", initCustomAudioPlayers);
