# data/processed 目录

本目录存放处理后的数据。

建议文件：

```text
documents.csv
chunks.jsonl
bm25_index.pkl
vector_index/
```

说明：

- `documents.csv` 记录文档清单。
- `chunks.jsonl` 记录切分后的文档片段。
- `bm25_index.pkl` 和 `vector_index/` 通常可以重新生成，体积大时不提交。
