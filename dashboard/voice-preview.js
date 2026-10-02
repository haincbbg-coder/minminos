/* Genuine selected ChatGPT voice with synthetic silence: no microphone permission or recording. */
(function () {
  "use strict";
  let current = null;
  function stop() { if (current) current(); }
  async function play(voice, status, provider = "chatgpt") {
    stop();
    const pcm = provider === "gemini";
    const pc = pcm ? null : new RTCPeerConnection();
    const sources = new Set();
    let nextAudio = 0;
    const audio = new Audio();
    audio.autoplay = true;
    // Unlock audio during the click for Safari/iPhone; no input device is opened.
    let audioContext = null, audioSource = null, transcript = "";
    try {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (Context) { audioContext = new Context(); audioContext.resume().catch(() => {}); }
    } catch (_) {}
    const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://")
      + location.host + "/ws/voice-preview?voice=" + encodeURIComponent(voice) + "&provider=" + encodeURIComponent(provider));
    ws.binaryType = "arraybuffer";
    let timer, ended = false, doneTimer, silence = null, silentOutput = null;
    const finish = () => {
      if (ended) return;
      ended = true;
      clearTimeout(timer); clearTimeout(doneTimer);
      audio.pause(); audio.srcObject = null;
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
    ws.onerror = fail;
    ws.onclose = () => { if (!ended) fail(); };
    ws.onmessage = async e => {
      try {
        if (pcm && e.data instanceof ArrayBuffer) {
          if (ended) return;
          const samples = new DataView(e.data);
          const count = Math.floor(samples.byteLength / 2);
          if (!count) return;
          const buffer = audioContext.createBuffer(1, count, 24000);
          const values = buffer.getChannelData(0);
          for (let i = 0; i < count; i++) values[i] = samples.getInt16(i * 2, true) / 32768;
          const source = audioContext.createBufferSource();
          source.buffer = buffer; source.connect(audioContext.destination); sources.add(source);
          source.onended = () => { sources.delete(source); source.disconnect(); };
          nextAudio = Math.max(nextAudio, audioContext.currentTime);
          source.start(nextAudio); nextAudio += buffer.duration;
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
          doneTimer = setTimeout(() => { status("Đã nghe thử giọng Min Min."); finish(); }, pcm ? Math.max(3000, (nextAudio - audioContext.currentTime) * 1000 + 300) : 3000);
        } else if (data.type === "error") fail();
      } catch (_) { if (!ended) fail(); }
    };
  }
  window.addEventListener("pagehide", stop);
  window.MinMinVoicePreview = { play, stop };
})();
