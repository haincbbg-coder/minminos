# Quy chuẩn giao diện MinMin - "Nổi mềm tinh gọn"

Đọc file này TRƯỚC khi làm trang hoặc thành phần giao diện mới cho MinMin (dashboard, HUD,
app phụ). Phong cách là phương án A "Nổi mềm tinh gọn", chủ repo chốt 2026-10-25.
Kế hoạch gốc: `plans/design-system/PLAN.md`. Token thật: `dashboard/surface-tokens.css`.

## Mục đích

- Mọi trang nhìn như một sản phẩm: cùng nền, cùng thang chữ, cùng bo góc, cùng khoảng cách.
- Một rule CSS chạy đúng cả hai tông (sáng và tối) vì chỉ gọi token, không gõ mã màu.
- Phiên Claude Code sau không phải đoán: chọn token có sẵn, không đẻ số mới.

## Hai tông

**Tông sáng (mặc định, `:root[data-theme="light"]`).** Mọi bề mặt cùng một nền kem
`#EFE9E2` (`--mm-bg`, `--mm-panel`, `--mm-field` đều bằng nhau), **không viền**. Thẻ và nút
NỔI lên bằng hai bóng: sáng phía trên trái, tối phía dưới phải. Ô nhập, mục đang chọn, nút
đang bấm LÕM xuống. Điểm nhấn là tím (`--mm-brand`).

**Tông tối (HUD và tuỳ chọn, `:root` không có `data-theme="light"`).** Bảng hổ phách
(`--mm-brand` = `#FF7A3C`) trên nền tím đêm. Bóng nổi mềm không hiện trên nền tối, nên thẻ
phẳng và có viền mảnh `--mm-line`.

Bạn không cần viết hai bộ rule: cùng tên token, mỗi tông tự gán giá trị riêng. Chỗ duy nhất
được tách theo tông là viền (xem "Quy tắc nổi/lõm").

## Bảng token

### Màu và bề mặt

| Token | Dùng cho |
|---|---|
| `--mm-bg` | nền trang |
| `--mm-panel` | nền thẻ, khối, menu |
| `--mm-field` | nền ô nhập |
| `--mm-text` | chữ chính |
| `--mm-muted` | chữ phụ, nút phụ |
| `--mm-dim` | chữ mờ nhất: nhãn nhỏ, chú thích, nút tắt |
| `--mm-line` | viền mảnh (chỉ tông tối), đường kẻ bảng |
| `--mm-brand` | màu nhấn: chấm, vạch đang chọn, `accent-color` |
| `--mm-link` | chữ link, chữ nhấn trên nền nhạt, vòng focus |
| `--mm-primary` | nền nút chính (dải màu) |
| `--mm-on-brand` | chữ trên `--mm-primary` / `--mm-brand` |
| `--mm-wash` | nền nhạt của mục đang chọn, ô tóm tắt |
| `--mm-row` | nền dòng xen kẽ, dòng hover |
| `--mm-scrim` | màn che sau hộp thoại |
| `--mm-ok` / `--mm-warn` / `--mm-bad` | trạng thái tốt / cần chú ý / lỗi |
| `--mm-font` | Be Vietnam Pro |

### Bóng (nổi và lõm)

| Token | Dùng cho |
|---|---|
| `--mm-out` | thẻ lớn, hộp thoại, nút khi hover |
| `--mm-out-sm` | nút thường, thẻ nhỏ |
| `--mm-out-xs` | chip, núm công tắc, nút tắt |
| `--mm-in` | vùng lõm lớn (khung chat, khung đồ thị) |
| `--mm-in-sm` | ô nhập, mục đang chọn, nút đang bấm, rãnh công tắc |
| `--mm-primary-shadow` | bóng riêng của nút chính |
| `--mm-hi` / `--mm-lo` | hai màu bóng sáng/tối, chỉ dùng khi cần tự ghép bóng đặc biệt |

### Cỡ chữ (Be Vietnam Pro)

| Token | px | Dùng cho |
|---|---|---|
| `--mm-fs-32` | 32 | tiêu đề trang |
| `--mm-fs-24` | 24 | số liệu chính (doanh thu, chi phí) |
| `--mm-fs-20` | 20 | tiêu đề khối |
| `--mm-fs-16` | 16 | tiêu đề thẻ |
| `--mm-fs-14` | 14 | chữ thường, tin nhắn chat |
| `--mm-fs-13` | 13 | chữ phụ, bảng, menu |
| `--mm-fs-12` | 12 | nhãn nhỏ |
| `--mm-fs-badge` | 10 | CHỈ huy hiệu đếm số (chấm đỏ trên chuông, số trên tab) |

