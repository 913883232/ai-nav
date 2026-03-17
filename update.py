#!/usr/bin/env python3
"""
AI NAV 每日自动更新脚本
通过 SerpAPI / Google 搜索抓取最新 AI 工具信息，合并到 data.json

用法:
  python update.py                         # 使用默认搜索（无需 API key，使用 DuckDuckGo）
  SERP_API_KEY=xxx python update.py        # 使用 SerpAPI（更稳定）
  OPENAI_API_KEY=xxx python update.py      # 使用 OpenAI 生成描述（可选增强）

依赖:
  pip install requests beautifulsoup4
"""

import json
import os
import re
import sys
import time
import hashlib
import logging
from datetime import datetime
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

# === 配置 ===
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger("ai-nav-updater")

# 搜索关键词 - 每个分类对应的搜索查询
SEARCH_QUERIES = {
    "chat":    ["best AI chatbot LLM 2025 2026", "最新AI大模型 聊天机器人"],
    "image":   ["best AI image generator text to image 2025 2026", "AI文生图工具"],
    "video":   ["best AI video generator text to video 2025 2026", "AI文生视频工具"],
    "coding":  ["best AI coding assistant IDE 2025 2026", "AI编程工具 代码助手"],
    "search":  ["best AI search engine 2025 2026", "AI搜索引擎"],
    "writing": ["best AI writing assistant 2025 2026", "AI写作工具"],
    "audio":   ["best AI music generator voice synthesis 2025 2026", "AI音乐生成 语音合成"],
    "design":  ["best AI design tool UI 2025 2026", "AI设计工具"],
    "editing": ["best AI image editor photo editing 2025 2026", "AI图像编辑 修图工具"],
    "free":    ["best free AI tools 2025 2026", "免费AI工具推荐"],
}

# 已知工具的基础数据库 - 用于匹配和补充信息
KNOWN_TOOLS = {
    # === PLACEHOLDER: will be loaded from existing data.json ===
}

# === 搜索引擎抽象 ===

class DuckDuckGoSearcher:
    """免费搜索，无需 API key"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    }

    def search(self, query, num_results=10):
        """通过 DuckDuckGo HTML 搜索"""
        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for r in soup.select(".result")[:num_results]:
                title_el = r.select_one(".result__title a")
                snippet_el = r.select_one(".result__snippet")
                if title_el:
                    href = title_el.get("href", "")
                    # DuckDuckGo redirect URLs
                    if "uddg=" in href:
                        from urllib.parse import parse_qs, urlparse as up
                        parsed = up(href)
                        qs = parse_qs(parsed.query)
                        href = qs.get("uddg", [href])[0]
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": href,
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                    })
        except Exception as e:
            log.warning(f"DuckDuckGo search failed for '{query}': {e}")
        return results


class SerpAPISearcher:
    """使用 SerpAPI（需要 API key，更稳定）"""

    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, query, num_results=10):
        results = []
        try:
            resp = requests.get("https://serpapi.com/search", params={
                "q": query,
                "api_key": self.api_key,
                "num": num_results,
                "engine": "google",
            }, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            for r in data.get("organic_results", [])[:num_results]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("snippet", ""),
                })
        except Exception as e:
            log.warning(f"SerpAPI search failed for '{query}': {e}")
        return results


def get_searcher():
    """根据环境变量选择搜索引擎"""
    serp_key = os.environ.get("SERP_API_KEY")
    if serp_key:
        log.info("Using SerpAPI searcher")
        return SerpAPISearcher(serp_key)
    log.info("Using DuckDuckGo searcher (no API key found)")
    return DuckDuckGoSearcher()


# === 工具发现逻辑 ===

def extract_tool_urls_from_results(results):
    """从搜索结果中提取可能的 AI 工具 URL"""
    tool_domains = set()
    # 排除的域名（搜索引擎、社交媒体、新闻站等）
    EXCLUDE_DOMAINS = {
        "youtube.com", "twitter.com", "x.com", "reddit.com", "facebook.com",
        "linkedin.com", "medium.com", "zhihu.com", "csdn.net", "github.com",
        "wikipedia.org", "amazon.com", "google.com", "bing.com",
        "36kr.com", "techcrunch.com", "theverge.com", "wired.com",
        "producthunt.com", "alternativeto.com", "g2.com", "capterra.com",
        "trustpilot.com", "sitejabber.com",
    }

    for r in results:
        url = r.get("url", "")
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "").lower()
            if domain and domain not in EXCLUDE_DOMAINS and "." in domain:
                tool_domains.add(domain)
        except:
            pass
    return tool_domains


def load_existing_data():
    """加载现有的 data.json"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"lastUpdated": "", "tools": []}


