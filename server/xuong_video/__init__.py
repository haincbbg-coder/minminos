"""Xưởng video (kết nối ngoài): từ ý tưởng chữ/ảnh/video đến video hoàn chỉnh và đăng đa nền tảng.

Thiết kế riêng của MinMin, học cách làm của các dự án mã nguồn mở (FlowKit, DramaClaw,
OpenMontage...) nhưng KHÔNG dùng mã của chúng: hai trong số đó là AGPL, một là Elastic License.
Chạy trên máy chủ, không cần trình duyệt mở sẵn: gọi thẳng API của nhà cung cấp.

Các tầng (mỗi tầng một file, test riêng):
  kho        dự án, cảnh, trạng thái, file
  khoa       khoá API và kết nối nền tảng (mã hoá)
  ncc        nhà cung cấp tạo ảnh / video / giọng (fal.ai, Gemini, OpenAI, ElevenLabs)
  kich_ban   từ ý tưởng + tài liệu thành kịch bản và storyboard
  ghep       ghép cảnh, giọng, phụ đề bằng ffmpeg
  dang       đăng lên nền tảng (YouTube, Facebook Reels, ...)
  chay       dây chuyền chạy từng bước có điểm dừng, hàng loạt, lịch đăng
Không dùng ký tự em dash.
"""