### Bo góc

| Token | px | Dùng cho |
|---|---|---|
| `--mm-r-chip` | 8 | chip vuông, tag nhỏ |
| `--mm-r-btn` | 12 | nút, tab |
| `--mm-r-field` | 16 | ô nhập, vùng chữ |
| `--mm-r-card` | 22 | thẻ, khối, hộp thoại |
| `--mm-r-pill` | tròn | chip trạng thái, công tắc, nút tròn |

### Khoảng cách (bước 4px)

`--mm-sp-1` 4 · `--mm-sp-2` 8 · `--mm-sp-3` 12 · `--mm-sp-4` 16 · `--mm-sp-6` 24 ·
`--mm-sp-8` 32 · `--mm-sp-12` 48.

Gợi ý: khe giữa chữ và icon 8, đệm nút 8-12 dọc / 16 ngang, đệm thẻ 16-24, khe giữa các thẻ
16-24, khe giữa các khối lớn 32-48.

### Ngoại lệ được giữ số trần

- Cỡ chữ **dưới 10px** (nhãn trục đồ thị) hoặc **từ 30px trở lên** (số trang trí, emoji lớn).
- Bo **2-4px** (thanh mảnh, thanh tiến độ, thanh cuộn).

Ngoài hai trường hợp trên: không gõ số, chọn token gần nhất.

## Quy tắc nổi/lõm

- **Nổi** (`--mm-out*`): thứ bấm được hoặc chứa nội dung: thẻ, nút, chip, menu, hộp thoại.
- **Lõm** (`--mm-in*`): thứ nhận dữ liệu hoặc đang ở trạng thái "đã chọn": ô nhập, tab đang
  mở, mục menu đang chọn, nút đang bấm (`:active`, `.on`, `[aria-pressed="true"]`), rãnh công tắc.
- **Thẻ lồng trong thẻ** thì lõm (`--mm-in-sm`) cho có tầng, không nổi chồng nổi.
- Bóng to dần theo kích thước: chip `-xs`, nút `-sm`, thẻ không hậu tố.
- **Viền**: tông sáng `border: 0`; tông tối thêm `1px solid var(--mm-line)`. Viết viền một
  lần cho tông tối rồi gỡ ở tông sáng:

```css
.the-moi { border: 1px solid var(--mm-line); }
:root[data-theme="light"] .the-moi { border: 0; }
```

## Công thức thành phần

### Thẻ

```css
.the-moi {
  background: var(--mm-panel); color: var(--mm-text);
  border: 1px solid var(--mm-line); border-radius: var(--mm-r-card);
  box-shadow: var(--mm-out); padding: var(--mm-sp-6);
}
:root[data-theme="light"] .the-moi { border: 0; }
.the-moi h3 { font-size: var(--mm-fs-16); margin: 0 0 var(--mm-sp-3); }
```

### Nút chính

```css
.nut-chinh {
  background: var(--mm-primary); color: var(--mm-on-brand);
  border: 0; border-radius: var(--mm-r-btn); box-shadow: var(--mm-primary-shadow);
  font-size: var(--mm-fs-14); padding: var(--mm-sp-3) var(--mm-sp-4); min-height: 44px;
}
.nut-chinh:hover { filter: brightness(1.05); }
.nut-chinh:active { box-shadow: var(--mm-in-sm); }
```

Mỗi màn chỉ nên có MỘT nút chính.

### Nút phụ

```css
.nut-phu {
  background: var(--mm-panel); color: var(--mm-muted);
  border: 1px solid var(--mm-line); border-radius: var(--mm-r-btn);
  box-shadow: var(--mm-out-sm); font-size: var(--mm-fs-13);
  padding: var(--mm-sp-2) var(--mm-sp-3);
  transition: box-shadow .16s, color .16s;
}
:root[data-theme="light"] .nut-phu { border: 0; }
.nut-phu:hover { color: var(--mm-link); box-shadow: var(--mm-out); }
.nut-phu:disabled { color: var(--mm-dim); box-shadow: var(--mm-out-xs); opacity: .7; }
```

### Nút / tab / mục đang chọn

