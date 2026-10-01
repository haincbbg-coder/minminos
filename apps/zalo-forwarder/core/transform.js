// Trich tu Zalo Forwarder v2.10.0 (TrungKienHa), chuyen sang chay tren web trong MinMin OS.
"use strict";
function escapeRegExp(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function roundTo(value, round) {
  if (!round || round <= 0) return Math.round(value);
  return Math.round(value / round) * round;
}
function computeNewValue(vnd, rule) {
  let out = vnd;
  switch (rule.mode) {
    case "add_percent":
      out = vnd * (1 + (rule.percent || 0) / 100);
      break;
    case "add_amount":
      out = vnd + (rule.amount || 0);
      break;
    case "multiply":
      out = vnd * (rule.factor || 1);
      break;
    default:
      out = vnd;
  }
  return roundTo(out, rule.round == null ? 1e3 : rule.round);
}
function formatVND(vnd) {
  return Math.round(vnd).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}
function formatK(vnd, kSuffix) {
  const k = vnd / 1e3;
  const num = Number.isInteger(k) ? String(k) : String(Math.round(k * 10) / 10);
  return num + kSuffix;
}
function transformPrice(text, rule) {
  if (!rule || !rule.enabled) return text;
  if (rule.mode === "replace_map") {
    let out2 = text;
    for (const [from, to] of Object.entries(rule.map || {})) {
      const re = new RegExp(escapeRegExp(from), "gi");
      out2 = out2.replace(re, to);
    }
    return out2;
  }
  let out = text;
  out = out.replace(/(\d+(?:[.,]\d+)?)\s*([kK])\b/g, (_m, numStr, kSuffix) => {
    const num = parseFloat(String(numStr).replace(",", "."));
    const vnd = num * 1e3;
    return formatK(computeNewValue(vnd, rule), kSuffix);
  });
  out = out.replace(
    /(\d{1,3}(?:[.,]\d{3})+)(\s*)(đ|₫|vnđ|vnd|d)(?![\p{L}\p{N}])/giu,
    (_m, numStr, sep, unit) => {
      const vnd = parseInt(String(numStr).replace(/[.,]/g, ""), 10);
      return formatVND(computeNewValue(vnd, rule)) + sep + unit;
    }
  );
  out = out.replace(/(\d{4,})(\s*)(đ|₫|vnđ|vnd)(?![\p{L}\p{N}])/giu, (_m, numStr, sep, unit) => {
    const vnd = parseInt(String(numStr), 10);
    return formatVND(computeNewValue(vnd, rule)) + sep + unit;
  });
  if (rule.bareNumber && rule.bareNumber.enabled) {
    const min = rule.bareNumber.min != null ? rule.bareNumber.min : 50;
    const max = rule.bareNumber.max != null ? rule.bareNumber.max : 2e3;
    const UNIT = "c\xE1i|chi\u1EBFc|m\u1EABu|b\u1ED9|\u0111\xF4i|sp|size|con|t\u1EA5m|chai|h\u1ED9p|g\xF3i|ng\u01B0\u1EDDi|ng\xE0y|gi\u1EDD|ph\xFAt|gi\xE2y|tu\u1ED5i|cm|mm|kg|ml";
    const bareRe = new RegExp(
      "(?<![\\d.,])(\\d{2,4})(?![\\d])(?![.,]\\d)(?![kK%:])(?!\\s*(?:k|\u0111|\u20AB|vn\u0111|vnd|" + UNIT + "))",
      "giu"
    );
    out = out.replace(bareRe, (m, numStr) => {
      const num = parseInt(numStr, 10);
      if (num < min || num > max) return m;
      const newVnd = computeNewValue(num * 1e3, rule);
      return String(Math.round(newVnd / 1e3));
    });
  }
  return out;
}
var URL_REGEX = /\b((?:https?:\/\/|www\.)[^\s<>()]+)/gi;
function transformLink(text, rule) {
  if (!rule || !rule.enabled) return text;
  const matchesDomain = (url) => {
    if (!rule.onlyDomains || rule.onlyDomains.length === 0) return true;
    return rule.onlyDomains.some((d) => url.toLowerCase().includes(String(d).toLowerCase()));
  };
  let out = text.replace(URL_REGEX, (m) => {
    if (!matchesDomain(m)) return m;
    if (rule.action === "replace") return rule.replaceWith || "";
    return "";
  });
  out = out.replace(/[ \t]{2,}/g, " ").replace(/[ \t]+\n/g, "\n").trim();
  return out;
}
function transformBrand(text, rule) {
  if (!rule || !rule.enabled) return text;
  let out = text;
  const flags = rule.caseInsensitive === false ? "g" : "gi";
  for (const [from, to] of Object.entries(rule.map || {})) {
    if (!from) continue;
    out = out.replace(new RegExp(escapeRegExp(from), flags), to);
  }
  return out;
}
function applyRules2(text, rules) {
  if (!rules) return text;
  let out = text || "";
  if (rules.brand) out = transformBrand(out, rules.brand);
  if (rules.price) out = transformPrice(out, rules.price);
  if (rules.link) out = transformLink(out, rules.link);
  if (Array.isArray(rules.custom)) {
    for (const c of rules.custom) {
      try {
        out = out.replace(new RegExp(c.pattern, c.flags || "g"), c.replaceWith);
      } catch (_e) {
      }
    }
  }
  if (rules.prependText) out = rules.prependText + out;
  if (rules.appendText) out = out + rules.appendText;
  return out;
}
module.exports = { transformPrice, transformLink, transformBrand, applyRules: applyRules2 };
