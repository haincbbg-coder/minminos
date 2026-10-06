"""Tạo dashboard/hud/figure.bin: lấy mẫu chấm từ ảnh tượng người hạt (Hub, hình 'figure').

    python tools/tao_hinh_hat.py anh-nguon.png

Ảnh nguồn gồm hai người cạnh nhau; script cắt người chính diện bên phải. Mật độ chấm theo độ đậm
của ảnh, màu lấy từ ảnh, độ sâu (z) tính từ khoảng cách tới viền hình để người có khối khi xoay nhẹ.
Định dạng: 'MMF1', N (u32), rộng, cao (u16), rồi x16[N] y16[N] (đơn vị 1/16 px), z8[N], rgb[3N], size8[N].
"""
import struct
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

CROP = (945, 70, 2048, 1950)
N = 150000

src = Image.open(sys.argv[1]).convert("RGB").crop(CROP)
a = np.asarray(src).astype(np.float32)
H, W, _ = a.shape
lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
bg = np.array([243, 237, 230], dtype=np.float32)
bgl = float(bg @ np.array([0.299, 0.587, 0.114]))
sat = (a.max(2) - a.min(2)) / 255.0
ink = np.clip((bgl - lum) / bgl, 0, 1)
ink = np.maximum(ink, np.clip(sat - 0.08, 0, 1) * 0.9)
ink = ndi.gaussian_filter(ink, 1.1)
ink[ink < 0.09] = 0
w = ink ** 1.15
w[20:430, 300:820] *= 3.4          # khuôn mặt: nhiều chấm hơn để thấy mắt, mũi, miệng
w /= w.sum()
rng = np.random.default_rng(7)
idx = rng.choice(w.size, size=N, p=w.ravel())
py, px = np.divmod(idx, W)
x = px + rng.random(N) - 0.5
y = py + rng.random(N) - 0.5

blur = np.stack([ndi.uniform_filter(a[..., c], 3) for c in range(3)], -1)
rgb = blur[py, px].clip(0, 255).astype(np.uint8)
sz = np.clip((0.55 + ink[py, px] * 0.9) * 120, 0, 255).astype(np.uint8)

mask = ndi.binary_closing(ink > 0.14, iterations=10)
mask = ndi.binary_fill_holes(mask)
dt = ndi.distance_transform_edt(ndi.gaussian_filter(mask.astype(np.float32), 3) > 0.5)
dt = ndi.gaussian_filter(dt, 6)
z = np.sqrt(dt / dt.max())[py, px]
z8 = (z * 255).astype(np.uint8)

out = bytearray(b"MMF1" + struct.pack("<IHH", N, W, H))
out += np.round(x * 16).astype("<u2").tobytes()
out += np.round(y * 16).astype("<u2").tobytes()
out += z8.tobytes() + rgb.tobytes() + sz.tobytes()
open("dashboard/hud/figure.bin", "wb").write(out)
print("ok", N, W, H, len(out) // 1024, "KB")
