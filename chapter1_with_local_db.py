import psycopg2
import requests
import json
import time
import re
from collections import defaultdict, Counter
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
COMBINED_KEYWORDS_LIMIT = 40
AI_URL = "http://164.52.212.233:8010/pi-chat-prod"
SOLR_URL = 'http://164.52.201.193:8983/solr/rp-quiz'
HEADERS = {"Content-Type": "application/json"}
AI_DELAY_SECONDS = 7
MAX_RETRIES = 3

# === DATABASE CONFIG ===
# === LOCAL DB CONFIG ===
LOCAL_DB_CONFIG = {
    "dbname": "quiz_chaptermaster",
    "user": "postgres",  # likely 'postgres'
    "password": "Hemanth",
    "host": "localhost",
    "port": "5432"
}

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
                    keywords = row[0][:MAX_KEYWORDS]
                    if len(keywords) < MAX_KEYWORDS:
                        print(f"[Keyword Check] Video ID {video_id} has only {len(keywords)} keywords (expected {MAX_KEYWORDS})")
                    return keywords
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

def extract_keywords_in_text(text, keywords):
    found = set()
    text_lower = text.lower()
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw.lower()) + r'\b', text_lower):
            found.add(kw)
    return found

def solr_docs_to_questions(docs, highlights, chapter, keyword_list):
    keyword_counter = Counter()
    processed_questions = []

    for doc in docs:
        q_text = f"{doc.get('question', '')} {doc.get('explanation', '')}"
        used_keywords = extract_keywords_in_text(q_text, keyword_list)
        keyword_counter.update(used_keywords)

        options = [doc.get(f'option{i}', '') for i in range(1, 5)]
        correct_text = doc.get('answer', '')
        correct_letter = next((chr(65 + i) for i, opt in enumerate(options) if opt.strip() == correct_text.strip()), 'A')
        processed_questions.append({
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
            "solr_highlight": highlights.get(doc.get('id'), {})
        })

    # Drop lower-scoring questions for overused keywords
    used_q_keywords = []
    for q in processed_questions:
        q_text = f"{q['question_text']} {q['answer_explanation']}"
        matched = extract_keywords_in_text(q_text, keyword_list)
        score = sum(keyword_counter[k] for k in matched)
        used_q_keywords.append((score, q))

    used_q_keywords.sort(key=lambda x: x[0])
    return [q for _, q in used_q_keywords[:round(QUESTIONS_PER_CHAPTER * SOLR_PERCENT)]]

def extract_json_array(text):
    match = re.search(r'\[\s*{.*?}\s*\]', text, re.DOTALL)
    return match.group(0) if match else "[]"

