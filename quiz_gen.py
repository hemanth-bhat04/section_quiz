from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import requests
import psycopg2
from collections import defaultdict
import time
from datetime import datetime

# === CONFIG ===
COURSE_ID = 212
VIDEO_TYPE = 2
SUBJECT = "computer science"
LEVEL = "computer science"
FAST_MODE = True

QUESTIONS_PER_SECTION = 3 if FAST_MODE else 20
QUESTIONS_PER_CHAPTER = 5 if FAST_MODE else 50

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
            return result[0] if result else []

# === NLP & AI UTILITIES ===

def clean_phrase(text):
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
    return " ".join(text.split())

def get_weighted_keywords(text, subject, level):
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
    except:
        pass
    return []

def generate_mcqs_from_keywords(keywords, count):
    prompt = f'''
Using the following list of keywords, generate {count} multiple-choice questions (MCQs) for degree-level Computer Science students.

Instructions:
- Each MCQ must have 1 correct answer and 3 plausible distractors.
- Tag each question with a difficulty level: L1, L2, or L3.
- Create two types of questions:
  1. Individual-topic questions: focus on understanding a single keyword or concept.
  2. Combination-topic questions: use two or more related keywords to frame a question.
- After the MCQs, indicate for each question if it’s based on an individual keyword or a combination, and list the keywords used.
- Exclude irrelevant or out-of-context keywords.

Keywords:
{', '.join(keywords)}
'''
    payload = {"prompt": prompt}
    try:
        res = requests.post(AI_URL, headers=HEADERS, json=payload, timeout=60)
        return res.json() if res.status_code == 200 else None
    except:
        return None

# === PARALLEL QUIZ GENERATION ===

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
    qns = generate_mcqs_from_keywords(weighted, QUESTIONS_PER_SECTION)

    elapsed = time.time() - start_time
    print(f"    Finished section: {section} in {elapsed:.2f}s")
    return section, {"keywords": weighted, "questions": qns}

def process_chapter(chapter, sections_dict):
    start_time = time.time()
    print(f"\n [{datetime.now().strftime('%H:%M:%S')}] Processing chapter: {chapter}")

    chapter_keywords = []
    chapter_data = {"sections": {}, "chapter_questions": None}
    futures = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        for section, vids in sections_dict.items():
            futures.append(executor.submit(process_section, section, vids))
        for fut in as_completed(futures):
            section_name, result = fut.result()
            chapter_data["sections"][section_name] = result
            chapter_keywords.extend(result["keywords"])

    deduped_keywords = list(dict.fromkeys(chapter_keywords))

    print(f" Generating chapter-level MCQs for: {chapter}")
    chapter_data["chapter_questions"] = {
        "keywords": deduped_keywords,
        "questions": generate_mcqs_from_keywords(deduped_keywords, QUESTIONS_PER_CHAPTER)
    }

    elapsed = time.time() - start_time
    print(f" Finished chapter: {chapter} in {elapsed:.2f}s")
    return chapter, chapter_data

def generate_quiz_parallel(course_id):
    print(f"\n Starting parallel quiz generation for course ID: {course_id}")
    start_time = time.time()

    structure = fetch_course_structure(course_id)
    data_by_chapter = defaultdict(lambda: defaultdict(list))
    for chapter, section, vid in structure:
        data_by_chapter[chapter][section].append(vid)

    quiz_output = {"chapters": {}}
    futures = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        for chap, sections in data_by_chapter.items():
            futures.append(executor.submit(process_chapter, chap, sections))
        for fut in as_completed(futures):
            chapter_name, chapter_result = fut.result()
            quiz_output["chapters"][chapter_name] = chapter_result

    with open("quiz_output.json", "w") as f:
        json.dump(quiz_output, f, indent=2)

    total_elapsed = time.time() - start_time
    print(f"\n Parallel quiz generation complete in {total_elapsed:.2f}s. Output saved to quiz_output.json")

# Trigger
generate_quiz_parallel(COURSE_ID)

