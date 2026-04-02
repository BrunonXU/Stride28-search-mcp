# TODO

## Mock-Based 集成测试（中优先级）

等 CI/CD 或开源发布时再补：
- R5 登录 fallback：mock `_page.evaluate` 失败 → fallback 到 DOM → fallback 到 Cookie
- R6/R10 captcha 检测：mock `_page.query_selector` 返回 captcha 元素 → 验证抛 CaptchaDetectedError
- R9 评论硬停止：mock `_extract_comments_from_dom` 模拟连续空加载 / selector 失效 / 超时

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
