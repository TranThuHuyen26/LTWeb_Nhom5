# LexiVault Pro - Gemini + Pronunciation Setup

## Tính năng đã thêm
- Chatbot dùng Gemini API để trả lời câu hỏi người dùng.
- Hỗ trợ tra cứu và dịch giữa tiếng Việt, tiếng Anh, tiếng Hàn, tiếng Nhật.
- Tự nhận biết ngôn ngữ trả lời: người dùng hỏi muốn trả lời bằng ngôn ngữ nào thì bot sẽ trả lời bằng ngôn ngữ đó.
- Chat trả về thêm metadata phát âm: từ chính, IPA, native script, romanization, câu ví dụ.
- Nút `🔊` trong khung chat gọi Gemini TTS để đọc từ/câu tiếng Anh rõ hơn.
- Các nút phát âm chính trong app được ưu tiên gọi backend `/api/pronounce`; nếu Gemini TTS không sẵn sàng thì tự fallback sang giọng đọc của trình duyệt.
- `.env` đã được làm sạch, không kèm khóa bí mật.

## Biến môi trường cần có
```env
GEMINI_API_KEY=your_google_ai_studio_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_API_VERSION=v1beta
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
GEMINI_TTS_VOICE=Kore
```

## Chạy app
```bash
pip install -r requirements.txt
python app.py
```

## Gợi ý sử dụng
- Vào `/chat` để hỏi nghĩa từ, dịch Việt -> Anh/Hàn/Nhật, IPA, ví dụ và nhấn `🔊 Đọc từ chính`.
- Có thể dùng các prompt như: `Từ quả táo sang tiếng Nhật`, `Explain 감사합니다 in English`, `Translate xin chào to Korean with pronunciation`.
- Nếu chưa cấu hình `GEMINI_API_KEY`, chatbot vẫn chạy demo/local mode.
- Muốn đổi giọng TTS, sửa `GEMINI_TTS_VOICE` trong `.env`.

## File đã sửa chính
- `app.py`
- `templates/chat.html`
- `templates/base.html`
- `templates/daily.html`
- `templates/review.html`
- `static/js/pronounce.js`
- `static/js/study.js`
