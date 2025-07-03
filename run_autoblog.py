import os
import re
from datetime import datetime, timedelta
from Bio import Entrez
import google.generativeai as genai

# --- 설정 ---
# 1. PubMed API 접속 정보
Entrez.email = os.getenv("PUBMED_EMAIL")
if not Entrez.email:
    raise ValueError("PUBMED_EMAIL environment variable not set.")
Entrez.tool = "AutoblogScript"

# 2. Gemini API 설정
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("Google API Key not found.")
genai.configure(api_key=api_key)

# 3. 검색할 저널 목록: 폴더명과 실제 검색명을 명확히 매핑
JOURNAL_MAPPING = {
    "joms": "J Oral Maxillofac Surg",
    "ijoms": "Int J Oral Maxillofac Surg",
    "jcs": "J Craniofac Surg"
}

# --- 함수 정의 ---

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
        (Summarize the key findings in 2-3 sentences for a clinical dentist or resident.)

        ### 임상적 의의 및 논평
        (Provide a brief commentary on the clinical significance or noteworthy aspects of this study in 1-2 sentences.)
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"### AI 리뷰 생성 실패\n오류: {e}"

def search_and_create_posts():
    search_days = 7
    end_date = datetime.now()
    start_date = end_date - timedelta(days=search_days)
    date_query = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'

    for short_name, full_name in JOURNAL_MAPPING.items():
        print(f"--- Searching for articles in '{full_name}' ---")
        
        query = f'("{full_name}"[Journal]) AND {date_query}'
        handle = Entrez.esearch(db="pubmed", term=query, retmax="100")
        record = Entrez.read(handle)
        handle.close()
        id_list = record["IdList"]

        if not id_list:
            print(f"No new articles found for '{full_name}'.")
            continue
        
        print(f"Found {len(id_list)} articles. Fetching details...")

        handle = Entrez.efetch(db="pubmed", id=id_list, rettype="medline", retmode="xml")
        articles = Entrez.read(handle)
        handle.close()

        for article in articles['PubmedArticle']:
            try:
                medline_citation = article['MedlineCitation']
                article_info = medline_citation['Article']
                
                title = article_info['ArticleTitle']
                if 'Abstract' not in article_info:
                    print(f"Skipping '{title}' (No abstract).")
                    continue
                abstract = article_info['Abstract']['AbstractText'][0]

                mesh_terms = []
                if 'MeshHeadingList' in medline_citation:
                    for mesh in medline_citation['MeshHeadingList']:
                        mesh_terms.append(str(mesh['DescriptorName']))
                
                today_str = datetime.now().strftime("%Y%m%d")
                
                date_folder_path = os.path.join('content', short_name, today_str)
                os.makedirs(date_folder_path, exist_ok=True)

                date_index_path = os.path.join(date_folder_path, '_index.md')
                if not os.path.exists(date_index_path):
                    weight = int(today_str)
                    index_content = f'---\ntitle: "{today_str}"\nweight: {weight}\n---\n\n{{{{% children %}}}}'
                    with open(date_index_path, 'w', encoding='utf-8') as f:
                        f.write(index_content)
                
                safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
                filename = f"{safe_title.replace(' ', '-').lower()[:50]}.md"
                filepath = os.path.join(date_folder_path, filename)

                if os.path.exists(filepath):
                    continue

                print(f"Generating AI review for: {title}")
                ai_review_content = get_ai_review(abstract)

                post_content = f"""---
title: '{title.replace("'", "''")}'
date: {datetime.now().isoformat()}
draft: false
tags: {str(mesh_terms)}
---

{ai_review_content}

---

#### 원문 초록 (Original Abstract)
{abstract}
"""
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(post_content)
                print(f"Successfully created post: {filename}")

            except Exception as e:
                print(f"ERROR processing article: {e}")

if __name__ == "__main__":
    search_and_create_posts()