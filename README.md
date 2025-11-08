# ScopeTree - Phân tích & Đánh giá

Tài liệu này cung cấp phân tích chuyên sâu về kiến trúc, điểm mạnh, khoảng trống kỹ thuật và lộ trình phát triển của ScopeTree dựa trên mã nguồn hiện tại.

## 1. Cấu trúc & Định hướng phát triển

### Cấu trúc hiện tại
```
scopetree/
	cli.py              # CLI (Click + Rich), cấu hình/log/db tạm thời
	modules/            # Hệ module tác vụ
		base.py         # Lớp trừu tượng BaseModule
		subdomain.py    # Module liệt kê subdomain (async)
	tools/              # Trừu tượng hóa tool bên ngoài
		wrappers.py     # BaseTool + wrapper Subfinder
```

### Đánh giá kiến trúc
- Kiểu kiến trúc theo module, tách lớp `BaseModule` rõ ràng; dễ mở rộng module mới chỉ bằng kế thừa.
- Luồng thực thi bất đồng bộ (async) cho phép chạy song song nhiều tool → nền tảng tốt để scale.
- Lớp `BaseTool` chuẩn hóa kiểm tra cài đặt, chạy lệnh, xử lý timeout/lỗi ở mức cơ bản.
- Tuy nhiên, cấu hình và lưu trữ hiện là giả lập (in-memory, hardcoded) → mới ở mức nguyên mẫu (~25-30%).

### Định hướng phát triển đề xuất
- MVP (1-2 tháng):
  - Thay `SimpleConfig` bằng loader YAML có validate (schema, mặc định, override theo môi trường).
  - Thay `SimpleDB` bằng lớp persist (SQLite/JSONL) với chỉ mục đơn giản cho domain/subdomain.
  - Hoàn thiện module `subdomain` và thêm 2-3 module: DNS resolution, port scan (nmap/masscan), tech detection (httpx/wappalyzer-api).
  - Thêm test cơ bản (unit + integration nhẹ cho CLI/module).
- Production (3-4 tháng):
  - Cơ chế plugin cho tool bên ngoài, nạp động từ config.
  - Định dạng đầu ra: JSON, CSV, HTML report; xuất file theo job.
  - Lịch chạy, theo dõi tiến độ, resume job.
  - Docker hóa, lock phiên bản tool, script bootstrap môi trường.
- Scale (6+ tháng):
  - Backend DB (PostgreSQL) + hàng đợi (RQ/Celery) nếu cần phân tán.
  - REST API (FastAPI) và dashboard web.
  - Orchestrate đa mục tiêu, chia shard theo chương trình.

---

## 2. Điểm mạnh & Tiềm năng sản phẩm

### Nền tảng kỹ thuật nổi bật
- **Async-first**: `asyncio.gather` trong `modules/subdomain.py` cho phép mở rộng sang nhiều tool cùng lúc.
- **Module hóa**: `BaseModule` + phân quyền rõ ràng giữa module và layer tool.
- **Abstraction cho tool**: `BaseTool` gom logic kiểm tra cài đặt, chạy lệnh, timeout/lỗi.
- **UX CLI**: Click + Rich giúp trải nghiệm tốt, dễ mở rộng lệnh.

### Tình huống sử dụng
1. Bug bounty: tự động mở rộng scope, phát hiện subdomain mới theo lịch.
2. Red team: điều phối quy trình reconnaissance, lưu trữ dữ liệu tập trung.
3. Security team: giám sát bề mặt tấn công liên tục.
4. Pentest firm: chuẩn hóa quy trình, tái sử dụng kết quả, sinh báo cáo.

### Khác biệt so với các công cụ
- Amass/Subfinder: công cụ đơn nhiệm → ScopeTree là lớp dàn nhạc (orchestration) có thể kết hợp nhiều tool.
- Recon-ng: khung nặng, học tập cao → ScopeTree nhẹ, async, dễ tích hợp dần.
- Script tự viết: khó bảo trì → ScopeTree chuẩn hóa, module hóa, dễ cắm thêm.

---

## 3. Khoảng trống cần cải thiện ngay

### Critical (chặn MVP)
1) Hệ cấu hình chưa thực (hardcoded):

```12:16:/home/kali/Desktop/ScopeTree/scopetree/cli.py
class SimpleConfig:
    def get(self, key, default=None):
        return True  # Enable subfinder by default
```

- Hệ quả: mọi khóa `tools.*.enabled` luôn bật; không có timeout/config theo tool; không có profile theo môi trường.
- Khuyến nghị: Loader YAML + schema (pydantic/yamale), hỗ trợ env override, mặc định an toàn.

2) Dữ liệu không bền vững (in-memory):

```18:31:/home/kali/Desktop/ScopeTree/scopetree/cli.py
class SimpleDB:
    def __init__(self):
        self.domains_list = []
    ...
    def add_domains(self, domains, source='passive'):
        ...
```

