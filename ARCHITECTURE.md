# 技术架构文档

## 项目结构

```text
stride28_search_mcp/
├── server.py          # MCP Server 入口、CLI 入口、tool handler
├── adapter.py         # 小红书浏览器搜索适配器
├── zhihu_adapter.py   # 知乎浏览器搜索适配器
├── lifecycle.py       # 生命周期、限流、风控冷却
├── state.py           # 数据目录、profile、headless 配置
└── models.py          # Pydantic 模型、ErrorCode、EnvelopeBuilder
```

## 架构概览

```text
MCP Client (Kiro / Cursor / Claude Code / Codex CLI)
    ↓ tool call (stdio)
server.py (FastMCP)
    ↓
小红书：先检查 risk cooldown
    ↓
RateLimiter.acquire(platform, tool_name)
    ↓
LifecycleManager
    ├── get_searcher()
    ├── destroy_searcher()
    ├── record/reset failures
    └── activate/get risk cooldown (xiaohongshu only)
    ↓
XhsBrowserSearcher / ZhihuBrowserSearcher
    ↓ Playwright persistent context
Chromium user_data_dir
    ↓
xiaohongshu.com / zhihu.com
    ↓
models.py / EnvelopeBuilder
    ↓
统一 JSON Envelope
```

## 平台状态与目录

### Profile 隔离

- `STRIDE28_SEARCH_MCP_PROFILE` 用于隔离不同客户端的浏览器持久化目录
- 未设置时仍走兼容模式：`shared_default`
- 已设置时目录为：
  - 小红书：`browser_data/profiles/<profile>/xhs`
  - 知乎：`browser_data/profiles/<profile>/zhihu`

这意味着 Kiro、Work Buddy、本地手测必须显式使用不同 profile，否则会共享登录态。

### Headless 策略

- 小红书默认：`STRIDE28_XHS_HEADLESS=false`
- 知乎默认：`STRIDE28_ZHIHU_HEADLESS=true`
- `STRIDE28_SEARCH_MCP_HEADLESS` 只作为兼容 fallback 保留

设计目标不是自动化体验最大化，而是优先降低小红书风险。

## 数据流

### 小红书搜索

1. `server.py` 收到 `search_xiaohongshu`
2. 先检查 `LifecycleManager.get_risk_cooldown("xiaohongshu")`
3. 若处于冷却期，直接返回 `risk_cooldown_active`
4. 调用 `RateLimiter.acquire("xiaohongshu", "search_xiaohongshu")`
5. `LifecycleManager.get_searcher("xiaohongshu")`
6. 直接导航到真实搜索页，不再先跳 `/explore` 做页面级认证预检
7. `search(query, limit, note_type)` 在真实搜索页上判断认证并读取 `__INITIAL_STATE__.search.feeds`
8. `_parse_feeds()` 过滤空标题并构造 `SearchResultItem`
9. 若结果为空：
   - 未登录 → `login_required`
   - 验证码 → `captcha_detected`
   - 登录有效但结构为空 → `search_blocked`
10. 命中 `captcha_detected` 或 `search_blocked` 后进入风控冷却

### 小红书笔记详情

1. `server.py` 收到 `get_note_detail`
2. 先检查小红书风控冷却
3. 统一限流
4. 直接导航到真实笔记页，不再先跳认证页
5. 在真实笔记页上判断认证并读取 `__INITIAL_STATE__.note.noteDetailMap`
6. 先提取首屏评论
7. 默认 `max_comments=10`，优先返回较少评论；只有显式请求更大值时才继续翻页
8. 评论加载命中硬停止条件即返回已获得评论

### 知乎搜索

1. 统一限流
2. `LifecycleManager.get_searcher("zhihu")`
3. `check_auth()` 通过 `z_c0` cookie 校验登录
4. 导航搜索页并拦截 `/api/v4/search_v3`
5. 从响应 JSON 解析搜索结果

### 知乎问题回答

1. 统一限流
2. 严格检查登录
3. 导航问题页
4. 从 DOM 提取问题描述与 Top N 回答
5. `max_content_length` 控制回答内容截断

## 关键设计决策

### 保守限流与抖动

- `login_xiaohongshu` / `login_zhihu` 在白名单中，不走限流
- 其他 tool 统一限流
- 默认 `STRIDE28_RATE_LIMIT_SECONDS=5.0`
- 小红书非登录工具额外增加 `0.5s-2.0s` 抖动