def save_data(data):
    """保存 data.json"""
    data["lastUpdated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"Saved {len(data['tools'])} tools to {DATA_FILE}")


def check_url_alive(url, timeout=8):
    """检查 URL 是否可访问"""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        return resp.status_code < 400
    except:
        return False


def discover_new_tools(searcher, existing_urls):
    """搜索发现新工具"""
    discovered = []
    existing_domains = set()
    for url in existing_urls:
        try:
            existing_domains.add(urlparse(url).netloc.replace("www.", "").lower())
        except:
            pass

    for cat, queries in SEARCH_QUERIES.items():
        log.info(f"Searching category: {cat}")
        for query in queries:
            results = searcher.search(query, num_results=10)
            time.sleep(1)  # 避免请求过快

            for r in results:
                url = r.get("url", "")
                title = r.get("title", "")
                snippet = r.get("snippet", "")

                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc.replace("www.", "").lower()
                except:
                    continue

                # 跳过已知域名
                if domain in existing_domains:
                    continue

                # 跳过非工具站点
                EXCLUDE = {
                    "youtube.com", "twitter.com", "x.com", "reddit.com",
                    "facebook.com", "linkedin.com", "medium.com", "zhihu.com",
                    "csdn.net", "wikipedia.org", "amazon.com", "google.com",
                    "36kr.com", "techcrunch.com", "theverge.com",
                    "producthunt.com", "alternativeto.com", "g2.com",
                    "blog.", "news.", "wiki.",
                }
                if any(ex in domain for ex in EXCLUDE):
                    continue

                # 简单启发式：标题或摘要包含 AI 相关关键词
                text = (title + " " + snippet).lower()
                ai_keywords = ["ai", "artificial", "machine learning", "gpt",
                               "llm", "生成", "智能", "模型", "neural"]
                if not any(kw in text for kw in ai_keywords):
                    continue

                # 构建候选工具
                clean_name = title.split(" - ")[0].split(" | ")[0].split(" : ")[0].strip()
                if len(clean_name) > 30:
                    clean_name = clean_name[:30]

                base_url = f"https://{domain}"
                discovered.append({
                    "name": clean_name,
                    "cat": cat,
                    "url": base_url,
                    "desc": snippet[:80] if snippet else title[:80],
                    "tag": "freemium",
                    "_domain": domain,
                    "_confidence": "low",  # 标记为低置信度，需人工审核
                })
                existing_domains.add(domain)

    return discovered


def validate_existing_tools(tools):
    """验证现有工具的链接是否仍然有效"""
    validated = []
    dead_count = 0

    for tool in tools:
        # 只抽查 10% 的链接以节省时间
        if hash(tool["url"]) % 10 == 0:
            if not check_url_alive(tool["url"]):
                log.warning(f"Dead link detected: {tool['name']} -> {tool['url']}")
                tool["_status"] = "dead"
                dead_count += 1
            else:
                tool["_status"] = "alive"
        validated.append(tool)

    log.info(f"Link check: {dead_count} dead links found (sampled)")
    return validated


def run_update():
    """主更新流程"""
    log.info("=" * 50)
    log.info("AI NAV 数据更新开始")
    log.info("=" * 50)

    # 1. 加载现有数据
    data = load_existing_data()
    existing_tools = data.get("tools", [])
    existing_urls = {t["url"] for t in existing_tools}
    log.info(f"现有工具数: {len(existing_tools)}")

    # 2. 初始化搜索引擎
    searcher = get_searcher()

    # 3. 搜索发现新工具
    new_tools = discover_new_tools(searcher, existing_urls)
    log.info(f"发现候选新工具: {len(new_tools)}")

    # 4. 验证现有链接
    existing_tools = validate_existing_tools(existing_tools)

    # 5. 移除明确死链的工具
    alive_tools = [t for t in existing_tools if t.get("_status") != "dead"]
    removed = len(existing_tools) - len(alive_tools)
    if removed > 0:
        log.info(f"移除死链工具: {removed}")

    # 6. 合并新工具（标记为待审核）
    # 新发现的工具放入 pending 区域，可通过 review 命令审核
    pending_file = DATA_FILE.replace("data.json", "pending.json")
    if new_tools:
        # 清理内部字段
        for t in new_tools:
            t.pop("_domain", None)
            t.pop("_confidence", None)
        with open(pending_file, "w", encoding="utf-8") as f:
            json.dump({
                "discoveredAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tools": new_tools
            }, f, ensure_ascii=False, indent=2)
        log.info(f"候选工具已保存到 pending.json，需人工审核后合并")

    # 7. 清理内部状态字段
    for t in alive_tools:
        t.pop("_status", None)

    # 8. 保存更新后的数据
    data["tools"] = alive_tools
    save_data(data)

    log.info("=" * 50)
    log.info(f"更新完成: {len(alive_tools)} 个工具 | {len(new_tools)} 个待审核")
    log.info("=" * 50)


def approve_pending():
    """审核并合并 pending.json 中的工具到 data.json"""
    pending_file = DATA_FILE.replace("data.json", "pending.json")
    if not os.path.exists(pending_file):
        log.info("没有待审核的工具")
        return

    with open(pending_file, "r", encoding="utf-8") as f:
        pending = json.load(f)

    pending_tools = pending.get("tools", [])
    if not pending_tools:
        log.info("没有待审核的工具")
        return

    data = load_existing_data()
    existing_urls = {t["url"] for t in data["tools"]}

    print(f"\n共 {len(pending_tools)} 个待审核工具:\n")
    approved = []
    for i, t in enumerate(pending_tools):
        print(f"[{i+1}] {t['name']}")
        print(f"    URL:  {t['url']}")
        print(f"    分类: {t['cat']}")
        print(f"    描述: {t['desc']}")
        ans = input("    => 通过? (y/n/e=编辑): ").strip().lower()

        if ans == "y":
            if t["url"] not in existing_urls:
                approved.append(t)
                existing_urls.add(t["url"])
        elif ans == "e":
            t["name"] = input(f"    名称 [{t['name']}]: ").strip() or t["name"]
            t["desc"] = input(f"    描述 [{t['desc']}]: ").strip() or t["desc"]
            t["tag"] = input(f"    标签 [{t['tag']}] (free/freemium/paid): ").strip() or t["tag"]
            if t["url"] not in existing_urls:
                approved.append(t)
                existing_urls.add(t["url"])
        print()

    if approved:
        data["tools"].extend(approved)
        save_data(data)
        log.info(f"已合并 {len(approved)} 个新工具")

    # 清理 pending
    os.remove(pending_file)
    log.info("pending.json 已清理")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "approve":
        approve_pending()
    else:
        run_update()
