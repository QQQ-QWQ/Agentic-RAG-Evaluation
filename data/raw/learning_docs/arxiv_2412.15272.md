# arxiv_2412.15272.md

> 来源: http://arxiv.org/abs/2412.15272v1
> 爬取时间: 2026-05-06

---

## SimGRAG: Leveraging Similar Subgraphs for Knowledge Graphs Driven Retrieval-Augmented Generation

- 论文ID: 2412.15272
- 作者: Yuzheng Cai, Zhenyue Guo, Yiwen Pei, Wanrui Bian

**摘要**:

Recent advancements in large language models (LLMs) have shown impressive versatility across various tasks. To eliminate their hallucinations, retrieval-augmented generation (RAG) has emerged as a powerful approach, leveraging external knowledge sources like knowledge graphs (KGs). In this paper, we study the task of KG-driven RAG and propose a novel Similar Graph Enhanced Retrieval-Augmented Generation (SimGRAG) method. It effectively addresses the challenge of aligning query texts and KG structures through a two-stage process: (1) query-to-pattern, which uses an LLM to transform queries into a desired graph pattern, and (2) pattern-to-subgraph, which quantifies the alignment between the pattern and candidate subgraphs using a graph semantic distance (GSD) metric. We also develop an optimized retrieval algorithm that efficiently identifies the top-k subgraphs within 1-second on a 10-million-scale KG. Extensive experiments show that SimGRAG outperforms state-of-the-art KG-driven RAG methods in both question answering and fact verification. Our code is available at https://github.com/YZ-Cai/SimGRAG.
