# Stride28 Search MCP

<p align="center">
  <strong>中文社区经验聚合搜索 MCP Server</strong><br>
  让你的 AI 助手直接搜索小红书和知乎的真实内容
</p>

> [Stride28](https://github.com/BrunonXU/XLearning-Agent) 智能学习平台的搜索模块，独立抽出来作为 MCP 工具。

## 演示

<p align="center">
  <img src="assets/kiro-ques1.png" width="700" alt="Kiro 搜索演示 1" />
</p>

<p align="center">
  <img src="assets/kiro-ques2.png" width="700" alt="Kiro 搜索演示 2" />
</p>

<!-- TODO: 更多演示
<p align="center">
  <img src="assets/workbuddy-demo.gif" width="700" alt="WorkBuddy MCP + 一键爬取接入腾讯/飞书文档" />
</p>

<p align="center">
  <img src="assets/auto-crawl-demo.gif" width="700" alt="配合 Claw 每日自动化拉取 + 整理" />
</p>
-->

## 使用场景

跟 AI 助手说：

- "帮我搜小红书上关于 RAG 的面试题"
- "看看那篇笔记的详细内容和评论"
- "去知乎搜搜 Agent 开发相关的讨论"
- "只搜小红书的视频笔记"
- "获取知乎这个问题的完整回答，不要截断"

AI 会自动调用对应的 MCP tool。首次使用时会弹出浏览器让你完成登录。

## 安装

需要 Python 3.10+。

```bash
# uv（推荐）
uv tool install stride28-search-mcp

# 或 pipx
pipx install stride28-search-mcp
```

安装 Playwright 浏览器：

```bash
stride28-search-mcp install-browser
```

## 配置 MCP Client

在你的 AI 客户端（Kiro / Cursor / Claude Code / VS Code）的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "stride28-search": {
      "command": "stride28-search-mcp",
      "disabled": false
    }
  }
}
```

用 `uvx` 免安装运行：

```json
{
  "mcpServers": {
    "stride28-search": {
      "command": "uvx",
      "args": ["stride28-search-mcp"],
      "disabled": false
    }
  }
}
```

## 可用 Tool

| Tool | 平台 | 说明 |
|------|------|------|
| `login_xiaohongshu` | 小红书 | 扫码登录，Cookie 持久化 |
| `search_xiaohongshu` | 小红书 | 关键词搜索笔记，支持图文/视频类型过滤 |
| `get_note_detail` | 小红书 | 获取笔记详情（正文/评论翻页/图片/互动数据/发布时间） |
| `login_zhihu` | 知乎 | 手动登录 |
| `search_zhihu` | 知乎 | 关键词搜索（问答/专栏/视频） |
| `get_zhihu_question` | 知乎 | 获取问题 Top N 回答，内容长度可配置 |

### search_xiaohongshu 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | string | 必填 | 搜索关键词 |
| `limit` | int | 10 | 返回条数（建议 10-20） |
| `note_type` | string | `"all"` | `"all"` / `"normal"`（图文）/ `"video"` |

### get_note_detail 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `note_id` | string | 必填 | 笔记 ID（从搜索结果获取） |
| `xsec_token` | string | `""` | 安全 token（从搜索结果获取） |
| `max_comments` | int | 50 | 最大评论获取数量 |

### get_zhihu_question 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `question_id` | string | 必填 | 问题 ID（从搜索结果的 `xsec_token` 字段获取） |
| `limit` | int | 5 | 返回回答数 |
| `max_content_length` | int | 10000 | 每条回答最大字符数，`0` = 不截断 |

## 错误码

所有错误返回统一 JSON 格式，包含 `retryable` 字段供 agent 判断是否自动重试。

| 错误码 | 含义 | 可重试 | 建议操作 |
|--------|------|--------|----------|
| `login_required` | 未登录或 Cookie 失效 | ✗ | 调用对应的 login tool |
| `login_timeout` | 登录超时（5 分钟） | ✓ | 重新登录 |
| `search_timeout` | 搜索/获取超时 | ✓ | 稍后重试 |
| `browser_init_failed` | 浏览器启动失败 | ✗ | 执行 `stride28-search-mcp install-browser` |
| `browser_crashed` | 浏览器崩溃 | ✗ | 重启 MCP Server |
| `captcha_detected` | 被验证码拦截 | ✗ | 等待后重试或手动处理 |
| `unknown_error` | 未知错误 | ✗ | 查看 server 日志 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STRIDE28_SEARCH_MCP_HOME` | `~/.stride28-search-mcp` | 数据目录（浏览器 Cookie 等） |
| `STRIDE28_RATE_LIMIT_SECONDS` | `2.0` | 同平台请求最小间隔（秒） |

## 常见问题

- **返回 `browser_init_failed`** → 执行 `stride28-search-mcp install-browser`
- **返回 `login_required`** → 调用 `login_xiaohongshu` 或 `login_zhihu`
- **返回 `captcha_detected`** → 请求太频繁被风控，等几分钟再试
- **搜索结果为空** → 正常情况，确实没有匹配内容（已自动排除验证码拦截的情况）

## 环境自检

```bash
stride28-search-mcp doctor
```

## 兼容的 MCP 客户端

[Kiro](https://kiro.dev) • [Cursor](https://cursor.sh) • [Claude Code](https://docs.anthropic.com/en/docs/claude-code) • [VS Code + Copilot](https://code.visualstudio.com/) • 任何支持 MCP stdio transport 的客户端

## 开发

详见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## License

MIT
