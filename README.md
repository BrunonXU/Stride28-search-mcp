# Stride28 Search MCP

中文社区经验聚合搜索 MCP Server。让你的 AI 助手直接搜索小红书和知乎的真实内容。

> 这是 [Stride28](https://github.com/BrunonXU/XLearning-Agent) 智能学习平台的搜索模块，独立抽出来作为 MCP 工具。

## 功能

| Tool | 平台 | 说明 |
|------|------|------|
| `login_xiaohongshu` | 小红书 | 扫码登录，Cookie 持久化 |
| `search_xiaohongshu` | 小红书 | 关键词搜索笔记（标题/URL/作者/点赞/封面） |
| `get_note_detail` | 小红书 | 获取笔记详情（正文/评论/图片/互动数据） |
| `login_zhihu` | 知乎 | 手动登录（可选，搜索不需要登录） |
| `search_zhihu` | 知乎 | 关键词搜索（问答/专栏/视频） |
| `get_zhihu_question` | 知乎 | 获取问题 Top N 回答（需登录） |

## 技术方案

- **纯浏览器操作**：使用 Playwright 在浏览器内完成所有操作，不直接调用 API，零风控风险
- **小红书**：导航到搜索页 + 提取 `__INITIAL_STATE__` SSR 数据
- **知乎**：API 响应拦截（`/api/v4/search_v3`）+ DOM 提取回答
- **Cookie 持久化**：Playwright Persistent Context，登录一次后续自动使用

## 快速开始

### 安装

推荐使用 `uv` 或 `pipx`，一行搞定：

```bash
# uv（推荐）
uv tool install stride28-search-mcp

# 或 pipx
pipx install stride28-search-mcp
```

安装后需要确保 Playwright 浏览器已下载：

```bash
playwright install chromium
```

### 配置 MCP Client

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

如果用 `uvx` 免安装运行：

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

### 使用

跟 AI 助手说：

- "帮我搜小红书上的 RAG 面试题"
- "看看快手那篇面经的详细内容"
- "去知乎搜搜 Agent 开发相关的讨论"

AI 会自动调用对应的 MCP tool，首次使用小红书会弹出浏览器让你扫码登录。

### 从源码安装（开发用）

```bash
git clone https://github.com/BrunonXU/Stride28-search-mcp.git
cd Stride28-search-mcp
pip install -e .
playwright install chromium
```

## 项目结构

```
Stride28-search-mcp/
├── pyproject.toml                  # 打包配置
├── stride28_search_mcp/
│   ├── server.py                   # MCP Server 入口
│   ├── adapter.py                  # 小红书浏览器搜索适配器
│   ├── zhihu_adapter.py            # 知乎浏览器搜索适配器
│   ├── lifecycle.py                # 搜索器生命周期管理
│   └── models.py                   # 数据模型
└── browser_data/                   # Cookie 持久化（~/.stride28-search-mcp/）
```

## 注意事项

- 小红书需要扫码登录才能搜索，知乎搜索不需要登录
- 知乎获取问题详情（`get_zhihu_question`）需要登录
- 浏览器数据存储在 `~/.stride28-search-mcp/browser_data/`，不会污染项目目录
- 首次运行 `playwright install chromium` 会下载约 150MB 的浏览器

## 兼容的 MCP 客户端

- [Kiro](https://kiro.dev)
- [Cursor](https://cursor.sh)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [VS Code + Copilot](https://code.visualstudio.com/)
- 任何支持 MCP stdio transport 的客户端

## License

MIT
