import json
import re
import requests
import psycopg2
import time
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

LOCAL_DB_CONFIG = {
    'dbname': 'quiz_chaptermaster',
    'user': 'postgres',
    'password': 'Inetframe',
    'host': 'localhost',
    'port': '5432'
}

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

def clean_phrase(text):
    return " ".join(re.sub(r'[^a-zA-Z0-9\s]', '', text.lower()).split())

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
            data = res.json().get("nlp_response_output", {})
            raw_phrases = data.get("phraseScorelist", [])
            return [clean_phrase(p[0]) for p in sorted(raw_phrases, key=lambda x: -x[1])][:20]
    except Exception as e:
        print(f"[Error] NLP keyword extraction failed: {e}")
    return []

def generate_mcqs_from_keywords(keywords, count):
    if not keywords:
        print("[Warning] No keywords provided — Skipping MCQ generation")
        return None

    keywords = keywords[:MAX_KEYWORDS]
    prompt = f'''
Using the following list of keywords, generate {count} high-quality multiple-choice questions (MCQs) tailored for undergraduate Computer Science students.

Instructions:
- Each MCQ must consist of a clear question stem, 4 answer choices (1 correct + 3 distractors), and a difficulty tag: L1, L2, or L3.
- Provide metadata after each question: Type, Keywords used, Difficulty.

Keywords:
{', '.join(keywords)}
'''
    payload = {"prompt": prompt}
    time.sleep(AI_DELAY_SECONDS)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = requests.post(AI_URL, headers=HEADERS, json=payload, timeout=60)
            if res.status_code == 200:
                return res.json()
            else:
                print(f"[Warning] AI generation failed (Attempt {attempt}) — Status code: {res.status_code}")
        except Exception as e:
            print(f"[Error] AI MCQ generation failed (Attempt {attempt}): {e}")
        time.sleep(AI_DELAY_SECONDS)
    print("[Final Warning] Skipped this generation after 3 failed attempts.")
    return None

def parse_ai_questions(ai_response):
    questions = []
    try:
        content = ai_response.get('content', '')
        print(f"[Debug] AI raw content: {content[:500]}...")

        blocks = re.split(r'\n\s*\d+\.\s*', content.strip())
        for block in blocks:
            if not block.strip():
                continue

            # Extract question
            question_match = re.match(r'^(.*?)\n\s*a\)', block, re.IGNORECASE | re.DOTALL)
            if not question_match:
                continue
            question_text = question_match.group(1).strip()

            # Extract options
            options = re.findall(r'[a-dA-D]\)\s*(.*?)\s*(?=\n[a-dA-D]\)|\n?\Z)', block, re.IGNORECASE)
            if len(options) < 4:
                continue

            # Extract metadata block
            meta_match = re.search(r'{(.*?)}', block, re.DOTALL)
            difficulty = "L1"
            qtype = "MCQ"
            keywords = []
            correct_option = "A"  # fallback default

            if meta_match:
                meta = meta_match.group(1)

                diff_match = re.search(r'Difficulty[:\s]*(L\d)', meta)
                if diff_match:
                    difficulty = diff_match.group(1)

                kw_match = re.search(r'Keywords[:\s]*(.*)', meta)
                if kw_match:
                    keywords = [k.strip() for k in kw_match.group(1).split(',') if k.strip()]

                type_match = re.search(r'Type[:\s]*(.*?)($|,)', meta)
                if type_match:
                    qtype = type_match.group(1).strip()

            # Try to find correct answer if present
            correct_match = re.search(r'Correct Answer[:\s]*([A-Da-d])', block)
            if correct_match:
                correct_option = correct_match.group(1).upper()

            questions.append({
                "question": question_text,
                "options": options[:4],
                "correct_option": correct_option,
                "difficulty": difficulty,
                "type": qtype,
                "keywords": keywords
            })

    except Exception as e:
        print(f"[Error] Failed to parse AI response: {e}")
    return questions

def insert_question_to_local_db(local_conn, chapter, section, q_data):
    try:
        with local_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO quiz_chaptermaster (
                    chapter_name, section_name, question_text,
                    option_a, option_b, option_c, option_d,
                    correct_option, difficulty_level, question_type, keywords
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                chapter,
                section,
                q_data.get('question', ''),
                q_data.get('options', ['','','',''])[0],
                q_data.get('options', ['','','',''])[1],
                q_data.get('options', ['','','',''])[2],
                q_data.get('options', ['','','',''])[3],
                q_data.get('correct_option', 'A'),
                q_data.get('difficulty', 'L1'),
                q_data.get('type', 'Single'),
                ", ".join(q_data.get('keywords', []))
            ))
            print(f"[DB] Inserted question: {q_data.get('question', '')[:50]}...")
    except Exception as e:
        print(f"[Error] Failed to insert question into DB: {e}")

def process_section(section, vids, chapter, local_conn):
    print(f"   [{datetime.now().strftime('%H:%M:%S')}] Processing section: {section}")

    keywords = []
    for vid in vids:
        kws = fetch_all_keywords(vid)
        if isinstance(kws, list):
            keywords.extend(kws)

    text_blob = " ".join(keywords)
    weighted = get_weighted_keywords(text_blob, SUBJECT, LEVEL)

    if not weighted:
        print(f"    No weighted keywords for section '{section}' — Skipping MCQ generation")
        return

    ai_response = generate_mcqs_from_keywords(weighted, QUESTIONS_PER_SECTION)

    if ai_response:
        extracted_questions = parse_ai_questions(ai_response)
        if extracted_questions:
            for idx, q in enumerate(extracted_questions, 1):
                insert_question_to_local_db(local_conn, chapter, section, q)
        else:
            print(f"[Warning] No valid questions parsed for section {section}")
    else:
        print(f"[Warning] No AI response received for section {section}")

def process_chapter(chapter, sections_dict, local_conn):
    print(f"\n [{datetime.now().strftime('%H:%M:%S')}] Processing chapter: {chapter}")
    for section, vids in sections_dict.items():
        process_section(section, vids, chapter, local_conn)

def generate_quiz_sequential(course_id):
    print(f"\n Starting quiz generation for course ID: {course_id}")

    structure = fetch_course_structure(course_id)
    data_by_chapter = defaultdict(lambda: defaultdict(list))
    for chapter, section, vid in structure:
        data_by_chapter[chapter][section].append(vid)

    try:
        with psycopg2.connect(**LOCAL_DB_CONFIG) as local_conn:
            for chap, sections in data_by_chapter.items():
                process_chapter(chap, sections, local_conn)
            local_conn.commit()
            print("[DB] All inserts committed.")
    except Exception as e:
        print(f"[Error] Could not connect to local DB: {e}")

    print(f"\n Quiz generation complete. Questions saved to local database.")

if __name__ == "__main__":
    generate_quiz_sequential(COURSE_ID)
