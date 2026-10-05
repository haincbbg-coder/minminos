"""Eyes for every engine, and the Zalo companion pack (0.73.0).

    python tests/run.py image_vision      (NO network: httpx MockTransport for the ChatGPT stream)

The owner (2026-10-04): "the Zalo MCP cannot read images in group chats". The Zalo tools that read, send and tag now live in
the store pack `javis.zalo` (its own tests are in the javis-store repo, tests/javis.zalo/). What stays in the app, and is
pinned here:
  1. `image_vision`: ChatGPT on the signed-in plan looks at brain images and describes them, the only eyes the six API
     engines have. Images outside the brain are never sent; more than 4 per look is refused.
  2. `javis_describe_image` in the bundled `image-chatgpt` plugin, read only.
  3. `javis_read_file` on a photo explains how to see it instead of returning mojibake.
  4. The Zalo plugins are no longer bundled, and the Zalo connector names `javis.zalo` as its companion pack so the QR flow
     and the Connect page can offer it. Javis never installs it silently: the state is reported, nothing more.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-iv-"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx  # noqa: E402
import yaml  # noqa: E402

import image_vision as iv  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        fails.append(name)


JPEG = b"\xff\xd8\xff\xe0" + b"x" * 200
vault = Path(tempfile.mkdtemp(prefix="javis-iv-vault-"))
(vault / "attachments").mkdir()
(vault / "attachments" / "x.jpg").write_bytes(JPEG)

# ============================================================
# 1. image_vision: payload and the real stream parser
# ============================================================
pl = iv.build_payload("hỏi", ["data:image/jpeg;base64,AAA"], model="m")
check("vision payload: text then input_image, no tools, streamed", pl["input"][0]["content"][1]["type"] == "input_image"
      and "tools" not in pl and pl["stream"] is True and pl["model"] == "m")
pr = iv.build_prompt("tổng tiền", ["tin 1, Lan", "tin 2, Quý"])
check("prompt lists one label per image and asks for an answer per image", "Ảnh 1: tin 1, Lan" in pr and "Ảnh 2" in pr
      and "tổng tiền" in pr)
check("single unlabeled image: no list", "Ảnh 1" not in iv.build_prompt("", [""]))
check("completed event text is a fallback", iv.text_from_completed(
    {"response": {"output": [{"content": [{"type": "output_text", "text": "xin chào"}]}]}}) == "xin chào")

SEEN = {}


def chatgpt(request):
    SEEN["body"] = json.loads(request.content)
    SEEN["auth"] = request.headers.get("authorization")
    events = [{"type": "response.output_text.delta", "delta": "Ảnh 1: "},
              {"type": "response.output_text.delta", "delta": "một hoá đơn"},
              {"type": "response.completed", "response": {"output": []}}]
    body = "".join("data: " + json.dumps(e, ensure_ascii=False) + "\n\n" for e in events)
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode("utf-8"))


real_oauth, real_httpx = iv.openai_oauth, iv.httpx
iv.openai_oauth = types.SimpleNamespace(valid_creds=lambda: {"access_token": "tok", "account_id": "acc"},
                                        status=lambda: {"connected": True})
gt = httpx.MockTransport(chatgpt)
iv.httpx = types.SimpleNamespace(AsyncClient=lambda **kw: httpx.AsyncClient(transport=gt, **kw), Timeout=httpx.Timeout)
r = asyncio.run(iv.describe_images(["attachments/x.jpg"], "có gì", vault_root=str(vault)))
check("ChatGPT stream deltas are joined into the answer", r.get("ok") and r["text"] == "Ảnh 1: một hoá đơn", r)
check("the image goes as a data URL, with the plan's token", SEEN["body"]["input"][0]["content"][1]["image_url"]
      .startswith("data:image/jpeg;base64,") and SEEN["auth"] == "Bearer tok")
outside = Path(tempfile.mkdtemp(prefix="javis-iv-out-")) / "secret.jpg"
outside.write_bytes(JPEG)
SEEN.clear()
r = asyncio.run(iv.describe_images([str(outside)], vault_root=str(vault)))
check("an image outside the brain is never sent", not r.get("ok") and "body" not in SEEN and r.get("error"), r)
r = asyncio.run(iv.describe_images(["a.jpg"] * 5, vault_root=str(vault)))
check("more than 4 images in one look is refused", not r.get("ok") and "body" not in SEEN)
iv.openai_oauth = types.SimpleNamespace(valid_creds=lambda: None, status=lambda: {"connected": False})
r = asyncio.run(iv.describe_images(["attachments/x.jpg"], vault_root=str(vault)))
check("not signed in to ChatGPT: says so", not r.get("ok") and "ChatGPT" in r["error"])
check("connected() is False then, and never raises", iv.connected() is False)
iv.openai_oauth = types.SimpleNamespace(status=lambda: (_ for _ in ()).throw(RuntimeError("x")))
check("connected() swallows a broken status", iv.connected() is False)
iv.openai_oauth, iv.httpx = real_oauth, real_httpx

# ============================================================
# 2. javis_describe_image in the bundled image-chatgpt plugin
# ============================================================
class Ctx:
    def __init__(self):
        self.tools = []
        self.vault_root = str(vault)

    def register_tool(self, **kw):
        self.tools.append(kw)


spec = importlib.util.spec_from_file_location("image_chatgpt_plugin", ROOT / "system" / "plugins" / "image-chatgpt" / "plugin.py")
IC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(IC)
c = Ctx()
IC.register(c)
y = yaml.safe_load((ROOT / "system" / "plugins" / "image-chatgpt" / "plugin.yaml").read_text(encoding="utf-8"))
by = {t["name"]: t for t in c.tools}
check("image-chatgpt: tools match plugin.yaml", sorted(by) == sorted(y["tools"]) == ["javis_describe_image", "javis_generate_image"],
      sorted(by))
check("describing is read only, generating stays a write", by["javis_describe_image"]["min_mode"] == "readonly"
      and by["javis_generate_image"]["min_mode"] == "safe")
calls = []


async def fake_describe(paths, question="", vault_root=None, labels=None, timeout_s=180.0):
    calls.append((paths, question, vault_root))
    return {"ok": True, "text": "một con mèo", "count": len(paths)}

real_describe = iv.describe_images
iv.describe_images = fake_describe
kq = asyncio.run(by["javis_describe_image"]["handler"]({"images": "attachments/x.jpg", "question": "con gì"},
                                                       types.SimpleNamespace(vault_root="V")))
check("javis_describe_image accepts one path as a string and passes the brain", calls == [(["attachments/x.jpg"], "con gì", "V")]
      and "một con mèo" in kq, kq)
check("javis_describe_image without images is an ERROR",
      asyncio.run(by["javis_describe_image"]["handler"]({}, types.SimpleNamespace(vault_root="V"))).startswith("ERROR"))
iv.describe_images = real_describe

# ============================================================
# 3. The brain's text reader on a photo
# ============================================================
import mcp_hub  # noqa: E402
_tools, route = mcp_hub._builtin_tools("full", str(vault))
kq = asyncio.run(route["javis_read_file"]["call"]({"path": "attachments/x.jpg"}))
check("reading a photo as text explains how to see it instead of mojibake", "javis_describe_image" in kq
      and "�" not in kq and "![](attachments/x.jpg)" in kq, kq[:200])
(vault / "note.md").write_text("xin chào", encoding="utf-8")
check("text files still read as before", asyncio.run(route["javis_read_file"]["call"]({"path": "note.md"})) == "xin chào")

# ============================================================
# 4. MinMin keeps its existing bundled Zalo tools.
bundled = {d.name for d in (ROOT / "system" / "plugins").iterdir() if d.is_dir()}
check("MinMin Zalo image and group tools stay available", {"zalo-image", "zalo-nhom"} <= bundled)

if fails:
    print("\nFAIL - test_image_vision: " + str(len(fails)) + " lỗi: " + ", ".join(fails))
    sys.exit(1)
print("\nOK - test_image_vision: tất cả pass")
