#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库爬虫 v3 - 使用论文ID精确获取arXiv摘要 + 更多在线内容
"""
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from scrapling.fetchers import Fetcher

BASE_DIR = Path(r"D:\programss\110501agenticRAG\Agentic-RAG-Evaluation-main\data\raw")

def save_md(subdir, filename, content, source_url=""):
    dir_path = BASE_DIR / subdir
    dir_path.mkdir(parents=True, exist_ok=True)
    filepath = dir_path / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {Path(filename).stem}\n\n")
        f.write(f"> 来源: {source_url}\n")
        f.write(f"> 爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n")
        f.write(content)
    print(f"  ✓ saved: {subdir}/{filename}")

def fetch_url(url, retries=2):
    for i in range(retries):
        try:
            page = Fetcher.get(url, stealthy_headers=True, timeout=15)
            if page and page.status == 200:
                return page
        except Exception:
            time.sleep(2)
    return None

def crawl_real_arxiv_papers():
    """使用arXiv API通过论文ID精确获取Agentic RAG论文摘要"""
    print("\n=== 1. arXiv 论文精确抓取（已知论文ID）===")
    
    # 已知的Agentic RAG论文ID列表（来自agentic_rag_crawler.py）
    paper_ids = [
        "2501.09136",  # Agentic RAG Survey
        "2603.07379",  # SoK Agentic RAG
        "2602.03442",  # A-RAG
        "2511.05385",  # TeaRAG
        "2310.11511",  # Self-RAG
        "2401.15884",  # CRAG
        "2412.15643",  # RAG-Loaded QA
        "2407.01219",  # RAG vs Long-Context
        "2312.10997",  # RAG Survey
        "2405.13007",  # KG-RAG
    ]
    
    base_url = "https://export.arxiv.org/api/query?id_list=" + ",".join(paper_ids)
    print(f"  fetching {len(paper_ids)} papers by ID...")
    
    try:
        req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=30)
        xml_data = resp.read().decode('utf-8')
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        root = ET.fromstring(xml_data)
        
        papers = []
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
            summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
            paper_id = entry.find('atom:id', ns).text.strip()
            published = entry.find('atom:published', ns)
            pub_date = published.text[:10] if published is not None else ""
            authors = []
            for a in entry.findall('atom:author', ns):
                n = a.find('atom:name', ns)
                if n is not None:
                    authors.append(n.text)
            
            papers.append({
                'title': title, 'summary': summary,
                'id': paper_id, 'date': pub_date,
                'authors': ', '.join(authors[:5])
            })
            print(f"  ✓ {title[:80]}...")
        
        # 保存完整论文列表
        content = f"# Agentic RAG 核心论文列表（arXiv API实时获取）\n\n共 {len(papers)} 篇论文\n\n---\n\n"
        for i, p in enumerate(papers, 1):
            content += f"## {i}. {p['title']}\n"
            content += f"- **ID**: {p['id']}\n- **日期**: {p['date']}\n- **作者**: {p['authors']}\n\n"
            content += f"**摘要**: {p['summary']}\n\n---\n\n"
        save_md('learning_docs', 'arxiv_agentic_rag_papers_v2.md', content, base_url)
        
        # 同时保存每个论文的单独文件
        print("\n  保存单篇论文文件...")
        for p in papers:
            paper_id_short = p['id'].split('/')[-1].split('v')[0]
            fname = f"arxiv_{paper_id_short}.md"
            single = f"## {p['title']}\n\n"
            single += f"- **论文ID**: {p['id']}\n- **日期**: {p['date']}\n- **作者**: {p['authors']}\n\n"
            single += f"**摘要**:\n\n{p['summary']}\n"
            save_md('learning_docs', fname, single, p['id'])
        
    except Exception as e:
        print(f"  ✗ error: {e}")

def crawl_vectordb_docs():
    """爬取向量数据库文档"""
    print("\n=== 2. 向量数据库文档 ===")
    urls = [
        ("chroma_getting_started", "https://docs.trychroma.com/getting-started"),
    ]
    for name, url in urls:
        print(f"  crawling: {url}")
        page = fetch_url(url)
        if page:
            text = page.get_all_text(ignore_tags=('script', 'style', 'nav', 'footer'))
            if text and len(text) > 200:
                save_md('tech_docs', f'{name}.md', text, url)
            else:
                print("  ✗ content too short")
        else:
            print("  ✗ failed")

def crawl_langchain_getting_started():
    """爬取LangChain入门文档"""
    print("\n=== 3. LangChain 入门文档 ===")
    url = "https://python.langchain.com/docs/introduction/"
    print(f"  crawling: {url}")
    page = fetch_url(url)
    if page:
        text = page.get_all_text(ignore_tags=('script', 'style', 'nav', 'footer'))
        if text and len(text) > 200:
            save_md('tech_docs', 'langchain_intro.md', text, url)
        else:
            print("  ✗ content too short")
    else:
        print("  ✗ failed")

def crawl_langgraph_agent_docs():
    """爬取LangGraph Agent文档"""
    print("\n=== 4. LangGraph Agent 文档 ===")
    # 尝试直接获取官方文档首页
    url = "https://langchain-ai.github.io/langgraph/"
    page = fetch_url(url)
    if page:
        text = page.get_all_text(ignore_tags=('script', 'style'))
        if text and len(text) > 200:
            save_md('tech_docs', 'langgraph_agent_docs.md', text, url)
        else:
            print("  ✗ content too short")
    else:
        print("  ✗ failed")

def crawl_faiss_docs():
    """爬取FAISS文档"""
    print("\n=== 5. FAISS 向量检索库 ===")
    url = "https://github.com/facebookresearch/faiss"
    page = fetch_url(url)
    if page:
        text = page.get_all_text(ignore_tags=('script', 'style', 'nav'))
        if text and len(text) > 200:
            save_md('tech_docs', 'faiss_overview.md', text, url)
        else:
            print("  ✗ content too short")
    else:
        print("  ✗ failed")

if __name__ == "__main__":
    print("=" * 60)
    print("知识库爬虫 v3 启动")
    print("=" * 60)
    crawl_real_arxiv_papers()
    crawl_vectordb_docs()
    crawl_langchain_getting_started()
    crawl_langgraph_agent_docs()
    crawl_faiss_docs()
    print("\n" + "=" * 60)
    print("全部爬取完成！")
    print("=" * 60)
