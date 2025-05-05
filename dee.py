from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import requests
import psycopg2
from collections import defaultdict
import time
from datetime import datetime
from dee_1 import insert_questions

# === CONFIG ===
COURSE_ID = 212
VIDEO_TYPE = 2
SUBJECT = "computer science"
LEVEL = "computer science"
FAST_MODE = True

QUESTIONS_PER_SECTION = 3 if FAST_MODE else 20
QUESTIONS_PER_CHAPTER = 5 if FAST_MODE else 50
AI_DELAY_SECONDS = 7  # Increased delay between AI calls
MAX_KEYWORDS = 15     # Cap keywords passed to AI
MAX_RETRIES = 3       # Increase retries to 3

AI_URL = "http://164.52.212.233:8010/pi-chat-prod"
NLP_URL = "http://164.52.192.242:8001/search-nlp-keywords/"
HEADERS = {"Content-Type": "application/json"}

# === DB FUNCTIONS ===

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
            rows = cur.fetchall()
    return rows

def fetch_all_keywords(video_id):
    with psycopg2.connect(dbname="piruby_automation", user="postgres", host="164.52.194.25",
                          password="piruby@157", port="5432") as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT critical_all_keywords FROM public.cs_ee_5m_test
                           WHERE video_id = %s LIMIT 1""", (video_id,))
            result = cur.fetchone()
            if result and isinstance(result[0], list):
                keywords = result[0]
                if keywords:
                    return keywords[:20]
    return []

# === NLP & AI UTILITIES ===

def clean_phrase(text):
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
    return " ".join(text.split())

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
- Each MCQ must consist of a clear question stem, 4 answer choices (1 correct + 3 well-reasoned distractors), and a difficulty level tag: L1 (basic), L2 (intermediate), or L3 (advanced).
- Ensure the options are conceptually close, plausible, and challenge critical thinking—avoid obvious wrong choices.
- Generate two types of questions:
  1. **Single-keyword questions**: Focus on the understanding or application of a single keyword or concept.
  2. **Multi-keyword questions**: Integrate two or more keywords to frame a question that connects multiple ideas or topics.
- Use only relevant keywords based on context. Discard vague, generic, or out-of-scope terms.
- After each MCQ, add metadata in the following format:
  - Type: Single / Multi
  - Keywords used: list them clearly
  - Difficulty: L1 / L2 / L3

Make the questions academically sound, unambiguous, and varied in format (definition, scenario-based, conceptual, application).

Keywords:
{', '.join(keywords)}
'''
    payload = {"prompt": prompt}

    print(f"[Info] Generating MCQs | Keywords count: {len(keywords)} | Prompt length: {len(prompt)} characters")
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

# === SEQUENTIAL QUIZ GENERATION ===

def process_section(section, vids):
    start_time = time.time()
    print(f"   [{datetime.now().strftime('%H:%M:%S')}] Processing section: {section} (Videos: {len(vids)})")

    keywords = []
    for vid in vids:
        kws = fetch_all_keywords(vid)
        if isinstance(kws, list):
            keywords.extend(kws)

    text_blob = " ".join(keywords)
    weighted = get_weighted_keywords(text_blob, SUBJECT, LEVEL)

    if not weighted:
        print(f"    No weighted keywords for section '{section}' — Skipping MCQ generation")
        return section, {"keywords": [], "questions": None}

    qns = generate_mcqs_from_keywords(weighted, QUESTIONS_PER_SECTION)

    elapsed = time.time() - start_time
    print(f"    Finished section: {section} in {elapsed:.2f}s")
    return section, {"keywords": weighted, "questions": qns}

def process_chapter(chapter, sections_dict):
    start_time = time.time()
    print(f"\n [{datetime.now().strftime('%H:%M:%S')}] Processing chapter: {chapter}")

    chapter_keywords = []
    chapter_data = {"sections": {}, "chapter_questions": None}

    # Process sections sequentially
    for section, vids in sections_dict.items():
        section_name, result = process_section(section, vids)
        chapter_data["sections"][section_name] = result
        chapter_keywords.extend(result["keywords"])

    deduped_keywords = list(dict.fromkeys(chapter_keywords))[:MAX_KEYWORDS]

    if not deduped_keywords:
        print(f" No aggregated keywords for chapter '{chapter}' — Skipping chapter MCQs")
        chapter_data["chapter_questions"] = {"keywords": [], "questions": None}
    else:
        print(f" Generating chapter-level MCQs for: {chapter}")
        chapter_data["chapter_questions"] = {
            "keywords": deduped_keywords,
            "questions": generate_mcqs_from_keywords(deduped_keywords, QUESTIONS_PER_CHAPTER)
        }

    elapsed = time.time() - start_time
    print(f" Finished chapter: {chapter} in {elapsed:.2f}s")
    return chapter, chapter_data

def generate_quiz_sequential(course_id):
    print(f"\n Starting SEQUENTIAL quiz generation for course ID: {course_id}")
    start_time = time.time()

    structure = fetch_course_structure(course_id)
    data_by_chapter = defaultdict(lambda: defaultdict(list))
    for chapter, section, vid in structure:
        data_by_chapter[chapter][section].append(vid)

    quiz_output = {"chapters": {}}

    for chap, sections in data_by_chapter.items():
        chapter_name, chapter_result = process_chapter(chap, sections)
        quiz_output["chapters"][chapter_name] = chapter_result

    with open("quiz_output.json", "w") as f:
        json.dump(quiz_output, f, indent=2)

    total_elapsed = time.time() - start_time
    print(f"\n SEQUENTIAL quiz generation complete in {total_elapsed:.2f}s. Output saved to quiz_output.json")

# === Trigger ===
generate_quiz_sequential(COURSE_ID)