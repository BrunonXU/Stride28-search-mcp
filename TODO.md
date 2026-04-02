# TODO

## Mock-Based 集成测试（中优先级）

等 CI/CD 或开源发布时再补：
- R5 登录 fallback：mock `_page.evaluate` 失败 → fallback 到 DOM → fallback 到 Cookie
- R6/R10 captcha 检测：mock `_page.query_selector` 返回 captcha 元素 → 验证抛 CaptchaDetectedError
- R9 评论硬停止：mock `_extract_comments_from_dom` 模拟连续空加载 / selector 失效 / 超时

## BUG: uvx 环境下搜索返回空结果（高优先级）

现象：通过 `uvx stride28-search-mcp` 运行时，login 成功但 search 一直返回空结果（total_returned=0）。
本地源码版本（指向 venv312）正常。

疑似原因：`uvx` 安装的 Playwright 使用 `chrome-headless-shell` 而非完整 Chromium，
小红书可能检测到 headless shell 后不返回 `__INITIAL_STATE__` 数据。

排查方向：
- 对比 uvx 和本地 venv 的 Playwright 浏览器类型（headless shell vs full chromium）
- 检查 `__INITIAL_STATE__` 在 headless shell 下是否为空
- 考虑在 adapter.py 中强制使用完整 Chromium 而非 headless shell
- 这也是 WorkBuddy 上搜索返回空结果的根因

## P1 改进（下一阶段）

- adapter 内部分层（导航层 / 提取层 / 转换层）
- 时间字段语义统一（毫秒时间戳 → ISO 8601 或统一格式）
- 登录信号优先级配置化
- result builder 模式替代手动构造 SearchData/NoteDetail

## P2 改进（长期演进）

- 并发模型（多平台并行请求）
- 恢复机制（浏览器崩溃后自动重建 + 重试）
- browser-level 集成测试（Playwright 录制回放）
- metrics 采集（请求延迟、成功率、rate limiter 等待时间）