```css
:is(.nut-phu, .tab):is(:active, .on, [aria-pressed="true"], [aria-selected="true"]) {
  background: var(--mm-panel); color: var(--mm-link); box-shadow: var(--mm-in-sm);
}
```

Mục danh sách đang chọn: thêm vạch nhấn bên trái
`box-shadow: inset 3px 0 var(--mm-brand), var(--mm-in-sm); background: var(--mm-wash);`.

### Ô nhập

```css
.o-nhap {
  background: var(--mm-field); color: var(--mm-text);
  border: 1px solid var(--mm-line); border-radius: var(--mm-r-field);
  box-shadow: var(--mm-in-sm); font-size: var(--mm-fs-14);
  padding: var(--mm-sp-3) var(--mm-sp-4);
}
:root[data-theme="light"] .o-nhap { border-color: transparent; }
.o-nhap::placeholder { color: var(--mm-dim); }
.o-nhap:focus { outline: none; border-color: var(--mm-link); }
```

Ở tông sáng giữ `1px solid transparent` (không phải `border: 0`) để khi focus đổi màu viền
mà ô không nhảy kích thước.

### Chip trạng thái

Màu trạng thái làm CHỮ, nền là chính màu đó pha 10%:

```css
.chip-tt {
  display: inline-flex; align-items: center; gap: var(--mm-sp-1);
  font-size: var(--mm-fs-12); font-weight: 600; padding: 2px var(--mm-sp-2);
  border-radius: var(--mm-r-pill);
}
.chip-tt.ok   { color: var(--mm-ok);   background: color-mix(in srgb, var(--mm-ok) 10%, transparent); }
.chip-tt.warn { color: var(--mm-warn); background: color-mix(in srgb, var(--mm-warn) 10%, transparent); }
.chip-tt.bad  { color: var(--mm-bad);  background: color-mix(in srgb, var(--mm-bad) 10%, transparent); }
```

Không dùng `--mm-ok/warn/bad` làm nền đặc với chữ trắng: không đạt tương phản ở tông sáng.
Chip không phải trạng thái (tag, bộ lọc) thì nổi: `background: var(--mm-panel); box-shadow: var(--mm-out-xs);`.

### Công tắc

Rãnh lõm, núm nổi, bật thì núm thành màu chính:

```css
.cong-tac span {
  width: 44px; height: 24px; border-radius: var(--mm-r-pill);
  background: var(--mm-panel); box-shadow: var(--mm-in-sm);
}
.cong-tac span::before {
  border-radius: var(--mm-r-pill); background: var(--mm-panel); box-shadow: var(--mm-out-xs);
}
.cong-tac input:checked + span::before { background: var(--mm-primary); }
```

### Danh sách "Cần xử lý"

Một thẻ, mỗi dòng là một việc. Chấm màu trạng thái ở đầu, chữ chính, chữ phụ, nút hành động
phụ ở cuối. Dòng không có nền riêng, hover mới hiện `--mm-row`.

```css
.can-xu-ly { list-style: none; margin: 0; padding: 0; }
.can-xu-ly li {
  display: flex; align-items: center; gap: var(--mm-sp-3);
  padding: var(--mm-sp-3) var(--mm-sp-2); border-radius: var(--mm-r-btn);
}
.can-xu-ly li:hover { background: var(--mm-row); }
.can-xu-ly .cham { width: 8px; height: 8px; border-radius: var(--mm-r-pill); background: var(--mm-bad); }
.can-xu-ly .ten { font-size: var(--mm-fs-14); color: var(--mm-text); }
.can-xu-ly .phu { font-size: var(--mm-fs-12); color: var(--mm-dim); }
.can-xu-ly .nut-phu { margin-left: auto; }
```

Chấm dùng `--mm-bad` cho việc gấp, `--mm-warn` cho việc nên làm. Đừng tô cả dòng màu đỏ.

## Khả dụng

- Nút chính trên điện thoại cao **tối thiểu 44px** (`min-height: 44px`). Nút icon nhỏ thì nới
  vùng bấm bằng `padding`, không phóng icon.
- Chữ đạt tương phản **4.5:1** với nền. Các cặp token đã đạt: `--mm-text`, `--mm-muted`,
  `--mm-dim`, `--mm-link`, `--mm-ok/warn/bad` trên `--mm-bg` (đo 2026-10-25: thấp nhất 4.65 ở
  tông sáng); `--mm-on-brand` trên đầu đậm của `--mm-primary`. Đừng hạ thêm độ đậm bằng
  `opacity` cho chữ đọc được.
