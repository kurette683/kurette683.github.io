import os
import feedparser
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
import re
from time import mktime
from collections import defaultdict

# GitHub Secrets에 저장된 API 키를 불러와 설정
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("Google API Key not found. Please set the GOOGLE_API_KEY environment variable.")
genai.configure(api_key=api_key)

# 논문을 가져올 저널 RSS 피드 목록 (나중에 여기에 IJOMS, JCS 추가 가능)
JOURNAL_FEEDS = {
    "JOMS": "https://www.joms.org/current.rss",
    # "IJOMS": "https://www.ijoms.com/current.rss",
    # "JCS": "https://journals.lww.com/jcraniofacialsurgery/_layouts/15/OAKS.Journals/feed.aspx?FeedType=CurrentIssue"
}

# AI에게 요약 및 논평을 요청하는 함수
def get_ai_review(abstract: str) -> str:
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        You are an expert in Oral and Maxillofacial Surgery.
        Analyze the following abstract from a major journal.

        Abstract:
        ---
        {abstract}
        ---

        Based on the abstract, please provide the following in KOREAN, formatted in Markdown:

        ### 핵심 요약
        (Summarize the key findings in 2-3 sentences for a clinical clinical dentist or resident.)

        ### 임상적 의의 및 논평
        (Provide a brief commentary on the clinical significance or noteworthy aspects of this study in 1-2 sentences.)
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"### AI 리뷰 생성 실패\n오류: {e}"

# 메인 실행 함수
def create_new_posts():
    for journal, url in JOURNAL_FEEDS.items():
        journal_lower = journal.lower()
        journal_content_path = os.path.join('content', journal_lower)
        os.makedirs(journal_content_path, exist_ok=True)

        feed = feedparser.parse(url)
        if not feed.entries:
            print(f"No entries found for {journal}. Skipping.")
            continue

        articles_by_date = defaultdict(list)
        seven_days_ago = datetime.now() - timedelta(days=7)

        for entry in feed.entries:
            try:
                entry_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    entry_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    entry_date = datetime.fromtimestamp(mktime(entry.updated_parsed))

                if entry_date and entry_date < seven_days_ago:
                    print(f"Skipping old article: {entry.title} (Published: {entry_date.strftime('%Y-%m-%d')})")
                    continue

                # Group articles by their publication date
                pub_date_str = entry_date.strftime("%Y-%m-%d") if entry_date else "Unknown-Date"
                articles_by_date[pub_date_str].append(entry)

            except Exception as e:
                print(f"ERROR processing entry '{entry.title}': {e}")

        for pub_date_str, entries_for_date in articles_by_date.items():
            filename = f"{pub_date_str}.md"
            filepath = os.path.join(journal_content_path, filename)

            # Check if file already exists to avoid re-generating AI review unnecessarily
            if os.path.exists(filepath):
                print(f"File {filepath} already exists. Skipping AI review generation for this date.")
                continue

            print(f"Generating content for {pub_date_str}")
            full_content = []

            # Frontmatter for the date file
            full_content.append(f"""---
title: "{pub_date_str}"
date: {datetime.now().isoformat()}
draft: false
---

""")

            for entry in entries_for_date:
                try:
                    ai_review_content = get_ai_review(entry.summary)

                    article_block = f"""
# {entry.title}

Publication Date : {pub_date_str}

{ai_review_content}

---

#### 원문 초록 (Original Abstract)
{entry.summary}

<br>

**[원문 바로가기]({entry.link})**
"""
                    full_content.append(article_block)
                except Exception as e:
                    print(f"ERROR generating content for article '{entry.title}': {e}")

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\n".join(full_content))


if __name__ == "__main__":
    create_new_posts()
