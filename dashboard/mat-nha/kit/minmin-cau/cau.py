# -*- coding: utf-8 -*-
"""minmin-cau: cau noi Frigate (may o nha) -> MinMin (VPS).

Nghe MQTT cua Frigate, gom moi su kien thanh mot dong gon roi POST len
{MINMIN_URL}/mat-nha/su-kien voi header x-mat-nha-token. Chi gui TOM TAT + anh chup nho:
video, khuon mat da hoc va ma camera o yen tren may nay.

Chu de MQTT dang nghe (prefix mac dinh "frigate"):
  frigate/events                        type=end -> mot su kien nguoi/xe/con vat/do vat
  frigate/tracked_object_update         type=face (ten nguoi nha), type=lpr (bien so)
  frigate/<camera>/audio/transcription  loi noi chep lai (gom theo cau, gui khi im 15 giay)

Mat mang: su kien nam trong hang doi file (/data/hang-doi.jsonl), gui lai voi thoi gian
cho tang dan (5s -> 5 phut). Trung id thi bo qua (nho 5000 id gan nhat).

Bien moi truong: MINMIN_URL, MAT_NHA_TOKEN (bat buoc); MQTT_HOST=mosquitto, MQTT_PORT=1883,
MQTT_PREFIX=frigate, FRIGATE_URL=http://frigate:5000, GUI_ANH=1, ANH_CAO=360,
THU_MUC=/data, NHIP_GIAY=120, CAMERAS=cong,san (de bao trang thai).
"""
from __future__ import annotations

import base64
import collections
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

PHIEN_BAN = "1.1.0"
ANH_TOI_DA = 280 * 1024
HANG_DOI_TOI_DA = 3000
IM_LANG_GIAY = 15.0
LOI_NOI_TOI_DA = 900

LOAI_THEO_NHAN = {
    "person": "nguoi", "face": "nguoi",
    "car": "xe", "motorcycle": "xe", "bicycle": "xe", "truck": "xe", "bus": "xe",
    "license_plate": "xe",
    "dog": "con_vat", "cat": "con_vat", "bird": "con_vat", "horse": "con_vat", "cow": "con_vat",
}
NHAN_AM_THANH = {"speech", "bark", "yell", "scream", "fire_alarm", "smoke_detector", "crying",
                 "baby_cry", "doorbell", "knock", "glass", "shatter", "siren", "car_alarm",
                 "honk", "meow", "laughter", "whistle", "music"}


# CANH RAO (1.1.0): vung ve trong Frigate dat ten theo quy uoc
#   rao_...   = dai sat hang rao / cong (ben ngoai hoac ngay tai rao)
#   trong_... = ben trong san, khu cam
# Cau noi suy ra muc canh bao tu thu tu cac vung mot nguoi da di qua (entered_zones).
LANG_VANG_GIAY = 30.0
MUC_BAO_NGAY = ("vuot_rao", "vao_khu")


def muc_canh_bao(vung, bat_dau=None, ket_thuc=None, xong=False):
    """Tra "vuot_rao" | "vao_khu" | "lang_vang" | "tien_sat" | None tu danh sach vung da vao.

    - vao dai rao ROI moi vao khu trong  -> vuot_rao (nang nhat)
    - vao thang khu trong                -> vao_khu
    - chi o dai rao, lau >= 30 giay      -> lang_vang (chi ket luan khi su kien da xong)
    - chi o dai rao                      -> tien_sat (chi ket luan khi su kien da xong)
    """
    ds = [str(z or "").lower() for z in (vung or [])]
    rao = [i for i, z in enumerate(ds) if z.startswith("rao")]
    trong = [i for i, z in enumerate(ds) if z.startswith("trong")]
    if trong:
        if rao and rao[0] < trong[0]:
            return "vuot_rao"
        return "vao_khu"
    if rao and xong:
        try:
            lau = float(ket_thuc or 0) - float(bat_dau or 0)
        except (TypeError, ValueError):
            lau = 0
        return "lang_vang" if lau >= LANG_VANG_GIAY else "tien_sat"
    return None


