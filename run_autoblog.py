import os
import feedparser
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
import re

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
    today_str = datetime.now().strftime("%Y%m%d")
    
    for journal, url in JOURNAL_FEEDS.items():
        journal_lower = journal.lower()
        
        feed = feedparser.parse(url)
        if not feed.entries:
            print(f"No entries found for {journal}. Skipping.")
            continue

        # 날짜별 폴더 경로 설정
        date_folder_path = os.path.join('content', journal_lower, today_str)
        os.makedirs(date_folder_path, exist_ok=True)

        # 날짜별 인덱스 파일 경로 설정 및 생성
        date_index_path = os.path.join(date_folder_path, '_index.md')
        if not os.path.exists(date_index_path):
            # 최신 날짜가 위로 오도록 weight 설정 (큰 숫자 = 낮은 우선순위)
            weight = int(today_str)
            index_content = f"""---
title: \"{today_str}\"
weight: {weight}
---

### {today_str} 발표 논문 목록

아래 목록에서 논문 제목을 클릭하여 내용을 확인하세요.

{{{{% children %}}}}
"""
            with open(date_index_path, 'w', encoding='utf-8') as f:
                f.write(index_content)

        seven_days_ago = datetime.now() - timedelta(days=7)

        for entry in feed.entries:
            try:
                # 논문 발행일 확인 (published 또는 updated 필드 사용)
                entry_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    entry_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    entry_date = datetime.fromtimestamp(mktime(entry.updated_parsed))
                
                if entry_date and entry_date < seven_days_ago:
                    print(f"Skipping old article: {entry.title} (Published: {entry_date.strftime('%Y-%m-%d')})")
                    continue

                # 파일명으로 부적합한 문자 제거
                safe_title = re.sub(r'[\\/*?:"<>|]', "", entry.title)
                filename = f"{safe_title.replace(' ', '-').lower()[:50]}.md"
                filepath = os.path.join(date_folder_path, filename)

                if os.path.exists(filepath):
                    continue
                
                print(f"Processing: {entry.title}")
                ai_review_content = get_ai_review(entry.summary)

                # Hugo 포스트 내용 생성
                post_content = f"""---
title: '{entry.title.replace("'", "''")}'
date: {datetime.now().isoformat()}

draft: false
---

{ai_review_content}

---

#### 원문 초록 (Original Abstract)
{entry.summary}

<br>

**[원문 바로가기]({entry.link})**
"""
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(post_content)
            except Exception as e:
                print(f"ERROR processing entry '{entry.title}': {e}")


if __name__ == "__main__":
    # time 모듈의 mktime 함수를 사용하기 위해 추가
    from time import mktime
    create_new_posts()
