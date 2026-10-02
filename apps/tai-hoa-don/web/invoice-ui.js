/* Pure date/filter helpers, shared by both invoice tables. */
(function (root) {
  "use strict";
  function iso(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2,"0") + "-" + String(d.getDate()).padStart(2,"0"); }
  function period(id, year, now) {
    var end = new Date(now || new Date()), start = new Date(end);
    var y = Number(year) || end.getFullYear(), m = end.getMonth();
    if (id === "all") return ["", ""];
    if (/^m\d+$/.test(id)) { m = Number(id.slice(1)) - 1; start = new Date(y,m,1); end = new Date(y,m+1,0); }
    else if (/^q[1-4]$/.test(id)) { m = (Number(id.slice(1))-1)*3; start = new Date(y,m,1); end = new Date(y,m+3,0); }
    else if (id === "h1" || id === "h2") { m = id === "h1" ? 0 : 6; start = new Date(y,m,1); end = new Date(y,m+6,0); }
    else if (id === "year") { start = new Date(y,0,1); end = new Date(y,11,31); }
    else if (id === "yesterday") { start.setDate(start.getDate()-1); end = new Date(start); }
    else if (/^last(7|30|90)$/.test(id)) start.setDate(start.getDate()-Number(id.slice(4))+1);
    else if (id === "lastmonth") { start = new Date(end.getFullYear(),m-1,1); end = new Date(end.getFullYear(),m,0); }
    else if (id === "week") start.setDate(start.getDate()-(start.getDay()+6)%7);
    else if (id === "month") start.setDate(1);
    return [iso(start),iso(end)];
  }
  function text(v) { return String(v || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g,"d").replace(/Đ/g,"D").toLowerCase(); }
  function date(r) {
    if (r.ngay || r.ngay_hd) return (r.ngay || r.ngay_hd).slice(0,10);
    var d = new Date(r.ngay_mail || ""); return isNaN(d) ? "" : iso(d);
  }
  function seller(r) { return r.doi_tac || r.ban_ten || r.tu || ""; }
  function hasFile(r, type) {
    if (type === "xml") return !!r.co_xml;
    if (type === "original") return !!r.co_goc;
    if (type === "tax") return !!r.co_trong_dong;
    return false;
  }
  function matchesFile(r, value) {
    if (!value) return true;
    if (value === "pdf") return !!(r.co_pdf || r.co_goc);
    if (value === "missing") return !r.co_pdf && !r.co_goc;
    var missing = value.indexOf("no-") === 0;
    var type = missing ? value.slice(3) : value;
    return missing ? !hasFile(r, type) : hasFile(r, type);
  }
  function filter(rows, f) {
    var q = text(f.q), supplier = text(f.supplier), number = text(f.number);
    var out = rows.filter(function(r) {
      var d = date(r), amount = Number(r.tong || 0);
      return (!f.from || d && d >= f.from) && (!f.to || d && d <= f.to) &&
        (!q || text([seller(r),r.mst_doi_tac,r.ban_mst,r.so,r.ky_hieu,r.nha_cung_cap].join(" ")).includes(q)) &&
        (!supplier || text(seller(r) + " " + (r.mst_doi_tac || r.ban_mst || "")).includes(supplier)) &&
        (!number || text(r.so).includes(number)) &&
        (!f.publisher || (r.nha_cung_cap || "unknown") === f.publisher) &&
        (!f.status || (f.status === "manual" ? r.can_tai_tay : r.goc_trang_thai ? r.goc_trang_thai === f.status : f.status === "done" && !r.can_tai_tay)) &&
        (f.min === "" || f.min == null || amount >= Number(f.min)) &&
        (f.max === "" || f.max == null || amount <= Number(f.max)) &&
        matchesFile(r, f.file);
    });
    var pair = (f.sort || "date-desc").split("-"), field = pair[0], dir = pair[1] === "asc" ? 1 : -1;
    return out.sort(function(a,b) {
      var x = field === "amount" ? Number(a.tong || 0) : field === "name" ? seller(a) : field === "number" ? a.so : date(a);
      var y = field === "amount" ? Number(b.tong || 0) : field === "name" ? seller(b) : field === "number" ? b.so : date(b);
      return dir * (field === "amount" ? x-y : String(x || "").localeCompare(String(y || ""),"vi",{numeric:true}));
    });
  }
  var api = {period:period,filter:filter,date:date};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.InvoiceUI = api;
})(typeof window !== "undefined" ? window : this);
