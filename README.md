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

### 1. 安装

```bash
git clone https://github.com/BrunonXU/Stride28-search-mcp.git
cd Stride28-search-mcp
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 MCP Client

在你的 AI 客户端（Kiro / Cursor / Claude Code / VS Code）的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "stride28-search": {
      "command": "/path/to/Stride28-search-mcp/.venv/bin/python",
      "args": ["/path/to/Stride28-search-mcp/mcp_server.py"],
      "disabled": false
    }
  }
}
```

Windows 用户把路径改成：
```json
{
  "command": "C:\\path\\to\\Stride28-search-mcp\\.venv\\Scripts\\python.exe",
  "args": ["C:\\path\\to\\Stride28-search-mcp\\mcp_server.py"]
}
```

### 3. 使用

跟 AI 助手说：

- "帮我搜小红书上的 RAG 面试题"
- "看看快手那篇面经的详细内容"
- "去知乎搜搜 Agent 开发相关的讨论"

AI 会自动调用对应的 MCP tool，首次使用小红书会弹出浏览器让你扫码登录。

## 项目结构

```
Stride28-search-mcp/
├── mcp_server.py           # MCP Server 入口（stdio transport）
├── src/mcp/
│   ├── adapter.py          # 小红书浏览器搜索适配器
│   ├── zhihu_adapter.py    # 知乎浏览器搜索适配器
│   ├── lifecycle.py        # 搜索器生命周期管理
│   └── models.py           # 数据模型（Envelope/SearchResult/NoteDetail）
├── requirements.txt
└── browser_data/            # Cookie 持久化目录（自动创建，已 gitignore）
```

## 注意事项

- 小红书需要扫码登录才能搜索，知乎搜索不需要登录
- 知乎获取问题详情（`get_zhihu_question`）需要登录
- `browser_data/` 目录存储登录 Cookie，不要提交到 git
- 首次运行 `playwright install chromium` 会下载约 150MB 的浏览器

## 兼容的 MCP 客户端

- [Kiro](https://kiro.dev)
- [Cursor](https://cursor.sh)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [VS Code + Copilot](https://code.visualstudio.com/)
- 任何支持 MCP stdio transport 的客户端

## License

MIT
