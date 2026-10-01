// Trich tu Zalo Forwarder v2.10.0 (TrungKienHa), chuyen sang chay tren web trong MinMin OS.
"use strict";
var fs8 = require("node:fs");
var path3 = require("node:path");
var crypto3 = require("node:crypto");
var EXT_BY_MIME = {
  "image/jpeg": ".jpg",
  "image/jpg": ".jpg",
  "image/png": ".png",
  "image/gif": ".gif",
  "image/webp": ".webp",
  "video/mp4": ".mp4",
  "video/quicktime": ".mov",
  "video/webm": ".webm"
};
function extFromUrl(url) {
  const clean = String(url).split("?")[0];
  const ext = path3.extname(clean);
  return ext && ext.length <= 5 ? ext : "";
}
async function downloadToTmp(url, tmpDir2, fallbackExt = ".bin") {
  fs8.mkdirSync(tmpDir2, { recursive: true });
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Tai media that bai (${res.status})`);
  const buf = Buffer.from(await res.arrayBuffer());
  const mime = (res.headers.get("content-type") || "").split(";")[0].trim();
  const ext = EXT_BY_MIME[mime] || extFromUrl(url) || fallbackExt;
  const filePath = path3.join(tmpDir2, crypto3.randomBytes(8).toString("hex") + ext);
  await fs8.promises.writeFile(filePath, buf);
  return filePath;
}
function cleanup(filePath) {
  try {
    if (fs8.existsSync(filePath)) fs8.unlinkSync(filePath);
  } catch (_e) {
  }
}
module.exports = { downloadToTmp, cleanup };
