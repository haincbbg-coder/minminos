"""Listen-only ChatGPT voice preview, isolated from chat history and tools."""
import asyncio
import json

SAMPLE = "Chào bạn, Min Min đây. Bạn muốn mình giúp việc gì hôm nay?"


async def serve(ws, provider):
    tasks = []
    try:
        await provider.connect()
        await ws.send_json({"type": "ready"})

        async def events():
            async for event in provider.events():
                if event.get("type") in ("error", "transcript", "turn_done"):
                    await ws.send_json(event)
                # No handoff/tool execution, history writes, or user audio in previews.

        async def client():
            offered = False
            spoken = False
            while True:
                message = await ws.receive()
                if message.get("type") == "websocket.disconnect":
                    return
                try:
                    data = json.loads(message.get("text") or "{}")
                except (ValueError, TypeError):
                    continue
                if data.get("type") == "stop":
                    return
                if data.get("type") == "webrtc_offer" and not offered:
                    offered = True
                    answer = await provider.start_webrtc(str(data.get("sdp") or ""))
                    await ws.send_json({"type": "webrtc_answer", "sdp": answer})
                elif data.get("type") == "sample" and offered and not spoken:
                    spoken = True
                    await provider.send_text("Chỉ đọc nguyên văn câu nghe thử sau, không thêm lời: " + SAMPLE)

        tasks = [asyncio.create_task(events()), asyncio.create_task(client())]
        done, _ = await asyncio.wait(tasks, timeout=60, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except Exception:
        try:
            await ws.send_json({"type": "error", "message": "Không mở được giọng nghe thử. Hãy thử lại."})
        except Exception:
            pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await provider.close()
        try:
            await ws.close()
        except Exception:
            pass
