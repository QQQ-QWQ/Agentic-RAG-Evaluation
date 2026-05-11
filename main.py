"""
Topic4 仓库统一 CLI 入口。

用法概览::

    uv run python main.py                         # 集成工作台：[1]配置偏好 [4]单文档RAG（无 C0/C1 菜单）
    uv run python main.py hub                     # 同上
    uv run python main.py chat -p "你好"          # 仅 DeepSeek，跳过工作台
    uv run python main.py rag <文档> <问题>
    uv run python main.py agent [可选单文档路径] [--once-file F] [--stdin] [--single-line] [--orchestrate-repeat]  # 单次注入默认不重跑编排；需研判重复时加 --orchestrate-repeat
    uv run python main.py experiment batch [--limit N]
    uv run python main.py experiment c2 [--phase all|1|2|3] ...
    uv run python main.py score answers --results runs/results/xxx.csv
    uv run python main.py score c2-ablation [--skip-judge]
    uv run python main.py demo interactive [文档路径]
    uv run python main.py demo once <文档> <问题>
    uv run python main.py demo c1 <文档> <问题>
    uv run python main.py ui
    uv run python main.py kb ingest <文件>      # 新文档入库并重建 Chroma 全库索引
    uv run python main.py session init        # 交互选择接入模块 → 写入 configs/active_session.yaml
    uv run python main.py session show

``rag`` 合并顺序：内置默认 → ``configs/active_session.yaml`` → ``-c`` YAML → CLI 开关。

新实验能力：在 ``src/agentic_rag/`` 实现函数 → 在 ``src/agentic_rag/cli/app.py`` 注册子命令；
避免继续在根目录新增 ``run_*.py`` / ``*_demo.py``（详见 ``.cursor/rules/topic4-experiment-stack.mdc``）。
"""

from __future__ import annotations

from agentic_rag.cli.app import main


if __name__ == "__main__":
    main()
