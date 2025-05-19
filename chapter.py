import psycopg2
import requests
import json
import time
import re
from collections import defaultdict
from datetime import datetime
from nlp_keywords import get_weighted_queries, cleanPhraseFirst

# === CONFIGURATION ===
COURSE_ID = 212
VIDEO_TYPE = 2
SUBJECT = "computer science"
LEVEL = "computer science"
QUESTIONS_PER_CHAPTER = 20
SOLR_PERCENT = 0.6
MAX_KEYWORDS = 30
COMBINED_KEYWORDS_LIMIT = 50
AI_URL = "http://164.52.212.233:8010/pi-chat-prod"
SOLR_URL = 'http://164.52.201.193:8983/solr/rp-quiz'
HEADERS = {"Content-Type": "application/json"}
AI_DELAY_SECONDS = 7
MAX_RETRIES = 3

# === DATABASE CONFIG ===
REMOTE_DB_CONFIG = {
    "dbname": "piruby_db_v2",
    "user": "postgres",
    "password": "prjeev@275",
    "host": "3.108.6.18",
    "port": "5432"
}

KEYWORD_DB_CONFIG = {
    "dbname": "piruby_automation",
    "user": "postgres",
    "password": "piruby@157",
    "host": "164.52.194.25",
    "port": "5432"
}

