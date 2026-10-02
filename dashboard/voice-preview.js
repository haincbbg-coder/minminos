/* Genuine selected ChatGPT voice, receive-only: no microphone permission or recording. */
(function () {
  "use strict";
  let current = null;
  function stop() { if (current) current(); }
  async function play(voice, status) {
    stop();
    const pc = new RTCPeerConnection();
    const audio = new Audio();
    audio.autoplay = true;
    // Unlock audio during the click for Safari/iPhone; no input device is opened.
    let audioContext = null, audioSource = null, transcript = "";
    try {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (Context) { audioContext = new Context(); audioContext.resume().catch(() => {}); }
    } catch (_) {}
    const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://")
      + location.host + "/ws/voice-preview?voice=" + encodeURIComponent(voice));
    let timer, ended = false, doneTimer;
    const finish = () => {
      if (ended) return;
      ended = true;
      clearTimeout(timer); clearTimeout(doneTimer);
      audio.pause(); audio.srcObject = null;
      if (audioSource) audioSource.disconnect();
      if (audioContext) audioContext.close().catch(() => {});
      pc.close(); ws.close();
      if (current === finish) current = null;
    };
    current = finish;
    const fail = () => { status("Không phát được giọng nghe thử. Hãy thử lại."); finish(); };
    timer = setTimeout(fail, 60000);
    status("Đang mở giọng nghe thử ChatGPT Live…");
    pc.addTransceiver("audio", { direction: "recvonly" });
    pc.createDataChannel("oai-events");
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
    ws.onerror = fail;
    ws.onclose = () => { if (!ended) fail(); };
    ws.onmessage = async e => {
      try {
        const data = JSON.parse(e.data);
        if (ended) return;
        if (data.type === "ready") {
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
          if (!ended) ws.send(JSON.stringify({ type: "sample" }));
        } else if (data.type === "transcript" && data.role === "assistant") {
          transcript += data.text || "";
          status("Đang nghe thử: " + transcript);
          // Transcript can finish slightly before the last audio packets arrive.
        } else if (data.type === "turn_done") {
          doneTimer = setTimeout(() => { status("Đã nghe thử giọng Min Min."); finish(); }, 3000);
        } else if (data.type === "error") fail();
      } catch (_) { if (!ended) fail(); }
    };
  }
  window.addEventListener("pagehide", stop);
  window.MinMinVoicePreview = { play, stop };
})();