- Hệ quả: mất dữ liệu sau mỗi lần chạy, không có metadata nguồn/thời gian.
- Khuyến nghị: SQLite (đơn giản, portable) hoặc JSONL theo job với index nhẹ.

3) Thiếu xử lý lỗi/validation:
- CLI chưa validate domain; chưa bắt lỗi công cụ thiếu/cú pháp sai.
- Khi tool lỗi/timeout, `BaseTool` trả rỗng nhưng chưa có chiến lược retry hay phân loại lỗi.
- Khuyến nghị: validate đầu vào (validators), try/except ở lệnh, phân loại lỗi tool (install/timeout/exitcode).

4) Chưa có test:
- Không có unit/integration test; rủi ro hồi quy cao khi thêm module.
- Khuyến nghị: pytest + tests cho `BaseTool`, `Subfinder`, `Subdomain.execute`, và CLI.

### Important (trước production)
5) Phụ thuộc chưa dùng/thiếu quản lý:
- `aiohttp` được import trong `tools/wrappers.py` nhưng chưa sử dụng.
- Cần tệp quản lý phụ thuộc (poetry/pip-tools) và cleanup imports.

6) Giá trị hardcode:

```21:28:/home/kali/Desktop/ScopeTree/scopetree/modules/subdomain.py
tools = []
if self.config.get('tools.subfinder.enabled'):
    tools.append(Subfinder(self.logger))
results = await asyncio.gather(*tasks, return_exceptions=True)
```

- Danh sách tool và timeout nên lấy từ cấu hình; hỗ trợ bật/tắt từng tool, tham số riêng.

7) Logging cơ bản:
- Logger cấu hình trực tiếp trong `cli.py`, chưa có cấu hình file/rotation/level theo môi trường.
- Khuyến nghị: `logging.config.dictConfig` với console + file handler, rotation theo dung lượng.

8) Tài liệu/DOCSTRING còn thiếu:
- Thiếu docstring chuẩn và ví dụ sử dụng; thiếu sơ đồ kiến trúc/lưu đồ chạy.

### Quick wins (1-2 ngày)
- Thêm validation domain tại CLI `subdomain` và thông báo lỗi rõ ràng.
- Phát hiện tool vắng mặt một cách mềm dẻo (skip thay vì lỗi cứng).
- Tạo `config.yaml` tối thiểu với tool enable/timeout và backend lưu trữ.
- Chuẩn hóa logging và tách khỏi `cli.py`.

Ví dụ cấu hình tối thiểu:

```yaml
tools:
  subfinder:
    enabled: true
    timeout: 180
database:
  type: sqlite
  path: ./scopetree.db
logging:
  level: INFO
```

Ví dụ phát hiện tool mềm dẻo:

```python
if not shutil.which('subfinder'):
    logger.warning('subfinder not found, skipping')
    return []
```

---

## 4. Khuyến nghị triển khai chi tiết (ngắn gọn)
- Cấu hình: `pydantic-settings` đọc YAML + ENV; schema versioning.
- Lưu trữ: lớp `Storage` (interface) với `JsonStorage` (MVP) và `SqliteStorage` (prod-ready).
- Tool registry: nạp tool từ config bằng tên lớp và tham số, validate `is_installed()` trước khi chạy.
- Thực thi: gom job theo domain, `asyncio.gather` với `return_exceptions=True`, retry có backoff cho lỗi tạm.
- Logging: dictConfig, console + file (rotation), correlation-id theo job.
- Test: mock `create_subprocess_exec` để không phụ thuộc tool thật.

---

## 5. Hướng dẫn nhanh (tạm thời với mã hiện tại)
1) Cài đặt tool bên ngoài cần thiết (ví dụ `subfinder`).
2) Chạy lệnh liệt kê subdomain:

```bash
python -m scopetree.cli subdomain -d example.com
```

Lưu ý: Dữ liệu hiện chỉ ở bộ nhớ tạm và cấu hình đang hardcode; kết quả sẽ không được lưu qua lần chạy khác.

---

## 6. Lộ trình ưu tiên
1. Cấu hình YAML + lưu trữ bền vững (1 tuần).
2. Xử lý lỗi + validation đầu vào (2-3 ngày).
3. Bộ test cơ bản (1 tuần).
4. Hoàn thiện tài liệu (2-3 ngày).
5. Mở rộng module (DNS, port scan, tech detection).

---

## 7. Kết luận
- Tiềm năng cao nhờ nền tảng async, module hóa, và lớp trừu tượng tool phù hợp.
- Rủi ro kỹ thuật sẽ tích lũy nhanh nếu không xử lý sớm cấu hình/lưu trữ/test.
- Nên ưu tiên thay `SimpleConfig` và `SimpleDB` trước khi mở rộng thêm module.
