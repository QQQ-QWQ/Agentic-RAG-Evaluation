# 实验档位（C0–C4）与代码归属说明

本文说明 **`configs/*.yaml` 中的档位定义**、**实际运行时读到的参数**、以及**源码文件按能力归属**的对应关系，避免「以为按 YAML 跑了 C2/C3，其实代码走的是另一套开关」这类混淆。

> **维护约定**：若你新增 YAML 字段或改档位语义，请同步更新本文件与 `docs/directory_rules.md` 中相关段落。

---

## 1. 先分清两条线

| 线索 | 含义 | 典型入口 |
|------|------|----------|
| **A. 批量/单管 RAG 实验线** | `RunProfile` + `pipelines/local_rag.py` 的 `run_c0_with_index` / `run_c1_with_index`，一次问答内的检索与生成。 | `run_batch_experiments.py`、`run_c2_retrieval_ablation.py`、`main.py rag --config ...`、`experiment.runner.run_*_rag` |
| **B. Agent 多层级编排线** | `deep_planning/` + `orchestration/`：规划 JSON → 工具（含 RAG）→ 可选 grounding → 研判循环。 | `main.py agent` |

两条线**共用**底层实现（`rag/`、`pipelines/local_rag.py`、`rewrite` 等），但**不等价**于「加载 `c3_agentic_retrieval.yaml` 就等于跑了 C3 单管实验」。C3 YAML 描述的是 **A 线**上的目标能力组合；**B 线**是另一套控制流，概念上接近「智能体化检索/编排」，但没有与 `config_name: c3_agentic_retrieval` 做一键绑定。

---

## 2. YAML 档位定义（合同层）

`configs/` 下各文件通过 `modules` 与 `base_config` 声明**递进关系**（语义上 C0→C1→C2→C3→C4）：

| 文件 | 相对上一层多出来的能力（摘要） |
|------|--------------------------------|
| `c0_naive.yaml` | 无 query rewrite、无 hybrid、无 rerank。 |
| `c1_rewrite.yaml` | 仅 `query_rewrite: true`，检索侧仍为稠密 Top-K（YAML 中 hybrid/bm25/rerank 均为 false）。 |
| `c2_advanced.yaml` | 在 C1 上打开 BM25/hybrid/rerank（`modules` 与 `rerank:` 块）。 |
| `c3_agentic_retrieval.yaml` | 在 C2 上打开 `task_planning`、`multi_round_retrieval`、`self_check`，且 `tool_calling: false`。 |
| `c4_tool_augmented.yaml` | 在 C3 上再打开外部工具等（见该文件 `tools:`）。 |

说明：`base_config: "c1_rewrite"` 等字段在仓库内**表示文档化继承关系**；当前 **`profile_from_yaml_dict` 不会递归合并父 YAML**，只会解析**当前打开的那一个 YAML 文件**。

---

## 3. 代码是否真的遵循 YAML？（A 线：RunProfile）

运行时真正驱动 A 线的是 **`src/agentic_rag/experiment/profile.py` 中的 `RunProfile`**，由 `load_profile_yaml` / `profile_from_yaml_dict`、CLI 参数、`active_session` 覆盖或代码里硬编码的 `common_kwargs` 共同决定。

### 3.1 已从 YAML 读入并影响运行的字段（摘要）

- `modules.hybrid_retrieval` → `use_hybrid_retrieval`
- `modules.query_rewrite` → `use_query_rewrite`
- 根级或 `merge_profile_dict` 支持的扁平键（若写在 YAML 根上）：如 `use_rerank`、`top_k` 等
- `retrieval.top_k`、`retrieval.use_rerank`、`retrieval.rerank_backend`、`retrieval.rerank_pool_size`、`retrieval.context_neighbor_chunks`
- `query_rewrite.prompt_file` → `rewrite_prompt_file`
- `logging.save_jsonl` → `save_jsonl_log`

### 3.2 与 `configs/c2_advanced.yaml` 等不一致之处（重要）