目的不是模拟真人，而是降低请求节奏、避免连续试探。

### 小红书严格认证

小红书不再使用通用 avatar DOM 作为登录成功信号，也不再把 `web_session` 视为强登录态。

内部使用结构化认证结果 `XhsAuthResult`：

- `logged_in`
- `source`
- `reason`
- `login_cookie_names`

当前按三层顺序判断：

- `selfinfo` 返回可解析且明确成功
- 命中白名单登录 cookie：`customer-sso-sid` / `galaxy_creator_session_id`
- 精确 DOM fallback：`.main-container .user .link-wrapper .channel`

这里的 DOM fallback 只保留为保守兜底，用的是登录后页面中的精确 selector，不再使用宽泛 avatar 类选择器。

### 风控冷却

小红书命中以下错误时进入冷却：

- `captcha_detected`
- `search_blocked`

默认冷却 15 分钟，可通过 `STRIDE28_XHS_RISK_COOLDOWN_SECONDS` 调整。冷却状态会持久化到当前 profile 的运行时状态目录。冷却期间：

- `search_xiaohongshu`
- `get_note_detail`

都会直接返回 `risk_cooldown_active`，不再继续试探页面。

### 统一错误信封

所有 tool 返回统一 Envelope：

```json
{
  "ok": false,
  "platform": "xiaohongshu",
  "tool": "search_xiaohongshu",
  "request_id": "uuid",
  "data": null,
  "error": {
    "code": "login_required",
    "message": "....",
    "retryable": false
  }
}
```

新增与风控相关的语义错误码：

- `captcha_detected`
- `search_blocked`
- `risk_cooldown_active`

### 可恢复性

支持显式清理状态：

- CLI：`stride28-search-mcp clear-state [xhs|zhihu|all]`
- Tools：`reset_xiaohongshu_login` / `reset_zhihu_login`

清理时会先销毁 searcher，再删除对应 profile/platform 浏览器目录，用于回到“首次用户”状态。

## `doctor` 自检内容

`stride28-search-mcp doctor` 用于统一排查环境与状态，输出至少包括：

- 当前 package 版本
- Python 版本
- `data_home`
- 当前 `profile`
- `profile_mode`
- `legacy_headless_fallback`
- `xhs_headless`
- `zhihu_headless`
- xhs/zhihu 浏览器数据目录
- xhs/zhihu cookie store 路径
- 小红书风控冷却状态

## 测试策略

### 设计原则

这个项目不再把“真实平台连续自动回归”当成默认测试手段。原因很直接：

- 小红书平台行为会变
- 自动化访问存在账号风险
- 登录态、无头模式、客户端环境会影响结果

因此测试收敛为三层：

### 第一层：离线回归

优先运行 `tests/`，覆盖：

- 单元测试
- Property-based tests
- 严格认证状态测试
- profile / headless 配置测试
- 风控冷却测试
- 搜索快照解析测试

这层应当覆盖绝大多数回归风险，不需要真实账号。

### 第二层：状态重置与本地自检

每次准备做真人工验证前：

```bash
stride28-search-mcp clear-state xhs
stride28-search-mcp doctor
```

确认：

- 当前是独立 profile
- 小红书是 `headless=false`
- cookie store 不存在或为空
- 没有激活中的风控冷却

### 第三层：低频人工 canary

只保留 1 个低频人工 canary 账号，用独立 profile 手动做最小验证：

1. `login_xiaohongshu`
2. `search_xiaohongshu`
3. `get_note_detail`

每次只做 1 轮，不做批量关键词压测，不做循环重试，不做定时自动化。

## 开发与运行

```bash
git clone https://github.com/BrunonXU/Stride28-search-mcp.git
cd Stride28-search-mcp
py -3.12 -m venv .test-venv
.test-venv\Scripts\activate
pip install -e .
playwright install chromium
pytest tests -q
python -m stride28_search_mcp.server doctor
```

## 当前边界

- 知乎当前按“必须先登录”收敛
- 小红书当前按“风险更低优先”收敛，不承诺 100% 成功率
- `uvx + WorkBuddy + 小红书搜索` 保留为实验性路径，不作为发布前必过项
