<p align="center">
  <img src="https://raw.githubusercontent.com/BrunonXU/Stride28/main/docs/assets/logo.svg" width="280" alt="Stride28" />
</p>

<h3 align="center">Search MCP</h3>

<p align="center">
  中文社区经验聚合搜索 MCP Server — 让 AI 助手直接搜索小红书和知乎的真实内容
</p>

<p align="center">
  <a href="https://pypi.org/project/stride28-search-mcp/">
    <img src="https://img.shields.io/pypi/v/stride28-search-mcp?color=D97757" alt="PyPI" />
  </a>
  <a href="https://github.com/BrunonXU/Stride28-search-mcp/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/BrunonXU/Stride28-search-mcp" alt="License" />
  </a>
  <img src="https://img.shields.io/pypi/pyversions/stride28-search-mcp" alt="Python" />
</p>

<p align="center">
  <a href="#使用场景">使用场景</a> · <a href="#安装">安装</a> · <a href="#配置">配置</a> · <a href="#可用-tool">Tool 参考</a> · <a href="#错误码">错误码</a>
</p>

---

> 这是 [Stride28](https://github.com/BrunonXU/Stride28) 智能学习平台的搜索模块，独立抽出来作为 MCP 工具。

## 演示

### Kiro + MCP 搜索

<p align="center">
  <img src="assets/kiro-ques1.png" width="700" alt="Kiro 搜索演示" />
</p>

<p align="center">
  <img src="assets/kiro-ques2.png" width="700" alt="Kiro 搜索演示" />
</p>

### WorkBuddy + MCP 自动化（即将推出）

> 一键爬取小红书/知乎内容 → 接入腾讯文档/飞书文档自动整理 → 配合 Claw 实现每日自动化拉取、分类归档、摘要生成。

<!-- 替换为实际截图/GIF
<p align="center">
  <img src="assets/workbuddy-crawl.gif" width="700" alt="WorkBuddy 一键爬取 + 文档整理" />
</p>
<p align="center">
  <img src="assets/claw-daily-auto.gif" width="700" alt="Claw 每日自动化拉取 + 归档" />
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

Python 3.10+

```bash
# uv（推荐）
uv tool install stride28-search-mcp

# 或 pipx
pipx install stride28-search-mcp
```

安装浏览器：

```bash
stride28-search-mcp install-browser
```

## 配置

在 MCP 客户端配置中添加：

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

建议为不同客户端显式设置不同的 `STRIDE28_SEARCH_MCP_PROFILE`，不要共用默认 profile。否则 Kiro、Work Buddy、本地手测会复用同一份 Chromium 持久化目录，导致“没扫码却像是已经登录”的假象。

Kiro 示例：

```json
{
  "mcpServers": {
    "stride28-search": {
      "command": "uvx",
      "args": ["stride28-search-mcp"],
      "env": {
        "STRIDE28_SEARCH_MCP_PROFILE": "kiro"
      },
      "disabled": false
    }
  }
}
```

Work Buddy 示例：

```json
{
  "mcpServers": {
    "stride28-search": {
      "command": "uvx",
      "args": ["stride28-search-mcp"],
      "env": {
        "STRIDE28_SEARCH_MCP_PROFILE": "workbuddy"
      },
      "disabled": false
    }
  }
}
```

<details>
<summary>用 uvx 免安装运行</summary>

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

</details>

兼容：[Kiro](https://kiro.dev) · [Cursor](https://cursor.sh) · [Claude Code](https://docs.anthropic.com/en/docs/claude-code) · [VS Code + Copilot](https://code.visualstudio.com/) · 任何支持 MCP stdio transport 的客户端

<details>
<summary><strong>可用 Tool</strong></summary>

| Tool | 平台 | 说明 |
|------|------|------|
| `login_xiaohongshu` | 小红书 | 扫码登录，Cookie 持久化 |
| `search_xiaohongshu` | 小红书 | 关键词搜索，支持图文/视频过滤 |
| `get_note_detail` | 小红书 | 笔记详情 + 评论翻页 + 发布时间 |
| `login_zhihu` | 知乎 | 手动登录 |
| `reset_xiaohongshu_login` | 小红书 | 清空当前 profile 的登录态 |
| `search_zhihu` | 知乎 | 关键词搜索（问答/专栏/视频） |
| `get_zhihu_question` | 知乎 | Top N 回答，内容长度可配置 |
| `reset_zhihu_login` | 知乎 | 清空当前 profile 的登录态 |

### search_xiaohongshu

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | string | 必填 | 搜索关键词 |
| `limit` | int | 10 | 返回条数 |
| `note_type` | string | `"all"` | `"all"` / `"normal"` / `"video"` |

### get_note_detail

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `note_id` | string | 必填 | 笔记 ID |
| `xsec_token` | string | `""` | 安全 token |
| `max_comments` | int | 50 | 最大评论数 |

### get_zhihu_question

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `question_id` | string | 必填 | 问题 ID |
| `limit` | int | 5 | 回答数 |
| `max_content_length` | int | 10000 | 最大字符数，`0` = 不截断 |

</details>

<details>
<summary><strong>错误码</strong></summary>

所有错误返回统一 JSON，包含 `retryable` 字段供 agent 判断是否重试。

| 错误码 | 含义 | 可重试 | 怎么办 |
|--------|------|:------:|--------|
| `login_required` | 未登录 | ✗ | 调用 login tool |
| `login_timeout` | 登录超时 | ✓ | 重新登录 |
| `search_timeout` | 搜索超时 | ✓ | 稍后重试 |
| `search_blocked` | 搜索结果异常为空 | ✗ | 检查无头模式、风控或重新登录 |
| `browser_init_failed` | 浏览器启动失败 | ✗ | `stride28-search-mcp install-browser` |
| `browser_crashed` | 浏览器崩溃 | ✗ | 重启 MCP Server |
| `captcha_detected` | 验证码拦截 | ✗ | 等待后重试 |
| `unknown_error` | 未知错误 | ✗ | 查看日志 |

</details>

<details>
<summary><strong>环境变量</strong></summary>

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STRIDE28_SEARCH_MCP_HOME` | `~/.stride28-search-mcp` | 数据目录 |
| `STRIDE28_SEARCH_MCP_PROFILE` | `""` | 浏览器 profile 名；为空时走兼容模式，共享默认目录，不推荐 |
| `STRIDE28_SEARCH_MCP_HEADLESS` | `true` | 非登录场景是否无头运行；疑难环境可设为 `false` 排查 |
| `STRIDE28_RATE_LIMIT_SECONDS` | `2.0` | 请求最小间隔（秒） |

</details>

## 首次测试建议

先确认环境：

```bash
stride28-search-mcp doctor
```

如果你要回到“新用户第一次安装”的状态：

```bash
stride28-search-mcp clear-state xhs
stride28-search-mcp clear-state zhihu
```

或一次清空全部：

```bash
stride28-search-mcp clear-state all
```

推荐测试顺序：

1. 为当前客户端设置独立 `STRIDE28_SEARCH_MCP_PROFILE`
2. 运行 `stride28-search-mcp doctor`，确认 profile、浏览器目录、cookie 库路径正确
3. 先调用 `login_xiaohongshu`，不扫码时不应返回成功
4. 再调用 `search_xiaohongshu`，未登录时必须返回 `login_required`
5. 完成登录后再次搜索，若仍空结果会明确返回 `search_blocked` 或 `captcha_detected`
6. 知乎同理，先 `login_zhihu` 再 `search_zhihu`

## 开发

详见 [ARCHITECTURE.md](ARCHITECTURE.md)

## License

MIT
