import psycopg2
import requests
import json
import time
import re
from collections import defaultdict
from datetime import datetime
from nlp_keywords import get_weighted_queries, cleanPhraseFirst

# === CONFIGURATION ===
SUBJECT = "electronics"
LEVEL = "electronics"
TOTAL_QUESTIONS = 20
SOLR_TARGET = 15
MAX_KEYWORDS = 200
COMBINED_KEYWORDS_LIMIT = 50
AI_URL = "http://164.52.212.233:8010/pi-chat-prod"
SOLR_URL = 'http://164.52.201.193:8983/solr/rp-quiz'
HEADERS = {"Content-Type": "application/json"}
AI_DELAY_SECONDS = 7
MAX_RETRIES = 3
VIDEO_ID = '982406834'  # For fetching keywords

# Manually set section name
SECTION_NAME = "RTL"

# === DATABASE CONFIG ===
DB_CONFIG = {
    "dbname": "piruby_automation",
    "user": "postgres",
    "password": "piruby@157",
    "host": "164.52.194.25",
    "port": "5432"
}

# === DB FUNCTIONS ===

def fetch_all_keywords(video_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT critical_keywords
                    FROM public.new_vimeo_master_m
                    WHERE video_id = %s
                    ORDER BY _offset
                """, (video_id,))
                result = cur.fetchall()
                keywords = []
                for row in result:
                    if isinstance(row[0], list):
                        keywords.extend(row[0])
                return keywords[:MAX_KEYWORDS]
    except Exception as e:
        print(f"[Keyword Fetch Error] {e}")
    return []

# === SOLR FUNCTIONS ===

def query_solr_with_boosted_keywords(keyword_weight_dict, section_name):
    query_parts = [f'"{section_name}"^3']
    for phrase, weight in keyword_weight_dict.items():
        weight = min(round(weight, 2), 3.5)
        if ' ' in phrase:
            query_parts.append(f'"{phrase}"^{weight}')
        else:
            query_parts.append(f'{phrase}^{weight}')
    query = ' OR '.join(query_parts)

    params = {
        'q': query,
        'qf': 'question^5 explanation^2 chapter_name^2 section_name^3',
        'fq': 'level:degree',
        'defType': 'edismax',
        'fl': 'id,score,question,option1,option2,option3,option4,answer,explanation',
        'wt': 'json',
        'rows': 100
    }

    try:
        res = requests.get(f"{SOLR_URL}/select", params=params, timeout=30)
        res.raise_for_status()
        docs = res.json().get('response', {}).get('docs', [])
        return docs
    except Exception as e:
        print(f"[Solr Error] {e}")
        return []

def solr_docs_to_questions(docs, chapter, section):
    questions = []
    for doc in docs:
        options = [doc.get(f'option{i}', '') for i in range(1, 5)]
        correct_text = doc.get('answer', '')
        correct_letter = next((chr(65 + i) for i, opt in enumerate(options) if opt.strip() == correct_text.strip()), 'A')
        questions.append({
            "question_text": doc.get('question', ''),
            "option_a": options[0],
            "option_b": options[1],
            "option_c": options[2],
            "option_d": options[3],
            "correct_answer": correct_letter,
            "correct_answer_text": correct_text,
            "answer_explanation": doc.get('explanation', ''),
            "difficulty_level": "L1",
            "questiontype": "Single",
            "subject": SUBJECT,
            "course": LEVEL,
            "chapter": "ADAD",
            "section_name": section
        })
    return questions

# === AI GENERATION ===

def extract_json_array(text):
    match = re.search(r'\[\s*{.*?}\s*\]', text, re.DOTALL)
    return match.group(0) if match else "[]"

def generate_mcqs_from_keywords(keywords, count, chapter, section):
    prompt = f'''
You are an AI question generator for a ELECTRONICS course.
Generate {count} MCQs for the section titled "{section}" in the chapter "{chapter}".
Use the following keywords to ensure relevance: {', '.join(keywords)}.
Make the questions strictly related to the section. Avoid generic or off-topic questions.
Return ONLY a valid JSON list in this format:
[{{
  "question_text": "...",
  "option_a": "...",
  "option_b": "...",
  "option_c": "...",
  "option_d": "...",
  "correct_answer": "A",
  "correct_answer_text": "...",
  "answer_explanation": "...",
  "difficulty_level": "L1",
  "questiontype": "Single",
  "subject": "{SUBJECT}",
  "course": "{LEVEL}",
  "chapter": "{chapter}",
  "section_name": "{section}"
}}]
Only return the JSON list. No explanation.
'''
    payload = {"prompt": prompt}
    time.sleep(AI_DELAY_SECONDS)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = requests.post(AI_URL, headers=HEADERS, json=payload, timeout=60)
            res.raise_for_status()
            raw_response = res.json().get("response") or res.json().get("content", "")
            json_text = extract_json_array(raw_response)
            return json.loads(json_text)
        except Exception as e:
            print(f"[AI Gen Error] Attempt {attempt}: {e}")
            time.sleep(AI_DELAY_SECONDS)
    return []

# === MAIN FLOW ===

def main():
    keywords = fetch_all_keywords(VIDEO_ID)

    if not keywords:
        print("[Skip] No keywords found for video.")
        return

    text_blob = " ".join(keywords)
    _, phrasescorelist, _, _ = get_weighted_queries(text_blob, len(text_blob), SUBJECT, LEVEL)

    weighted_keywords = {
        cleanPhraseFirst(p): min(round(score, 2), 3.5)
        for p, score in phrasescorelist if score >= 1.0
    }
    weighted_keywords = dict(sorted(weighted_keywords.items(), key=lambda x: -x[1])[:COMBINED_KEYWORDS_LIMIT])

    solr_docs = query_solr_with_boosted_keywords(weighted_keywords, SECTION_NAME)
    solr_questions = solr_docs_to_questions(solr_docs, "ADAD", SECTION_NAME)[:SOLR_TARGET]

    print(f"[Info] Got {len(solr_questions)} from Solr.")
    remaining_count = TOTAL_QUESTIONS - len(solr_questions)

    ai_questions = []
    if remaining_count > 0:
        ai_questions = generate_mcqs_from_keywords(list(weighted_keywords.keys()), remaining_count, "ADAD", SECTION_NAME)
        print(f"[Info] Generated {len(ai_questions)} via AI.")

    all_questions = solr_questions + ai_questions
    print("\n\n=== FINAL QUESTIONS ===\n")
    for i, q in enumerate(all_questions, 1):
        print(f"Q{i}: {q['question_text']}")
        print(f"  A. {q['option_a']}")
        print(f"  B. {q['option_b']}")
        print(f"  C. {q['option_c']}")
        print(f"  D. {q['option_d']}")
        print(f"  Correct Answer: {q['correct_answer']} - {q['correct_answer_text']}")
        print(f"  Explanation: {q['answer_explanation']}\n")

if __name__ == "__main__":
    main()