1. **`modules.rerank: true` 不会自动变成 `RunProfile.use_rerank`**  
   `apply_modules_yaml` 目前**只**处理 `hybrid_retrieval` 与 `query_rewrite`，**没有**把 `modules.rerank` 映射到 `use_rerank`。

2. **`c2_advanced.yaml` 顶层的 `rerank:` 块（含 `enabled: true`）未被 `profile_from_yaml_dict` 读取**  
   因此若仅 `load_profile_yaml("configs/c2_advanced.yaml")` 且不设其它覆盖，**`use_rerank` 可能仍为默认 `false`**，与 YAML 字面「全开 C2」不完全一致。  
   实际打开 rerank 的路径包括：`RunProfile` 默认值以外的显式赋值、CLI `--rerank`、`main.py rag` 相关参数、或 `retrieval` 段内若将来补充 `use_rerank` 等。

3. **`c2_advanced.yaml` 中 `retrieval` 的 `vector_top_k` / `merged_top_k` / `final_top_k` 等**  
   当前 `profile_from_yaml_dict` **未映射**这些细粒度字段；粗检与融合逻辑以 `pipelines/local_rag.py` 与 `RunProfile` 已有字段（如 `rerank_pool_size`、`top_k`）为准。

4. **C3/C4 YAML 中的 `task_planning`、`multi_round_retrieval`、`self_check`、`tool_calling` 及 `tools:`**  
   **没有**对等的 `RunProfile` 布尔项与 `runner.run_document_rag` / `run_knowledge_base_rag` 内的分支；即 **A 线单管入口目前不实现「整包 C3/C4 YAML 语义」**，这些文件主要起**规格与实验记录对齐**作用，直到有专门管线代码接好。

### 3.3 `run_batch_experiments.py` 与 YAML

`run_batch_experiments.py` **不调用** `load_profile_yaml`：在 `run_config` 里对 C0/C1 **硬编码**了 `hybrid=False`、`use_rerank=False`、`context_neighbor_chunks=0` 等，与当前 `c0_naive` / `c1_rewrite` 的 `modules` 意图一致，但属于**重复约定**，改 YAML 不会自动改变批量脚本行为。

### 3.4 `run_c2_retrieval_ablation.py` 与 YAML

C2 消融脚本通过**代码里各 phase 的 kwargs** 打开 hybrid / rerank / 邻接扩展，**不读取** `c2_advanced.yaml` 全文作为单一真源；语义上与 `docs/c2_ablation_guide.md` 及「C2 三阶段」一致，但与「仅 `load_profile_yaml(c2_advanced)`」不是同一件事。

---

## 4. 源码「归属」：按能力域，不按目录名

下列不是「只属于 C2 的文件夹」，而是**多档位共用**；归属指「主要服务于哪一档声明的能力」。

### 4.1 全员共用（所有档位都依赖）

| 路径 | 作用 |
|------|------|
| `src/agentic_rag/documents/` | 解析 |
| `src/agentic_rag/ark/` | 向量 |
| `src/agentic_rag/llm/` | 对话客户端 |
| `src/agentic_rag/rag/simple.py` | 稠密索引与相似度 |
| `src/agentic_rag/rag/chroma_store.py` | Chroma 持久化 |
| `src/agentic_rag/experiment/kb_index_builder.py` | 全库索引构建 |
| `src/agentic_rag/experiment/runner.py` | 单文档/全库 RAG 入口（按 `RunProfile` 调 `run_c0`/`run_c1`） |
| `src/agentic_rag/pipelines/local_rag.py` | `run_c0_with_index`、`run_c1_with_index`、检索与生成主路径 |

### 4.2 主要对应「C0 vs C1」分支

| 路径 | 说明 |
|------|------|
| `src/agentic_rag/rewrite.py` 及 `run_c1_with_index` 内改写逻辑 | Query rewrite、多检索 query |
| `prompts/query_rewrite_prompt.md` | C1 改写提示词 |
| `src/agentic_rag/cli/demos.py` 中 `run_c1_rewrite_once` | 单次 C1 演示 |
| `run_batch_experiments.py` | 仅跑通 **c0_naive / c1_rewrite** 两档（硬编码 kwargs） |