# === DB FUNCTIONS ===
def fetch_course_structure(course_id):
    query = f"""
    SELECT cs.chapter_name, cs.section_name, vm.video_id
    FROM "Lms_videomaster" vm
    JOIN "Lms_coursesections" cs ON vm.course_section_id = cs.id
    WHERE cs.course_content_id = {course_id} AND vm.type = {VIDEO_TYPE}
    ORDER BY cs.chapter_name, cs.cno;
    """
    with psycopg2.connect(**REMOTE_DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()

def fetch_all_keywords(video_id):
    try:
        with psycopg2.connect(**KEYWORD_DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT critical_all_keywords
                    FROM public.cs_ee_5m_test
                    WHERE video_id = %s LIMIT 1
                """, (video_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], list):
                    return row[0][:MAX_KEYWORDS]
    except Exception as e:
        print(f"[Keyword Fetch Error] {e}")
    return []

# === SOLR FUNCTIONS ===
def query_solr_with_boosted_keywords(keyword_weight_dict, chapter_name):
    query_parts = [f'"{chapter_name}"^3']
    for phrase, weight in keyword_weight_dict.items():
        weight = min(round(weight, 2), 3.5)
        if ' ' in phrase:
            query_parts.append(f'"{phrase}"^{weight}')
        else:
            query_parts.append(f'{phrase}^{weight}')
    query = ' OR '.join(query_parts)

    params = {
        'q': query,
        'qf': 'question^5 explanation^2 chapter_name^3',
        'fq': 'level:degree',
        'defType': 'edismax',
        'fl': 'id,score,question,option1,option2,option3,option4,answer,explanation',
        'wt': 'json',
        'rows': 100,
        'hl': 'true',
        'hl.fl': 'question,explanation',
        'hl.simple.pre': '[[[HL]]]','hl.simple.post': '[[[/HL]]]'
    }

    try:
        res = requests.get(f"{SOLR_URL}/select", params=params, timeout=30)
        res.raise_for_status()
        data = res.json()
        docs = data.get('response', {}).get('docs', [])
        highlights = data.get('highlighting', {})
        return docs, highlights
    except Exception as e:
        print(f"[Solr Error] {e}")
        return [], {}

def solr_docs_to_questions(docs, highlights, chapter):
    questions = []
    for doc in docs:
        doc_id = doc.get('id')
        hl = highlights.get(doc_id, {})
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
            "chapter": chapter,
            "section_name": "",
            "solr_highlight": hl
        })
    return questions

# === AI GENERATION ===
def extract_json_array(text):
    match = re.search(r'\[\s*{.*?}\s*\]', text, re.DOTALL)
    return match.group(0) if match else "[]"

def generate_mcqs_from_keywords(keywords, count, chapter, section):
    trimmed_keywords = keywords[:30]
    keyword_list = ', '.join(f'"{kw}"' for kw in trimmed_keywords)

    prompt = f'''
You are an expert MCQ generator for ELECTRONICS.
Generate {count} MCQs for the section "{section}" in chapter "{chapter}".
Use these top keywords and combinations: {keyword_list}.
Each question must:
- Be technically sound and conceptually relevant.
- Have exactly 1 correct answer and 3 plausible distractors.
- Include at least 40% questions with code or calculations.
- Output JSON only, no explanations. Format:
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
'''
    payload = {"prompt": prompt.strip()}
    time.sleep(AI_DELAY_SECONDS)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = requests.post(AI_URL, headers=HEADERS, json=payload, timeout=120)
            res.raise_for_status()
            response_text = res.json().get("response") or res.json().get("content", "")
            json_text = extract_json_array(response_text)
            parsed = json.loads(json_text)
            if isinstance(parsed, list) and all('question_text' in q for q in parsed):
                return parsed
        except Exception as e:
            wait = AI_DELAY_SECONDS * attempt
            print(f"[AI Gen Error] Attempt {attempt}: {e} - Retrying in {wait} sec")
            time.sleep(wait)
    return []

# === MAIN CHAPTER PROCESSING ===
def process_chapter(chapter, section_videos):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Processing Chapter: {chapter}")
    all_keywords = []
    for vids in section_videos.values():
        for vid in vids:
            kws = fetch_all_keywords(vid)
            all_keywords.extend(kws)

    text_blob = " ".join(all_keywords)
    _, phrasescorelist, _, _ = get_weighted_queries(text_blob, len(text_blob), SUBJECT, LEVEL)

    weighted_keywords = {
        cleanPhraseFirst(p): min(round(score, 2), 3.5)
        for p, score in phrasescorelist if score >= 1.0
    }
    weighted_keywords = dict(sorted(weighted_keywords.items(), key=lambda x: -x[1])[:MAX_KEYWORDS])

    solr_count = round(QUESTIONS_PER_CHAPTER * SOLR_PERCENT)
    ai_count = QUESTIONS_PER_CHAPTER - solr_count

    solr_docs, solr_highlights = query_solr_with_boosted_keywords(weighted_keywords, chapter)
    solr_questions = solr_docs_to_questions(solr_docs, solr_highlights, chapter)[:solr_count]

    print(f"[Info] Solr returned {len(solr_questions)} / {solr_count} needed.")
    remaining_ai_count = QUESTIONS_PER_CHAPTER - len(solr_questions)

    ai_questions = []
    if remaining_ai_count > 0:
        ai_questions = generate_mcqs_from_keywords(list(weighted_keywords.keys()), remaining_ai_count, chapter, "")
        print(f"[Info] AI generated {len(ai_questions)} questions.")

    all_questions = solr_questions + ai_questions
    for i, q in enumerate(all_questions, 1):
        print(f"\nQ{i}: {q['question_text']}")
        print(f"  A. {q['option_a']}")
        print(f"  B. {q['option_b']}")
        print(f"  C. {q['option_c']}")
        print(f"  D. {q['option_d']}")
        print(f"  Correct Answer: {q['correct_answer']} - {q['correct_answer_text']}")
        print(f"  Explanation: {q['answer_explanation']}")

        matched_keywords = []
        if 'solr_highlight' in q and q['solr_highlight']:
            for field, fragments in q['solr_highlight'].items():
                for frag in fragments:
                    matched_keywords += re.findall(r'\[\[\[HL\]\]\](.+?)\[\[\[/HL\]\]\]', frag)
        matched_keywords = sorted(set(matched_keywords))
        # Fallback: check keywords in question/explanation if highlight is empty
        if not matched_keywords:
            q_text = f"{q['question_text']} {q.get('answer_explanation', '')}".lower()
            for kw in weighted_keywords.keys():
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', q_text):
                    matched_keywords.append(kw)
            matched_keywords = sorted(set(matched_keywords))
        if matched_keywords:
            print(f"  [Matched keywords]: {matched_keywords}")
            if len(matched_keywords) > 1:
                print(f"  [Combination]: {' + '.join(matched_keywords)}")
        else:
            print("  [Matched keywords]: None found")

# === RUN DRIVER ===
def run():
    structure = fetch_course_structure(COURSE_ID)
    data_by_chapter = defaultdict(lambda: defaultdict(list))
    for chapter, section, vid in structure:
        data_by_chapter[chapter][section].append(vid)

    for chapter, sections in data_by_chapter.items():
        process_chapter(chapter, sections)

if __name__ == "__main__":
    run()