def log(*a):
    print("[minmin-cau]", *a, file=sys.stderr, flush=True)


def _ten_sub_label(sub):
    """sub_label cua Frigate co the la None, "Bo", hoac ["Bo", 0.93]."""
    if not sub:
        return None
    if isinstance(sub, (list, tuple)):
        sub = sub[0] if sub else None
    s = str(sub or "").strip()
    return s or None


class Cau:
    def __init__(self, minmin_url="", token="", frigate_url="http://frigate:5000", thu_muc="/data",
                 gui_anh=True, anh_cao=360, prefix="frigate", cameras=None, gui_ham=None, lay_anh_ham=None):
        self.minmin_url = (minmin_url or "").rstrip("/")
        self.token = token or ""
        self.frigate_url = (frigate_url or "").rstrip("/")
        self.thu_muc = thu_muc
        self.gui_anh = gui_anh
        self.anh_cao = int(anh_cao or 360)
        self.prefix = prefix or "frigate"
        self.cameras = set(c for c in (cameras or []) if c)
        self.nhan_dien = collections.OrderedDict()   # id -> {"ten":..., "bien_so":..., "ten_xe":...}
        self.da_gui = collections.OrderedDict()      # id -> 1  (5000 id gan nhat)
        self.loi_noi = {}                            # camera -> {"bat_dau", "cuoi", "chu"}
        self.da_bao = collections.OrderedDict()      # id su kien da gui canh bao som (vuot rao)
        self.khoa = threading.Lock()
        self.gui_ham = gui_ham or self._gui_http
        self.lay_anh_ham = lay_anh_ham or self._lay_anh_http
        self.cho_den = 0.0
        self.cho_giay = 5.0
        os.makedirs(self.thu_muc, exist_ok=True)
        self.f_hang_doi = os.path.join(self.thu_muc, "hang-doi.jsonl")
        self.f_da_gui = os.path.join(self.thu_muc, "da-gui.json")
        try:
            with open(self.f_da_gui, encoding="utf-8") as fh:
                for i in json.load(fh)[-5000:]:
                    self.da_gui[i] = 1
        except Exception:
            pass

    # ------------------------------------------------------------ nhan tin MQTT
    def xu_ly(self, topic, payload, now=None):
        """Xu ly mot tin MQTT. Tra ve su kien vua xep hang (dict) hoac None."""
        now = now or time.time()
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8", "replace")
        p = self.prefix
        if topic == p + "/tracked_object_update":
            self._nho_nhan_dien(payload)
            return None
        if topic == p + "/events":
            return self._su_kien(payload)
        if topic.startswith(p + "/") and topic.endswith("/audio/transcription"):
            cam = topic[len(p) + 1:-len("/audio/transcription")]
            return self._loi_noi(cam, payload, now)
        return None

    def _nho_nhan_dien(self, payload):
        try:
            m = json.loads(payload)
        except Exception:
            return
        if not isinstance(m, dict) or not m.get("id"):
            return
        with self.khoa:
            d = self.nhan_dien.setdefault(str(m["id"]), {})
            self.nhan_dien.move_to_end(str(m["id"]))
            if m.get("type") == "face" and m.get("name"):
                d["ten"] = str(m["name"])
            elif m.get("type") == "lpr":
                if m.get("plate"):
                    d["bien_so"] = str(m["plate"])
                if m.get("name"):
                    d["ten_xe"] = str(m["name"])
            while len(self.nhan_dien) > 5000:
                self.nhan_dien.popitem(last=False)

    def _su_kien(self, payload):
        try:
            m = json.loads(payload)
        except Exception:
            return None
        if not isinstance(m, dict):
            return None
        if m.get("type") in ("new", "update"):
            return self._canh_bao_som(m.get("after") or {})
        if m.get("type") != "end":
            return None
        a = m.get("after") or {}
        eid = str(a.get("id") or "")
        if not eid or a.get("false_positive"):
            return None
        nhan = str(a.get("label") or "")
        loai = LOAI_THEO_NHAN.get(nhan) or ("giong" if nhan in NHAN_AM_THANH else "vat")
        with self.khoa:
            nd = dict(self.nhan_dien.pop(eid, {}))
        sub = _ten_sub_label(a.get("sub_label"))
        ten = bien_so = None
        if loai == "nguoi":
            ten = nd.get("ten") or sub
        elif loai == "xe":
            bien_so = nd.get("bien_so") or a.get("recognized_license_plate") or None
            ten = nd.get("ten_xe") or sub   # bien so quen (known_plates) -> ten xe
        ev = {
            "id": eid[:80],
            "camera": a.get("camera") or "",
            "loai": loai,
            "nhan": nhan,
            "ten": ten,
            "bien_so": bien_so,
            "la_nguoi_la": bool(loai == "nguoi" and not ten),
            "bat_dau": a.get("start_time"),
            "ket_thuc": a.get("end_time"),
            "diem": a.get("top_score") or a.get("score"),
            "chu": None,
        }
        vung = [str(z) for z in (a.get("entered_zones") or []) if z][:8]
        if vung:
            ev["vung"] = vung
        if loai == "nguoi":
            muc = muc_canh_bao(vung, a.get("start_time"), a.get("end_time"), xong=True)
            if muc:
                ev["canh_bao"] = muc
                with self.khoa:
                    # Da nhan chu bang canh bao som roi: ban cuoi chi de luu, khong nhan lan hai.
                    if self.da_bao.pop(eid, None):
                        ev["da_bao"] = True
        if a.get("camera"):
            self.cameras.add(a["camera"])
        if self.gui_anh and a.get("has_snapshot"):
            anh = self.lay_anh_ham(eid)
            if anh:
                ev["anh_b64"] = base64.b64encode(anh).decode("ascii")
        return self.xep_hang(ev)

    def _canh_bao_som(self, a):
        """Nguoi VUOT RAO / VAO KHU CAM thi gui ngay luc dang dien ra, khong doi su kien ket thuc
        (mot nguoi dung trong san 5 phut thi 5 phut sau moi biet la qua muon)."""
        eid = str(a.get("id") or "")
        if not eid or a.get("false_positive") or str(a.get("label") or "") != "person":
            return None
        vung = [str(z) for z in (a.get("entered_zones") or []) if z][:8]
        muc = muc_canh_bao(vung)
        if muc not in MUC_BAO_NGAY:
            return None
        with self.khoa:
            if eid in self.da_bao:
                return None
            self.da_bao[eid] = 1
            while len(self.da_bao) > 2000:
                self.da_bao.popitem(last=False)
            nd = dict(self.nhan_dien.get(eid, {}))
        ten = nd.get("ten") or _ten_sub_label(a.get("sub_label"))
        ev = {
            "id": ("cb-" + eid)[:80],
            "camera": a.get("camera") or "",
            "loai": "nguoi",
            "nhan": "person",
            "ten": ten,
            "bien_so": None,
            "la_nguoi_la": not ten,
            "bat_dau": a.get("start_time"),
            "ket_thuc": None,
            "diem": a.get("top_score") or a.get("score"),
            "chu": None,
            "canh_bao": muc,
            "vung": vung,
        }
        if self.gui_anh:
            anh = self.lay_anh_ham(eid)
            if anh:
                ev["anh_b64"] = base64.b64encode(anh).decode("ascii")
        return self.xep_hang(ev)

    def _loi_noi(self, cam, payload, now):
        chu = " ".join(str(payload or "").split())
        if not chu:
            return None
        ra = None
        with self.khoa:
            b = self.loi_noi.get(cam)
            if b and (now - b["cuoi"] > IM_LANG_GIAY or len(b["chu"]) + len(chu) > LOI_NOI_TOI_DA):
                ra = self.loi_noi.pop(cam)
                b = None
            if not b:
                self.loi_noi[cam] = {"bat_dau": now, "cuoi": now, "chu": chu}
            else:
                b["cuoi"] = now
                b["chu"] += " " + chu
        self.cameras.add(cam)
        return self._gui_loi_noi(cam, ra) if ra else None

    def _gui_loi_noi(self, cam, b):
        h = hashlib.sha1(f"{cam}|{b['bat_dau']}|{b['chu']}".encode("utf-8")).hexdigest()[:16]
        return self.xep_hang({"id": f"giong-{h}", "camera": cam, "loai": "giong", "nhan": "speech",
                              "ten": None, "bien_so": None, "la_nguoi_la": False,
                              "bat_dau": b["bat_dau"], "ket_thuc": b["cuoi"], "diem": None,
                              "chu": b["chu"][:LOI_NOI_TOI_DA]})

    def tick(self, now=None):
        """Goi dinh ky: dong cac doan loi noi da im lang du lau."""
        now = now or time.time()
        xong = []
        with self.khoa:
            for cam, b in list(self.loi_noi.items()):
                if now - b["cuoi"] > IM_LANG_GIAY:
                    xong.append((cam, self.loi_noi.pop(cam)))
        return [self._gui_loi_noi(c, b) for c, b in xong]

    # ------------------------------------------------------------ hang doi
    def _doc_hang_doi(self):
        try:
            with open(self.f_hang_doi, encoding="utf-8") as fh:
                return [json.loads(d) for d in fh if d.strip()]
        except FileNotFoundError:
            return []
        except Exception as e:
            log("hang doi hong, bo qua dong loi:", e)
            ds = []
            try:
                with open(self.f_hang_doi, encoding="utf-8") as fh:
                    for d in fh:
                        try:
                            ds.append(json.loads(d))
                        except Exception:
                            pass
            except Exception:
                pass
            return ds

    def _ghi_hang_doi(self, ds):
        tmp = self.f_hang_doi + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for ev in ds[-HANG_DOI_TOI_DA:]:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        os.replace(tmp, self.f_hang_doi)

    def xep_hang(self, ev):
        with self.khoa:
            if ev["id"] in self.da_gui:
                return None
            ds = self._doc_hang_doi()
            if any(x.get("id") == ev["id"] for x in ds):
                return None
            ds.append(ev)
            self._ghi_hang_doi(ds)
        return ev

    def so_hang_doi(self):
        with self.khoa:
            return len(self._doc_hang_doi())

    def gui_het(self, now=None):
        """Gui cac su kien dang cho. Tra so da gui. Loi mang -> cho lau dan roi thu lai."""
        now = now or time.time()
        if now < self.cho_den:
            return 0
        with self.khoa:
            ds = self._doc_hang_doi()
        da = 0
        con = list(ds)
        for ev in ds:
            ma = self.gui_ham(ev)
            if ma == 413 and ev.get("anh_b64"):
                ev = dict(ev)
                ev.pop("anh_b64", None)
                ma = self.gui_ham(ev)
            if 200 <= ma < 300 or ma in (400, 409, 413, 422):
                # 4xx do du lieu (khong phai do mang/ma) -> bo, khong gui mai mai
                if not 200 <= ma < 300:
                    log(f"MinMin tu choi su kien {ev['id']} (HTTP {ma}), bo qua")
                con.pop(0)
                da += 1
                with self.khoa:
                    self.da_gui[ev["id"]] = 1
                    while len(self.da_gui) > 5000:
                        self.da_gui.popitem(last=False)
                continue
            if ma == 401:
                log("MinMin bao SAI MA GHEP NOI (401). Tao ma moi tren trang /mat-nha roi sua MAT_NHA_TOKEN trong .env.")
                self.cho_giay = 300.0
            else:
                self.cho_giay = min(300.0, max(5.0, self.cho_giay * 2))
            self.cho_den = now + self.cho_giay
            break
        else:
            self.cho_giay = 5.0
        with self.khoa:
            # giu nhung su kien moi xep them trong luc dang gui
            moi = [x for x in self._doc_hang_doi() if x.get("id") not in {e.get("id") for e in ds}]
            self._ghi_hang_doi(con + moi)
            if da:
                try:
                    with open(self.f_da_gui, "w", encoding="utf-8") as fh:
                        json.dump(list(self.da_gui)[-5000:], fh)
                except Exception:
                    pass
        return da

    # ------------------------------------------------------------ mang
    def _gui_http(self, body):
        if not self.minmin_url or not self.token:
            return 0
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.minmin_url + "/mat-nha/su-kien", data=data, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "x-mat-nha-token": self.token,
                                              "User-Agent": "minmin-cau/" + PHIEN_BAN})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception as e:
            log("chua gui duoc (mat mang?):", type(e).__name__, e)
            return 0

    def _lay_anh_http(self, eid):
        url = f"{self.frigate_url}/api/events/{eid}/snapshot.jpg?height={self.anh_cao}&quality=70&bbox=1"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = r.read(ANH_TOI_DA + 1)
            if len(data) > ANH_TOI_DA or not data.startswith(b"\xff\xd8"):
                return None
            return data
        except Exception as e:
            log("khong lay duoc anh", eid, type(e).__name__)
            return None

    def nhip(self):
        return self.gui_ham({"loai": "nhip", "cameras": sorted(self.cameras)[:32],
                             "phien_ban": PHIEN_BAN, "hang_doi": self.so_hang_doi()})