def generate_mcqs_from_keywords(keyword_chunks, count, chapter, section):
    import math
    all_questions = []
    total_chunks = len(keyword_chunks)
    if total_chunks == 0 or count == 0:
        return []

    questions_per_chunk = [count // total_chunks] * total_chunks
    for i in range(count % total_chunks):
        questions_per_chunk[i] += 1

    for idx, chunk_keywords in enumerate(keyword_chunks):
        chunk_count = questions_per_chunk[idx]
        if not chunk_keywords or chunk_count == 0:
            continue

        keyword_list = ', '.join(f'"{kw}"' for kw in chunk_keywords)
        prompt = f'''
You are an expert MCQ generator for ELECTRONICS.
Generate {chunk_count} MCQs for the section "{section}" in chapter "{chapter}".
Use these top keywords and combinations: {keyword_list}.
Each question must:
- Be technically sound and conceptually relevant.
- Have exactly 1 correct answer and 3 plausible distractors.
- Include at least 40% questions with code or calculations.
- In at least half the questions, use two or more keywords together in the question or options.
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
                    all_questions.extend(parsed)
                    break
            except Exception as e:
                wait = AI_DELAY_SECONDS * attempt
                print(f"[AI Gen Error] Chunk {idx+1}/{total_chunks}, Attempt {attempt}: {e} - Retrying in {wait} sec")
                time.sleep(wait)

    seen = set()
    deduped_questions = []
    for q in all_questions:
        qtext = q.get("question_text", "").strip()
        if qtext and qtext not in seen:
            deduped_questions.append(q)
            seen.add(qtext)
    return deduped_questions[:count]


def insert_questions_to_local_db(questions):
    insert_query = """
    INSERT INTO mcq_master2 (
        question, answer, option1, option2, option3, option4,
        explanation, subject, course_name, chapter_name, section_name,
        difficulty_level, q_category
    ) VALUES (
        %(question_text)s, %(correct_answer_text)s, %(option_a)s, %(option_b)s, %(option_c)s, %(option_d)s,
        %(answer_explanation)s, %(subject)s, %(course)s, %(chapter)s, %(section_name)s,
        %(difficulty_level)s, %(questiontype)s
    )
    """
    try:
        with psycopg2.connect(**LOCAL_DB_CONFIG) as conn:
            with conn.cursor() as cur:
                for idx, q in enumerate(questions, 1):
                    cur.execute(insert_query, q)
                    print(f"[DB Inserted] Q{idx}: {q['question_text'][:80]}... (Section: {q['section_name']}, Chapter: {q['chapter']})")
            conn.commit()
            print(f"[Success] Inserted {len(questions)} questions into local database.")
    except Exception as e:
        print(f"[DB Error] {e}")

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
    weighted_keywords = dict(sorted(weighted_keywords.items(), key=lambda x: -x[1])[:COMBINED_KEYWORDS_LIMIT])
    keyword_list = list(weighted_keywords.keys())

    chunk_size = 10
    overlap = 3
    keyword_chunks = []
    for i in range(0, len(keyword_list), chunk_size - overlap):
        chunk = keyword_list[i:i + chunk_size]
        if len(chunk) >= 3:
            keyword_chunks.append(chunk)

    solr_count = round(QUESTIONS_PER_CHAPTER * SOLR_PERCENT)
    solr_docs, solr_highlights = query_solr_with_boosted_keywords(weighted_keywords, chapter)
    solr_questions = solr_docs_to_questions(solr_docs, solr_highlights, chapter, keyword_list)

    print(f"[Info] Solr returned {len(solr_questions)} / {solr_count} needed.")
    remaining_ai_count = QUESTIONS_PER_CHAPTER - len(solr_questions)

    ai_questions = []
    if remaining_ai_count > 0:
        ai_questions = generate_mcqs_from_keywords(keyword_chunks, remaining_ai_count, chapter, "")
        print(f"[Info] AI generated {len(ai_questions)} questions.")

    all_questions = solr_questions + ai_questions

    used_keywords = set()
    for q in all_questions:
        q_text = f"{q['question_text']} {q.get('option_a','')} {q.get('option_b','')} {q.get('option_c','')} {q.get('option_d','')} {q.get('answer_explanation','')}"
        used_keywords.update(extract_keywords_in_text(q_text, keyword_list))

    missing_keywords = set(keyword_list) - used_keywords

    print(f"\n[Metrics] Keyword coverage for chapter '{chapter}':")
    print(f"  Used keywords: {len(used_keywords)} / {len(keyword_list)}")
    print(f"  Missing keywords: {len(missing_keywords)}")
    if missing_keywords:
        print(f"  Missing: {sorted(missing_keywords)}")

    MAX_EXTRA_QUESTIONS = 5
    if missing_keywords:
        print(f"[Info] Generating extra questions to cover missing keywords...")
        retry_chunks = [list(missing_keywords)]
        extra_questions = generate_mcqs_from_keywords(
            retry_chunks,
            min(MAX_EXTRA_QUESTIONS, len(missing_keywords)),
            chapter,
            ""
        )
        for q in extra_questions:
            q_text = f"{q['question_text']} {q.get('option_a','')} {q.get('option_b','')} {q.get('option_c','')} {q.get('option_d','')} {q.get('answer_explanation','')}"
            found = extract_keywords_in_text(q_text, missing_keywords)
            if found:
                all_questions.append(q)
                used_keywords.update(found)
                missing_keywords -= found
            if not missing_keywords:
                break

        print(f"[Metrics] After retry, used keywords: {len(used_keywords)} / {len(keyword_list)}")
        if missing_keywords:
            print(f"[Warning] Still missing: {sorted(missing_keywords)}")
        else:
            print("[Success] All keywords covered in questions.")

    insert_questions_to_local_db(all_questions)

    for i, q in enumerate(all_questions, 1):
        print(f"\nQ{i}: {q['question_text']}")
        print(f"  A. {q['option_a']}")
        print(f"  B. {q['option_b']}")
        print(f"  C. {q['option_c']}")
        print(f"  D. {q['option_d']}")
        print(f"  Correct Answer: {q['correct_answer']} - {q['correct_answer_text']}")
        print(f"  Explanation: {q['answer_explanation']}")
        q_text = f"{q['question_text']} {q.get('option_a','')} {q.get('option_b','')} {q.get('option_c','')} {q.get('option_d','')} {q.get('answer_explanation','')}"
        matched = extract_keywords_in_text(q_text, keyword_list)
        print(f"  [Matched keywords]: {sorted(matched)}")
        if len(matched) > 1:
            print(f"  [Combination]: {' + '.join(sorted(matched))}")

def run():
    structure = fetch_course_structure(COURSE_ID)
    data_by_chapter = defaultdict(lambda: defaultdict(list))
    for chapter, section, vid in structure:
        data_by_chapter[chapter][section].append(vid)

    for chapter, sections in data_by_chapter.items():
        process_chapter(chapter, sections)

if __name__ == "__main__":
    run()