「C0」= `use_query_rewrite=False` 走 `run_c0_with_index`；「C1」= `use_query_rewrite=True` 走 `run_c1_with_index`，常与 `hybrid=False` 对照纯 C1。

### 4.3 主要对应「C2」检索增强

| 路径 | 说明 |
|------|------|
| `src/agentic_rag/rag/bm25.py` | BM25 |
| `src/agentic_rag/rag/fusion.py` | 稠密 + BM25 融合 |
| `src/agentic_rag/rag/rerank.py` | LLM rerank |
| `src/agentic_rag/rag/context_expand.py` | 邻接块等上下文扩展 |
| `run_c2_retrieval_ablation.py`、`run_c2_ablation_answer_accuracy.py` | C2 消融与评分脚本 |
| `src/agentic_rag/experiment/c2_ablation_metrics.py` | C2 消融 CSV 扩展字段 |
| `src/agentic_rag/deep_planning/presets.py` | RAG 工具用预设：`c2_stage1_hybrid`、`c2_stage2_rerank`、`c2_stage3_context`（与 C2 三阶段对齐，**无 c3_ 预设名**） |

### 4.4 「C3 / C4」在 A 线现状

- **无**单独命名为 `c3_*.py` 的单管流水线文件与 `RunProfile` 中 `task_planning` 等一一对应。
- `configs/c3_agentic_retrieval.yaml`、`configs/c4_tool_augmented.yaml`：**规格与日志字段设计**为主；完整行为需在 `runner` / `local_rag` 或独立 orchestrator 中实现后才能称「代码遵循 YAML」。
- `prompts/self_check_prompt.md`：YAML 中 C3 的 self-check 引用；是否在**同一条** `run_c1_with_index` 路径里调用，以实际 `local_rag` 实现为准（当前以检索+生成为主）。

### 4.5 「C4 工具」与 Agent 线

| 路径 | 说明 |
|------|------|
| `src/agentic_rag/deep_planning/tools_factory.py` | LangChain 工具：RAG、入库、MarkItDown、可选沙箱等 |
| `src/agentic_rag/tools/` | MarkItDown 等 |
| `src/agentic_rag/orchestration/`、`src/agentic_rag/deep_planning/agent_runner.py` 等 | **B 线**编排与研判 |

这与 `c4_tool_augmented.yaml` 里列举的工具名**概念对齐**，但具体工具列表与 YAML 逐项可能不完全相同，以 `tools_factory` 为准。

### 4.6 评测与档位无关

| 路径 | 说明 |
|------|------|
| `src/agentic_rag/evaluation/`、`run_score_answer_accuracy.py` 等 | 对已有日志/答案打分；不单独属于某一 C 档 |

---

## 5. 快速查表：「我想改 X，该动哪里？」

| 目标 | 优先查看 |
|------|------------|
| 改 C0/C1 批量行为 | `run_batch_experiments.py`（注意：未读 YAML） |
| 改 `main.py rag --config` 从 YAML 得到的开关 | `experiment/profile.py` 的 `profile_from_yaml_dict` / `apply_modules_yaml` |
| 改检索、混合、rerank、邻接 | `pipelines/local_rag.py`、`rag/fusion.py`、`rag/rerank.py` |
| 改全库索引与 Chroma | `experiment/kb_index_builder.py`、`rag/chroma_store.py` |
| 改 Agent 可调 RAG 档位名 | `deep_planning/presets.py`（当前到 C2 三阶段 + c0/c1/project_default） |
| 对齐实验笔记里的「正式 C 档定义」 | `configs/c*.yaml` |

---

## 6. 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) — 目录与模块职责  
- [c2_ablation_guide.md](c2_ablation_guide.md) — C2 三阶段消融与脚本行为  
- [directory_rules.md](directory_rules.md) — 目录与配置命名约定  
- [experiment_notes.md](experiment_notes.md) — 实验过程与结果记录  

---

*文档生成说明：反映仓库在撰写时的 `RunProfile` 与脚本行为；若后续实现「YAML 全量驱动」或「C3 单管管线」，请更新第 3、4 节。*