- Chưa đạt, cần biết: ở tông sáng chữ trạng thái trên nền pha 10% chỉ còn 4.1-4.4, và chữ
  trắng trên đầu nhạt của dải `--mm-primary` (`#8a6cf0`) chỉ 3.83. Chip trạng thái nên in đậm
  (`font-weight: 600`); xem mục "Còn nợ".
- Focus luôn thấy: `outline: 2px solid var(--mm-link); outline-offset: 3px;` cho
  `:focus-visible`.

## Nên / không nên

**Nên**
- Gọi token `--mm-*` cho màu, bóng, cỡ chữ, bo góc, khoảng cách.
- Viết rule một lần, chỉ tách theo tông khi gỡ viền ở tông sáng.
- Thử trang ở cả hai tông và ở bề ngang điện thoại trước khi báo xong.

**Không nên**
- Không gõ mã màu (`#fff`, `rgb(...)`) trong rule mới. Cần màu không có trong bảng thì hỏi
  chủ repo trước khi thêm token, đừng tự gõ.
- Không thêm cỡ chữ hay mức bo mới. Thiết kế đưa 15px thì dùng `--mm-fs-16`, bo 10px thì dùng
  `--mm-r-btn`.
- Không dùng `--mm-fs-badge` cho chữ thường: 10px chỉ dành cho huy hiệu đếm số.
- Không viền ở tông sáng: tách khối bằng bóng nổi/lõm.
- Không đặt `style="background:..."` inline trên `<button>`: style inline thắng `:hover` nên
  nút đứng im nền cũ khi rê chuột. Dùng class. `tests/python/test_theme_tokens.py` chặn lỗi này.
- Không chồng nổi lên nổi (thẻ trong thẻ đều nổi): lớp trong phải lõm.

## App phụ (HUD, hoá đơn, app riêng)

App chạy trong trang riêng nạp `dashboard/app-theme.css` (file này đã `@import`
`surface-tokens.css`) và gắn tên app lên `<body>`:

```html
<link rel="stylesheet" href="../app-theme.css">
<body data-mm-app="ten-app">
```

`body[data-mm-app]` tự lo nền, màu chữ, font, focus, thanh cuộn, `accent-color`. Rule riêng
của app thì viết trong `app-theme.css` dưới `[data-mm-app="ten-app"]` và vẫn chỉ gọi token.
App có bộ biến riêng (ví dụ `--nen`, `--chu` của app hoá đơn) thì nối biến đó về `--mm-*`
trong khối `body[data-mm-app="..."]`, đừng chép mã màu.

## Test giữ quy chuẩn

- `tests/python/test_design_tokens.py` chặn cỡ chữ và bo góc lạ quay lại trong vùng CSS đã
  chuẩn hoá (số trần nằm ngoài thang và ngoài ngoại lệ ở trên). Test đỏ thì đổi sang token,
  đừng nới test.
- `tests/python/test_theme_tokens.py` chặn nút gõ `background` inline và giữ các token màu.

## Còn nợ

- **CSS tiêm từ JS chưa chuẩn hoá.** Ví dụ `dashboard/console.js` tạo thẻ `<style>` bằng
  `document.createElement("style")` với số px và mã màu gõ cứng. Test token chưa quét các chuỗi
  này. Khi sửa đoạn đó, chuyển dần sang token.
- **Lớp màu cũ chưa gộp.** `style.css` vẫn có `--bg`, `--bg2`, `--accent`, `--text`, `--text2`...
  và `noi-mem.css` có `--nm-*` (đã nối về `--mm-*`). Code mới dùng `--mm-*`; việc gộp lớp cũ
  vào `--mm-*` để PR sau.
- **Tương phản tông sáng chưa trọn 4.5:1** ở chip trạng thái (chữ trên nền pha 10%) và đầu
  nhạt của nút chính. Cách sửa dự kiến: đậm thêm `--mm-ok/warn/bad` tông sáng một nấc, hoặc
  đổi đầu nhạt của `--mm-primary`. Việc này sửa token nên cần chủ repo duyệt.
- Một số chỗ cũ trong `noi-mem.css` còn ghi `color: #fff` và bóng tự ghép thay cho
  `--mm-on-brand` / `--mm-primary-shadow`.
