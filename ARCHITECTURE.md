# 技术架构文档

## 项目结构

```
stride28_search_mcp/
├── server.py          # MCP Server 入口，6 个 tool handler
├── adapter.py         # 小红书浏览器搜索适配器
├── zhihu_adapter.py   # 知乎浏览器搜索适配器
├── lifecycle.py       # 搜索器生命周期管理 + RateLimiter
└── models.py          # Pydantic 数据模型 + ErrorCode + EnvelopeBuilder
```

## 架构概览

```
MCP Client (AI agent)
    ↓ tool call (stdio)
server.py (FastMCP)
    ↓ acquire()
RateLimiter (统一限流入口，login 白名单跳过)
    ↓
LifecycleManager (管理 searcher 实例的创建/销毁/故障计数)
    ↓ get_searcher()
XhsBrowserSearcher / ZhihuBrowserSearcher
    ↓ Playwright
Chromium → xiaohongshu.com / zhihu.com
    ↓
models.py → EnvelopeBuilder → JSON 响应
```

## 数据流

### 小红书搜索

1. `server.py` 收到 `search_xiaohongshu` tool call
2. `RateLimiter.acquire("xiaohongshu", "search_xiaohongshu")` — 非白名单，强制等待间隔
3. `LifecycleManager.get_searcher("xiaohongshu")` — 获取或创建 `XhsBrowserSearcher`
4. `check_auth()` — 三层 Fallback 登录检测（selfinfo API → DOM → Cookie）
5. `search(query, limit, note_type)` — 导航到搜索页，提取 `__INITIAL_STATE__`
6. `_parse_feeds(feeds, limit)` — 过滤空标题，提取 publish_time，构造 SearchResultItem
7. 空结果时 `_check_captcha()` — 检测验证码，有则抛 `CaptchaDetectedError`
8. `EnvelopeBuilder.success()` 或 `.error()` — 统一 JSON 信封返回

### 小红书笔记详情

1. 同上 1-4
2. `get_note_detail(note_id, xsec_token, max_comments)` — 导航到笔记页
3. 从 `__INITIAL_STATE__.note.noteDetailMap` 提取详情 + publish_time
4. 首屏评论从 JSON 提取，不够时 `_load_more_comments()` 翻页加载
5. 评论加载有三个硬停止条件：max_duration / max_empty_loads / max_selector_failures

### 知乎搜索

1. 同上限流 + 生命周期
2. `search(query, limit)` — 导航到搜索页，拦截 `/api/v4/search_v3` API 响应
3. 从拦截到的 JSON 解析搜索结果

### 知乎问题回答

1. 同上限流 + 生命周期
2. `get_question_answers(question_id, limit, max_content_length)` — 导航到问题页
3. JS evaluate 从 DOM 提取回答，`max_content_length` 控制截断

## 关键设计决策

### 统一限流入口（RateLimiter）

所有 tool handler 在获取 searcher 之前统一调用 `lifecycle.rate_limiter.acquire(platform, tool_name)`。handler 不自行判断是否需要限速。

白名单机制：`login_xiaohongshu` 和 `login_zhihu` 跳过限流，因为登录操作需要即时响应。

限流按平台隔离：小红书和知乎各自独立计时，互不影响。

### 统一错误信封（EnvelopeBuilder）

所有错误走同一个 `EnvelopeBuilder.error()` 方法，输出结构一致：

```json
{
  "ok": false,
  "platform": "...",
  "tool": "...",
  "request_id": "uuid",
  "data": null,
  "error": {"code": "...", "message": "...", "retryable": bool}
}
```

`retryable` 有默认映射表 `_RETRYABLE_MAP`，调用方可显式覆盖。

### 登录检测三层 Fallback

拆分为三个独立 try/except 块，每层失败不影响下一层。日志记录实际使用的检测方法（`selfinfo_api` / `dom_avatar` / `cookie_session`），便于排查。

### captcha 与空结果语义分离

搜索结果为空时必须检测 captcha。检测到 → 抛 `CaptchaDetectedError`（绝不伪装成空结果）。未检测到 → 返回正常空结果。`_check_captcha()` 内部异常返回 False（保守策略，不误报）。

### 评论翻页硬停止

防止浏览器自动化因 DOM 变化而无限卡住。三个独立条件任一触发即停止，返回已加载的评论。

## 从源码开发

```bash
git clone https://github.com/BrunonXU/Stride28-search-mcp.git
cd Stride28-search-mcp
py -3.12 -m venv .test-venv
.test-venv\Scripts\activate
pip install -e .
playwright install chromium
```

运行测试：

```bash
pip install hypothesis pytest pytest-asyncio
pytest tests/ -v
```

## 测试体系

- 11 个 Property-Based Tests（hypothesis，每个 100 次随机输入）
- 26 个单元测试（models / adapter / zhihu_adapter）
- 17 个 RateLimiter 测试

详见 `tests/` 目录。
