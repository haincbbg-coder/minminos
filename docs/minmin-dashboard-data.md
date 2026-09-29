# Số liệu cho Bảng điều hành MinMin OS

Bảng điều hành (cột trái màn chính, tab **Điều hành**) đọc một file JSON trong brain đang chọn:

```
00 - Dashboard/minmin-dashboard.json
```

Bảng KHÔNG tự bịa số. Chưa có file thì bảng hiện "Chưa có số liệu kinh doanh". Phần **Việc nền (sống)** thì luôn lấy thẳng từ `/kanban` và `/loops` nên không cần file này.

## Cách để MinMin tự cập nhật file

Nhắn MinMin trong khung chat, ví dụ:

> Đọc docs/minmin-dashboard-data.md, rồi tạo việc định kỳ mỗi giờ (08h-22h): lấy số từ POS và Meta Ads, ghi đè `00 - Dashboard/minmin-dashboard.json` đúng định dạng này. Không có nguồn nào thì bỏ trống mục đó, không bịa.

## Định dạng

```json
{
  "updated_at": "2026-09-29T11:00:00+07:00",
  "source": "Pancake POS + Meta Ads",
  "demo": false,
  "period_label": "tháng 9/2026",
  "target_month": 520000000,
  "kpis": [
    { "label": "Doanh thu hôm qua", "value": 19000000, "unit": "đ", "delta_pct": 6.4, "compare": "so tuần trước" },
    { "label": "Doanh thu tháng",   "value": 476200000, "unit": "đ", "delta_pct": 12.1, "compare": "cùng kỳ" },
    { "label": "Đơn hôm qua",       "value": 142, "unit": "", "delta_pct": -3.2, "compare": "so tuần trước" },
    { "label": "CPO",               "value": 38000, "unit": "đ", "delta_pct": 5.0, "compare": "7 ngày", "lower_is_better": true }
  ],
  "revenue_daily": [ { "date": "2026-09-01", "value": 15200000 } ],
  "forecast": null,
  "alerts": [ { "level": "critical", "text": "Mã D533 tồn 12, bán 9/ngày - hết sau ~1 ngày" } ],
  "projects": [
    { "name": "Kho số liệu HALIMI", "status": "running", "progress": 55, "next": "Duyệt định nghĩa doanh thu", "due": "05/10" }
  ]
}
```

| Trường | Ý nghĩa |
|---|---|
| `updated_at` | Giờ lấy số (ISO). Bảng hiện "Số liệu X phút trước". |
| `source` | Tên nguồn, hiện cạnh giờ cập nhật. |
| `demo` | `true` thì bảng dán nhãn vàng "DỮ LIỆU MẪU". Số thật phải để `false`. |
| `kpis` | Tối đa 4 ô. `unit`: `"đ"`, `"%"`, `"x"` hoặc chữ tuỳ ý. `lower_is_better: true` cho chỉ số càng thấp càng tốt (CPO, tỷ lệ hoàn). |
| `revenue_daily` | Doanh thu từng ngày trong tháng, cũ đến mới, `date` dạng `YYYY-MM-DD`. Dùng vẽ biểu đồ và tính dự báo. |
| `target_month` | Mục tiêu tháng (tuỳ chọn). Có thì hiện % dự báo so mục tiêu. |
| `forecast` | Để `null` thì bảng tự tính: doanh thu đã có + trung bình 7 ngày gần nhất × số ngày còn lại, biên dao động theo độ lệch chuẩn 14 ngày. Muốn tự đưa dự báo thì ghi `{ "month_end": 0, "low": 0, "high": 0, "note": "..." }`. |
| `alerts` | `level`: `good` / `warning` / `serious` / `critical` / `info`. Tối đa 5 dòng. |
| `projects` | `status`: `running` / `done` / `review` / `blocked` / `planned` / `paused`. `progress` 0-100. Tối đa 6 dự án. |

## Bật / tắt giao diện thiên hà

- Nút ✦ ở góc trên khoang não, hoặc link "Tắt thiên hà" cuối Bảng điều hành. Trạng thái nhớ theo trình duyệt.
- Người dùng bật "giảm chuyển động" trong hệ điều hành thì thiên hà đứng yên, không quay.
