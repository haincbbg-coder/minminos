"""Offline validation + real FFmpeg: local scenes never call image/video AI."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp()
import _paths  # noqa
from xuong_video import kho, tu_lieu, chay, ghep


async def test():
    pid = kho.tao({"nguon": "tu_lieu", "ten": "Local render", "y_tuong": "test"})
    rel, _ = kho.them_tai_lieu(pid, "sample.png", b"placeholder")
    p = kho.doc(pid)
    plan = {"canh": [{"rel": rel, "giay": 1, "chu": "Xin chào MinMin"}]}
    clean = tu_lieu.chuan_hoa(p, dict(plan, mau="x',bad", toc_do=float("nan")))
    assert clean["mau"] == "#FFFFFF" and clean["toc_do"] == 1
    for bad in ({}, {"canh": [{"rel": "../../outside.png"}]},
                dict(plan, nhac=rel), dict(plan, canh=[{"rel": rel, "giay": 30}] * 7)):
        try:
            tu_lieu.chuan_hoa(p, bad)
            raise AssertionError("accepted invalid material plan")
        except ValueError:
            pass
    assert "<" not in tu_lieu._srt([(0, 1, "<b>hello</b>")])
    print("PASS plan ownership, media types, numeric bounds, subtitles")
    if not shutil.which("ffmpeg"):
        print("SKIP real FFmpeg (not installed)")
        return

    root = kho.thu_muc(pid)
    def ff(*args):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], check=True)
    # Real still, clip and audio, no downloaded/user assets.
    img = root / rel
    img.unlink()
    ff("-f", "lavfi", "-i", "color=red:s=120x180", "-frames:v", "1", "-threads", "1", img)
    sample = root / "source.mp4"
    ff("-f", "lavfi", "-i", "color=blue:s=180x120:r=30", "-t", "0.5", "-c:v", "libx264", sample)
    clip, err = kho.them_tai_lieu(pid, "clip.mp4", sample.read_bytes())
    assert not err
    sound = root / "tone.wav"
    ff("-f", "lavfi", "-i", "sine=frequency=440:duration=3", sound)
    bg, err = kho.them_tai_lieu(pid, "music.wav", sound.read_bytes())
    assert not err
    # Smaller test frame, same production rendering path.
    ghep.KICH_CO["9:16"] = (180, 320)
    data = {"canh": [{"rel": rel, "giay": 1, "chu": "Một"}, {"rel": clip, "giay": 1, "chu": "Hai"}],
            "nhac": bg, "loi_doc": bg, "giong": "tep", "phu_de": True, "khung": "fit"}
    kho.cap_nhat(pid, ban_dung=tu_lieu.chuan_hoa(kho.doc(pid), data))
    async def forbidden(*args):
        raise AssertionError("local mode must not call script/image/video AI")
    await chay.san_xuat(pid, forbidden, forbidden)
    p = kho.doc(pid)
    assert p["trang_thai"] == "san_sang", p["loi"]
    result = p["ket_qua"]
    video = kho.duong_dan_file(pid, result["video"])
    assert video and video.stat().st_size > 1000
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
    assert {"video", "audio"} <= {s["codec_type"] for s in info["streams"]}
    assert 1.9 <= float(info["format"]["duration"]) <= 2.2
    assert result["phu_de"] and "Hai" in kho.duong_dan_file(pid, result["srt"]).read_text(encoding="utf-8")
    print("PASS real still + looped clip + uploaded narration + BGM + burned subtitles + MP4/SRT")
    old = video
    # Mock only external TTS, exercise timestamps and actual FFmpeg audio/render.
    async def fake_edge(text, voice, rate, path):
        shutil.copyfile(sound, path)
        return [(0, .5, "Xin"), (.5, .5, "chào")]
    tu_lieu._edge = fake_edge
    data.update(giong="edge", nhac="", canh=[{"rel": rel, "giay": 1, "chu": "Xin chào"}], khung="crop")
    kho.cap_nhat(pid, ban_dung=tu_lieu.chuan_hoa(kho.doc(pid), data))
    result = await tu_lieu.dung(pid)
    assert result["giay"] >= 3 and old.is_file()
    txt = kho.duong_dan_file(pid, result["srt"]).read_text(encoding="utf-8")
    assert "00:00:00,500" in txt
    print("PASS timestamp subtitles, narration extends scene, rerender preserves prior artifact")


asyncio.run(test())

# New API retains the existing licence gate, rejects foreign assets and busy edits.
from fastapi import FastAPI
from fastapi.testclient import TestClient
import giay_phep
from routes import xuong_video as rx, ket_noi_ngoai as knn
async def no_ai(*args):
    raise AssertionError("unexpected AI call")
app = FastAPI()
rx.register(app, no_ai, lambda *_: [])
with TestClient(app) as client:
    api = "/apps/xuong-video/api"
    giay_phep.da_mo = lambda _: False
    assert client.put(api + "/du-an/a/ban-dung", json={}).status_code == 403
    giay_phep.da_mo = lambda _: True
    knn.da_dong_y = lambda *_: True
    pid = client.post(api + "/du-an", json={"y_tuong": "test", "nguon": "tu_lieu"}).json()["id"]
    r = client.post(f"{api}/du-an/{pid}/tai-lieu?ten=sample.png", content=b"test")
    rel = r.json()["rel"]
    url = f"{api}/du-an/{pid}/ban-dung"
    assert client.put(url, json={"canh": [{"rel": "outside.png"}]}).status_code == 400
    assert client.put(url, json={"canh": []}).status_code == 200
    assert kho.doc(pid)["ban_dung"]["canh"] == []
    assert client.post(f"{api}/du-an/{pid}/chay").status_code == 400
    assert client.put(url, json={"canh": [{"rel": rel, "chu": "test"}]}).status_code == 200
    chay._dang_chay.add(pid)
    assert client.put(url, json={"canh": [{"rel": rel}]}).status_code == 409
    assert client.patch(f"{api}/du-an/{pid}", json={"ten": "oops"}).status_code == 409
    assert client.post(f"{api}/du-an/{pid}/tai-lieu?ten=b.png", content=b"x").status_code == 409
    chay._dang_chay.discard(pid)
    r = client.get(f"{api}/du-an/{pid}/tep", params={"rel": rel, "tai": "true"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert client.get(f"{api}/du-an/{pid}/tep", params={"rel": "../../khoa.json"}).status_code == 404
    called = []
    from threading import Event
    started = Event()
    async def capture(pid, *args):
        called.append(pid)
        started.set()
    original = chay.san_xuat
    chay.san_xuat = capture
    assert client.post(f"{api}/du-an/{pid}/chay").status_code == 200
    assert started.wait(2), "background task did not start"
    assert called == [pid], called
    chay.san_xuat = original
    print("PASS licence, asset ownership, busy edits, explicit download and async start")

