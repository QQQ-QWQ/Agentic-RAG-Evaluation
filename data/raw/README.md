# data/raw — 知识库原文与附加材料

## 系统知识库（会进入 Chroma）

下列子目录中的文件由 **`main.py kb sync`** 自动扫描，写入 `data/processed/documents.csv` 并向量化为全库索引（持久化在 `.env` 的 `CHROMA_PERSIST_DIRECTORY`）：

- `tech_docs/` — 框架/平台文档
- `learning_docs/` — 论文、博客、学习材料
- `lab_docs/` — 实验室规范
- `tables_csv/` — 表格类 CSV
- `code_snippets/` — 代码片段

**不会**被系统 sync 扫描的目录：

- `session_upload/` — 用户会话附加文件（仅当次临时索引）
- `user_docs/` — 历史客户端复制目录（已弃用为全库来源）
- `web_snapshots/` — Firecrawl 网页快照（由工具按需处理）

## 维护命令

```powershell
# 干净重启：清空 Chroma + 按 raw 系统目录重建清单与索引
uv run python main.py kb reset

# 仅增量同步（不清空 Chroma，除非加 --clear-chroma）
uv run python main.py kb sync

# 只删向量缓存
uv run python main.py kb clear-chroma
```

## 会话附加文件

在 `main.py client` 的「多文档路径」框中填写**任意可读路径**（含盘外文件），将：

- **不**写入 `documents.csv`
- **不**污染全库 Chroma
- 仅在本会话内建立**临时切块索引**供 `topic4_rag_query` 使用

也可将材料复制到 `session_upload/` 再在路径框引用。

## 评测题目

正式测试题在 **`data/testset/`**，不属于本目录知识库。
