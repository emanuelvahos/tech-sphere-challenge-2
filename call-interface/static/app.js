const AGENT_ID = window.__ELEVENLABS_AGENT_ID__ || "";

const els = {
  body: document.body,
  orbButton: document.getElementById("orb-button"),
  startButton: document.getElementById("start-button"),
  endButton: document.getElementById("end-button"),
  statusLabel: document.getElementById("status-label"),
  statusIcon: document.getElementById("status-icon"),
  statusDetail: document.getElementById("status-detail"),
  waveform: document.getElementById("waveform"),
  icons: {
    mic: document.getElementById("icon-mic"),
    ear: document.getElementById("icon-ear"),
    speaker: document.getElementById("icon-speaker"),
    spinner: document.getElementById("icon-spinner"),
    warn: document.getElementById("icon-warn"),
  },
};

const waveformBars = Array.from(els.waveform.querySelectorAll("span"));

let conversation = null;
let volumePollHandle = null;

const STATES = {
  idle: {
    icon: "🎙️",
    label: "Toca el botón para iniciar la llamada",
    detail: "",
    orbIcon: "mic",
    callActive: false,
  },
  permission: {
    icon: "🔓",
    label: "Solicitando acceso al micrófono…",
    detail: "Tu navegador te pedirá permiso — acéptalo para poder hablar con el asistente.",
    orbIcon: "spinner",
    callActive: false,
  },
  connecting: {
    icon: "🔌",
    label: "Conectando con el asistente…",
    detail: "",
    orbIcon: "spinner",
    callActive: true,
  },
  listening: {
    icon: "👂",
    label: "Te está escuchando",
    detail: "Habla con calma, puedes tomarte tu tiempo.",
    orbIcon: "ear",
    callActive: true,
  },
  speaking: {
    icon: "🗣️",
    label: "El asistente está hablando",
    detail: "",
    orbIcon: "speaker",
    callActive: true,
  },
  ended: {
    icon: "✅",
    label: "Llamada finalizada",
    detail: "Puedes iniciar otra llamada cuando quieras.",
    orbIcon: "mic",
    callActive: false,
  },
  error: {
    icon: "⚠️",
    label: "Hubo un problema con la llamada",
    detail: "",
    orbIcon: "warn",
    callActive: false,
  },
  "not-configured": {
    icon: "⚙️",
    label: "El asistente aún no está configurado",
    detail: "Falta ELEVENLABS_AGENT_ID en el servidor.",
    orbIcon: "warn",
    callActive: false,
  },
};

function setState(name, detailOverride) {
  const state = STATES[name];
  if (!state) return;

  els.body.dataset.state = name;
  els.body.dataset.callActive = String(state.callActive);

  els.statusIcon.textContent = state.icon;
  els.statusLabel.textContent = state.label;
  els.statusDetail.textContent = detailOverride ?? state.detail;

  Object.entries(els.icons).forEach(([key, el]) => {
    el.classList.toggle("orb-icon-hidden", key !== state.orbIcon);
  });

  const inCall = name === "connecting" || name === "listening" || name === "speaking";
  els.startButton.classList.toggle("is-hidden", inCall || name === "permission");
  els.endButton.classList.toggle("is-hidden", !inCall);
  els.startButton.disabled = name === "permission";
}

function stopVolumePolling() {
  if (volumePollHandle) {
    clearInterval(volumePollHandle);
    volumePollHandle = null;
  }
  waveformBars.forEach((bar) => (bar.style.transform = "scaleY(0.2)"));
}

function startVolumePolling() {
  stopVolumePolling();
  volumePollHandle = setInterval(async () => {
    if (!conversation) return;
    try {
      const mode = els.body.dataset.state;
      const volume =
        mode === "speaking"
          ? await conversation.getOutputVolume()
          : await conversation.getInputVolume();
      const level = Math.min(1, Math.max(0, volume ?? 0));
      waveformBars.forEach((bar, i) => {
        const jitter = 0.55 + Math.sin(Date.now() / 180 + i) * 0.25;
        const scale = 0.2 + level * jitter * 1.6;
        bar.style.transform = `scaleY(${Math.min(1, Math.max(0.15, scale))})`;
      });
    } catch (e) {
      // volumen no disponible momentáneamente, no es un error de llamada
    }
  }, 90);
}

async function startCall() {
  if (!AGENT_ID) {
    setState("not-configured");
    return;
  }

  setState("permission");

  try {
    await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    setState("error", "No se pudo acceder al micrófono. Revisa los permisos del navegador e inténtalo de nuevo.");
    return;
  }

  setState("connecting");

  try {
    const { Conversation } = await import("https://esm.sh/@elevenlabs/client@0.8.1");

    conversation = await Conversation.startSession({
      agentId: AGENT_ID,
      onConnect: () => {
        setState("listening");
        startVolumePolling();
      },
      onDisconnect: () => {
        stopVolumePolling();
        setState("ended");
        conversation = null;
      },
      onModeChange: ({ mode }) => {
        if (mode === "speaking") setState("speaking");
        else if (mode === "listening") setState("listening");
      },
      onStatusChange: ({ status }) => {
        if (status === "connecting") setState("connecting");
        if (status === "disconnected" && els.body.dataset.state !== "ended") {
          stopVolumePolling();
          setState("ended");
        }
      },
      onError: (message) => {
        stopVolumePolling();
        setState("error", typeof message === "string" ? message : "Ocurrió un error inesperado durante la llamada.");
      },
    });
  } catch (err) {
    stopVolumePolling();
    setState("error", "No se pudo iniciar la llamada. Verifica tu conexión e inténtalo de nuevo.");
  }
}

async function endCall() {
  stopVolumePolling();
  if (conversation) {
    try {
      await conversation.endSession();
    } catch (e) {
      // ya se estaba cerrando
    }
    conversation = null;
  }
  setState("ended");
}

els.startButton.addEventListener("click", startCall);
els.endButton.addEventListener("click", endCall);
els.orbButton.addEventListener("click", () => {
  const current = els.body.dataset.state;
  if (current === "idle" || current === "ended" || current === "error" || current === "not-configured") {
    startCall();
  }
});

setState(AGENT_ID ? "idle" : "not-configured");
