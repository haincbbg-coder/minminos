(function(root) {
  "use strict";
  function filter(rows, level, query) {
    const q = String(query || "").normalize("NFC").toLocaleLowerCase("vi");
    return rows.filter(r => (!level || r.level === level) &&
      (!q || String(r.msg || "").normalize("NFC").toLocaleLowerCase("vi").includes(q)));
  }
  function cell(value) {
    let s = String(value == null ? "" : value);
    // Spreadsheet applications must treat message content as text, never a formula.
    if (/^[\s]*[=+@-]/.test(s) || /^[\t\r\n]/.test(s)) s = "'" + s;
    return '"' + s.replace(/"/g, '""') + '"';
  }
  function csv(rows) {
    return "\uFEFF" + [["Thời gian", "Mức độ", "Nội dung"], ...rows.map(r =>
      [new Date(r.ts).toISOString(), r.level, r.msg])].map(r => r.map(cell).join(",")).join("\r\n");
  }
  const api = {filter, csv};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ForwarderOperations = api;
})(typeof window !== "undefined" ? window : this);
