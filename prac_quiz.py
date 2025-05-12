import psycopg2
import requests
import time
import json
from collections import defaultdict
from datetime import datetime

# === CONFIG ===
COURSE_ID = 212
VIDEO_TYPE = 2
SUBJECT = "computer science"
LEVEL = "computer science"
FAST_MODE = True
QUESTIONS_PER_SECTION = 3 if FAST_MODE else 20
QUESTIONS_PER_CHAPTER = 5 if FAST_MODE else 50
AI_DELAY_SECONDS = 7
MAX_KEYWORDS = 15
MAX_RETRIES = 3
AI_URL = "http://164.52.212.233:8010/pi-chat-prod"
NLP_URL = "http://164.52.192.242:8001/search-nlp-keywords/"
HEADERS = {"Content-Type": "application/json"}

# === DB CONFIG ===
LOCAL_DB_CONFIG = {
    "dbname": "quiz_chaptermaster",
    "user": "postgres",
    "password": "Inetframe",
    "host": "localhost",
    "port": "5432"
}

# === UTILITIES ===

def clean_phrase(text):
    import re
    return " ".join(re.sub(r'[^a-zA-Z0-9\\s]', '', text.lower()).split())

def fetch_course_structure(course_id):
    query = f"""
    SELECT cs.chapter_name, cs.section_name, vm.video_id
    FROM "Lms_videomaster" vm
    JOIN "Lms_coursesections" cs ON vm.course_section_id = cs.id
    WHERE cs.course_content_id = {course_id} AND vm.type = {VIDEO_TYPE}
    ORDER BY cs.chapter_name, cs.cno;
    """
    with psycopg2.connect(dbname="piruby_db_v2", user="postgres", host="3.108.6.18",
                          password="prjeev@275", port="5432") as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()

def fetch_all_keywords(video_id):
    with psycopg2.connect(dbname="piruby_automation", user="postgres", host="164.52.194.25",
                          password="piruby@157", port="5432") as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT critical_all_keywords FROM public.cs_ee_5m_test
                           WHERE video_id = %s LIMIT 1""", (video_id,))
            result = cur.fetchone()
            if result and isinstance(result[0], list):
                return result[0][:20]
    return []

def get_weighted_keywords(text, subject, level):
    if not text.strip():
        return []
    payload = {
        'url': 'test',
        'section_title': [''],
        'section_para': text,
        'complete_sections': [{'end_index': len(text), 'start_index': 0, 'sectionName': '', 'level': [2]}],
        'offlineSubject': subject,
        'level': level,
        'is_nlp_server': True
    }
    try:
        res = requests.post(NLP_URL, json=payload, headers=HEADERS, timeout=30)
        if res.status_code == 200:
            raw_phrases = res.json().get("nlp_response_output", {}).get("phraseScorelist", [])
            return [clean_phrase(p[0]) for p in sorted(raw_phrases, key=lambda x: -x[1])][:20]
    except Exception as e:
        print(f"[Error] NLP keyword extraction failed: {e}")
    return []

def generate_mcqs_from_keywords(keywords, count):
    prompt = f'''
Generate {count} computer science MCQs strictly focused on questions that include relevant code snippets using the following keywords:
{', '.join(keywords)}

Return ONLY a valid JSON list where each question strictly contains a code snippet for context and follows this format:
{{
  "question_text": "Your question here, must include a code snippet",
  "option_a": "Option A",
  "option_b": "Option B",
  "option_c": "Option C",
  "option_d": "Option D",
  "correct_answer": "C",
  "correct_answer_text": "Full answer text of correct option",
  "answer_explanation": "Detailed explanation including code analysis",
  "difficulty_level": "L1",
  "questiontype": "Single",
  "subject": "{SUBJECT}",
  "course": "{LEVEL}",
  "chapter": "Test Chapter",
  "section_name": "Test Section"
}}
Only output the JSON list — no explanation.
'''
    payload = {"prompt": prompt}
    time.sleep(AI_DELAY_SECONDS)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = requests.post(AI_URL, headers=HEADERS, json=payload, timeout=60)
            res.raise_for_status()
            full_response = res.json()
            print("=== RAW AI RESPONSE ===")
            print(full_response)
            raw_text = full_response.get("response") or full_response.get("content", "")
            return json.loads(raw_text)
        except Exception as e:
            print(f"[AI Error] Attempt {attempt}: {e}")
            time.sleep(AI_DELAY_SECONDS)
    return []

def insert_questions_to_db(questions):
    try:
        conn = psycopg2.connect(**LOCAL_DB_CONFIG)
        cur = conn.cursor()
        for idx, q in enumerate(questions):
            try:
                cur.execute(
                    '''INSERT INTO public."BaseModel_quizchaptermaster"
                    (question_text, option_a, option_b, option_c, option_d, correct_answer,
                     correct_answer_text, answer_explanation, difficulty_level, questiontype,
                     subject, course, chapter, section_name)
                     VALUES (%(question_text)s, %(option_a)s, %(option_b)s, %(option_c)s, %(option_d)s, %(correct_answer)s,
                             %(correct_answer_text)s, %(answer_explanation)s, %(difficulty_level)s, %(questiontype)s,
                             %(subject)s, %(course)s, %(chapter)s, %(section_name)s)
                    ''', q
                )
                print(f"[Insert] Question {idx+1} inserted.")
            except Exception as e:
                print(f"[DB Insert Error] Q{idx+1}: {e}")
        conn.commit()
    except Exception as e:
        print(f"[DB Connection Error] {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

def process_section(section, vids):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Processing section: {section}")
    keywords = []
    for vid in vids:
        kws = fetch_all_keywords(vid)
        if isinstance(kws, list):
            keywords.extend(kws)
    text_blob = " ".join(keywords)
    weighted = get_weighted_keywords(text_blob, SUBJECT, LEVEL)
    if not weighted:
        print(f"[Skip] No weighted keywords for section '{section}'")
        return []
    return generate_mcqs_from_keywords(weighted, QUESTIONS_PER_SECTION)

def generate_quiz(course_id):
    print(f"== Generating quiz for course ID {course_id} ==")
    structure = fetch_course_structure(course_id)
    data_by_chapter = defaultdict(lambda: defaultdict(list))
    for chapter, section, vid in structure:
        data_by_chapter[chapter][section].append(vid)

    for chap, sections in data_by_chapter.items():
        for section, vids in sections.items():
            questions = process_section(section, vids)
            if questions:
                for q in questions:
                    q["chapter"] = chap
                    q["section_name"] = section
                insert_questions_to_db(questions)
    print("[Complete] All questions generated and saved.")

# === Run ===
generate_quiz(COURSE_ID)
