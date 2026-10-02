/* Genuine selected ChatGPT voice with synthetic silence: no microphone permission or recording. */
(function () {
  "use strict";
  let current = null, pendingPreview = null;
  function stop() { if (current) current(); }
  async function play(voice, status, provider = "chatgpt") {
    if (pendingPreview && pendingPreview.voice === voice && pendingPreview.provider === provider) {
      return pendingPreview.resume();
    }
    stop();
    const pcm = provider === "gemini";
    const pc = pcm ? null : new RTCPeerConnection();
    const sources = new Set();
    const pcmChunks = [];
    let pcmBytes = 0;
    let nextAudio = 0;
    const audio = new Audio();
    audio.autoplay = true;
    // Unlock audio during the click for Safari/iPhone; no input device is opened.
    let audioContext = null, audioSource = null, transcript = "";
    let previousAudioSession = null;
    try {
      if (navigator.audioSession) {
        previousAudioSession = navigator.audioSession.type;
        navigator.audioSession.type = "playback";
      }
    } catch (_) {}
    try {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (Context) { audioContext = new Context(); audioContext.resume().catch(() => {}); }
    } catch (_) {}
    const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://")
      + location.host + "/ws/voice-preview?voice=" + encodeURIComponent(voice) + "&provider=" + encodeURIComponent(provider));
    ws.binaryType = "arraybuffer";
    let timer, ended = false, doneTimer, silence = null, silentOutput = null, playbackStarted = false, previewReady = false;
    const finish = () => {
      if (ended) return;
      ended = true; pendingPreview = null;
      clearTimeout(timer); clearTimeout(doneTimer);
      audio.pause(); audio.srcObject = null;
      try { if (previousAudioSession !== null) navigator.audioSession.type = previousAudioSession; } catch (_) {}
      if (silence) { silence.stop(); silence.disconnect(); }
      if (silentOutput) silentOutput.stream.getTracks().forEach(track => track.stop());
      if (audioSource) audioSource.disconnect();
      if (audioContext) audioContext.close().catch(() => {});
      sources.forEach(source => { try { source.stop(); source.disconnect(); } catch (_) {} });
      sources.clear();
      if (pc) pc.close(); ws.close();
      if (current === finish) current = null;
    };
    current = finish;
    const fail = () => { status("Không phát được giọng nghe thử. Hãy thử lại."); finish(); };
    timer = setTimeout(fail, 60000);
    status("Đang mở giọng nghe thử " + (pcm ? "Gemini Live" : "ChatGPT Live") + "…");
    // The realtime model advances with incoming audio. Generate zeros, never capture a mic.
    if (!audioContext) { fail(); return; }
    // Keep an actual output connected during the original gesture on iOS.
    if (pcm) {
      silence = audioContext.createConstantSource(); silence.offset.value = 0;
      silence.connect(audioContext.destination); silence.start();
    }
    if (!pcm) {
    silentOutput = audioContext.createMediaStreamDestination();
    silence = audioContext.createConstantSource();
    silence.offset.value = 0;
    silence.connect(silentOutput); silence.start();
    pc.addTrack(silentOutput.stream.getAudioTracks()[0], silentOutput.stream);
    const channel = pc.createDataChannel("oai-events");
    channel.onopen = () => {
      if (!ended) ws.send(JSON.stringify({ type: "sample" }));
    };
    pc.ontrack = e => {
      if (ended) return;
      audio.srcObject = e.streams[0] || new MediaStream([e.track]);
      audio.play().catch(() => {
        if (ended) return;
        try {
          if (!audioContext || audioContext.state !== "running") return fail();
          audioSource = audioContext.createMediaStreamSource(audio.srcObject);
          audioSource.connect(audioContext.destination);
        } catch (_) { fail(); }
      });
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed") fail();
    };
    }
    ws.onerror = () => { if (!previewReady) fail(); };
    ws.onclose = () => { if (!ended && !previewReady && !playbackStarted) fail(); };
    ws.onmessage = async e => {
      try {
        if (pcm && e.data instanceof ArrayBuffer) {
          if (ended) return;
          pcmBytes += e.data.byteLength;
          if (pcmBytes > 8 * 1024 * 1024) return fail();
          pcmChunks.push(new Uint8Array(e.data));
          return;
        }
        const data = JSON.parse(e.data);
        if (ended) return;
        if (data.type === "ready") {
          if (pcm) { ws.send(JSON.stringify({ type: "sample" })); return; }
          await pc.setLocalDescription(await pc.createOffer());
          await new Promise(resolve => {
            if (pc.iceGatheringState === "complete") return resolve();
            const timeout = setTimeout(resolve, 1500);
            pc.onicegatheringstatechange = () => {
              if (pc.iceGatheringState === "complete") { clearTimeout(timeout); resolve(); }
            };
          });
          if (!ended) ws.send(JSON.stringify({ type: "webrtc_offer", sdp: pc.localDescription.sdp }));
        } else if (data.type === "webrtc_answer") {
          await pc.setRemoteDescription({ type: "answer", sdp: data.sdp });

        } else if (data.type === "transcript" && data.role === "assistant") {
          transcript += data.text || "";
          status("Đang nghe thử: " + transcript);
          // Transcript can finish slightly before the last audio packets arrive.
        } else if (data.type === "turn_done") {
          if (pcm) {
            // Preview is a short sentence. Buffer it once to avoid underruns/clicks
            // between network packets and preserve samples split across packets.
            if (!pcmBytes || pcmBytes % 2) return fail();
            const bytes = new Uint8Array(pcmBytes);
            let offset = 0;
            pcmChunks.forEach(chunk => { bytes.set(chunk, offset); offset += chunk.length; });
            pcmChunks.length = 0; pcmBytes = 0;
            const samples = new DataView(bytes.buffer);
            const buffer = audioContext.createBuffer(1, bytes.length / 2, 24000);
            const values = buffer.getChannelData(0);
            for (let i = 0; i < values.length; i++) values[i] = samples.getInt16(i * 2, true) / 32768;
            previewReady = true;
            const startBuffer = async () => {
              try { await audioContext.resume(); } catch (_) {}
              if (ended) return;
              if (audioContext.state !== "running") {
                pendingPreview = { voice, provider, resume: startBuffer };
                status("Giọng đã sẵn sàng. Bấm Nghe thử lần nữa để phát trên iPhone.");
                return;
              }
              pendingPreview = null; playbackStarted = true;
              clearTimeout(timer);
              const source = audioContext.createBufferSource();
              source.buffer = buffer; source.connect(audioContext.destination); sources.add(source);
              source.onended = () => {
                sources.delete(source); source.disconnect();
                if (!ended) { status("Đã nghe thử giọng Min Min."); finish(); }
              };
              nextAudio = audioContext.currentTime + 0.05;
              source.start(nextAudio); nextAudio += buffer.duration;
              status("Đang nghe thử: " + transcript);
              doneTimer = setTimeout(() => { status("Đã nghe thử giọng Min Min."); finish(); }, Math.max(3000, buffer.duration * 1000 + 1000));
            };
            await startBuffer();
            return;
          }
          doneTimer = setTimeout(() => { status("Đã nghe thử giọng Min Min."); finish(); }, pcm ? Math.max(3000, (nextAudio - audioContext.currentTime) * 1000 + 300) : 3000);
        } else if (data.type === "error") fail();
      } catch (_) { if (!ended) fail(); }
    };
  }
  window.addEventListener("pagehide", stop);
  window.MinMinVoicePreview = { play, stop };
})();
