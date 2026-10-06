"""Tạo dashboard/hud/figure.bin: lấy mẫu chấm từ ảnh tượng người hạt (Hub, hình 'figure').

    python tools/tao_hinh_hat.py anh-nguon.png

Ảnh nguồn gồm hai người cạnh nhau; script cắt người chính diện bên phải. Mật độ chấm theo độ đậm
của ảnh, màu lấy từ ảnh, độ dày (z) tính từ khoảng cách tới viền hình: có mặt trước (z8>=128) và mặt sau (z8<128) nên xoay 360 độ vẫn là khối người.
Định dạng: 'MMF1', N (u32), rộng, cao (u16), rồi x16[N] y16[N] (đơn vị 1/16 px), z8[N], rgb[3N], size8[N].
"""
import struct
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

CROP = (945, 70, 2048, 1950)
N = 400000        # chấm mặt trước
NB = 160000       # chấm mặt sau (để xoay 360 độ vẫn có lưng)

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
w0 = ndi.gaussian_filter(ink, 14) ** 1.0        # mặt sau: nhòe hẳn đi, không có mắt mũi miệng (lưng, gáy)
w0[ink < 0.02] *= 0.3
w = w0.copy()
w[20:430, 300:820] *= 3.4          # khuôn mặt: nhiều chấm hơn để thấy mắt, mũi, miệng
w /= w.sum()
w0 /= w0.sum()
rng = np.random.default_rng(7)
bl = np.stack([ndi.uniform_filter(a[..., c], 3) for c in range(3)], -1)
bl_back = np.stack([ndi.gaussian_filter(a[..., c], 14) for c in range(3)], -1)

mask = ndi.binary_closing(ink > 0.14, iterations=10)
mask = ndi.binary_fill_holes(mask)
dt = ndi.distance_transform_edt(ndi.gaussian_filter(mask.astype(np.float32), 3) > 0.5)
dt = ndi.gaussian_filter(dt, 6)
zn = np.sqrt(dt / dt.max())          # 0 ở viền, 1 ở chỗ dày nhất: mặt cắt tròn như thân người thật

def lay(weights, n, back):
    idx = rng.choice(weights.size, size=n, p=weights.ravel())
    py, px = np.divmod(idx, W)
    x = px + rng.random(n) - 0.5
    y = py + rng.random(n) - 0.5
    rgb = (bl_back if back else bl)[py, px]
    if back:                          # mặt sau: cùng nét mực nhưng nhạt hơn một chút
        rgb = rgb * 0.82 + bg * 0.18
    rgb = rgb.clip(0, 255).astype(np.uint8)
    sz = np.clip((0.55 + ink[py, px] * 0.9) * 120, 0, 255).astype(np.uint8)
    d = np.round(zn[py, px] * 127).astype(np.int32)
    z8 = (127 - d if back else 128 + d).astype(np.uint8)
    return x, y, z8, rgb, sz

parts = [lay(w, N, False), lay(w0, NB, True)]
x, y, z8, rgb, sz = (np.concatenate([p[i] for p in parts]) for i in range(5))
order = rng.permutation(len(x))       # trộn đều để cắt bớt chấm (mức Cân bằng/Nhẹ) vẫn đủ cả hai mặt
x, y, z8, rgb, sz = x[order], y[order], z8[order], rgb[order], sz[order]
N = len(x)

out = bytearray(b"MMF1" + struct.pack("<IHH", N, W, H))
out += np.round(x * 16).astype("<u2").tobytes()
out += np.round(y * 16).astype("<u2").tobytes()
out += z8.tobytes() + rgb.tobytes() + sz.tobytes()
open("dashboard/hud/figure.bin", "wb").write(out)
print("ok", N, W, H, len(out) // 1024, "KB")