def main():
    import paho.mqtt.client as mqtt   # chi can khi chay that; test khong can paho

    env = os.environ
    cau = Cau(minmin_url=env.get("MINMIN_URL", ""), token=env.get("MAT_NHA_TOKEN", ""),
              frigate_url=env.get("FRIGATE_URL", "http://frigate:5000"),
              thu_muc=env.get("THU_MUC", "/data"), gui_anh=env.get("GUI_ANH", "1") != "0",
              anh_cao=int(env.get("ANH_CAO", "360")), prefix=env.get("MQTT_PREFIX", "frigate"),
              cameras=[c.strip() for c in env.get("CAMERAS", "").split(",")])
    if not cau.minmin_url or not cau.token:
        log("THIEU MINMIN_URL hoac MAT_NHA_TOKEN trong .env - chay lai CaiMatNha.bat")
    p = cau.prefix

    def on_connect(client, userdata, flags, rc, properties=None):
        log("da noi MQTT, rc =", rc)
        client.subscribe([(p + "/events", 0), (p + "/tracked_object_update", 0),
                          (p + "/+/audio/transcription", 0)])

    def on_message(client, userdata, msg):
        try:
            ev = cau.xu_ly(msg.topic, msg.payload)
            if ev:
                log("xep hang:", ev["camera"], ev["loai"], ev.get("ten") or ev.get("bien_so") or ev.get("nhan"))
        except Exception as e:
            log("loi xu ly tin:", type(e).__name__, e)

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="minmin-cau")
    except AttributeError:   # paho-mqtt 1.x
        client = mqtt.Client(client_id="minmin-cau")
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    host, port = env.get("MQTT_HOST", "mosquitto"), int(env.get("MQTT_PORT", "1883"))
    while True:
        try:
            client.connect(host, port, 60)
            break
        except Exception as e:
            log("chua noi duoc MQTT", host, port, e, "- thu lai sau 5s")
            time.sleep(5)
    client.loop_start()
    nhip_giay = int(env.get("NHIP_GIAY", "120"))
    nhip_luc = 0.0
    log(f"minmin-cau {PHIEN_BAN} dang chay, gui ve {cau.minmin_url or '(chua dat)'}")
    while True:
        now = time.time()
        try:
            cau.tick(now)
            cau.gui_het(now)
            if now - nhip_luc >= nhip_giay:
                nhip_luc = now
                ma = cau.nhip()
                if ma == 401:
                    log("MinMin bao sai ma ghep noi (401).")
        except Exception as e:
            log("loi vong chinh:", type(e).__name__, e)
        time.sleep(1)


if __name__ == "__main__":
    main()
