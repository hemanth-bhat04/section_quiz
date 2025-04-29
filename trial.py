import json
import re
import requests
import psycopg2
from collections import defaultdict

# === CONFIG ===
COURSE_ID = 30
SERVER_TYPE = 'dev'
VIDEO_TYPE = 2
QUESTIONS_PER_SECTION = 20
QUESTIONS_PER_CHAPTER = 50
SUBJECT = "computer science"
LEVEL = "computer science"

AI_URL = "http://164.52.212.233:8010/pi-chat-prod"
NLP_URL = "http://164.52.192.242:8001/search-nlp-keywords/"
HEADERS = {"Content-Type": "application/json"}

# === DB CONNECTIONS ===

def get_course_vids_secs(course_id, server_type, video_type):
    query = f"""SELECT DISTINCT video_id, course_section_id FROM "Lms_videomaster"
    WHERE course_section_id IN (SELECT id FROM "Lms_coursesections"
    WHERE course_content_id = {course_id} ORDER BY cno) AND type = {video_type}"""
    
    host = "3.108.6.18" if server_type == "dev" else "216.48.176.169"
    port = "5432" if server_type == "dev" else "6432"

    with psycopg2.connect(dbname="piruby_db_v2", user="postgres", host=host,
                          password="prjeev@275", port=port) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [row[0] for row in rows], [row[1] for row in rows]

def fetch_all_keywords(video_id):
    with psycopg2.connect(dbname="piruby_automation", user="postgres", host="164.52.194.25",
                          password="piruby@157", port="5432") as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT critical_all_keywords FROM public.cs_ee_5m_test
                           WHERE video_id = %s LIMIT 1""", (video_id,))
            result = cur.fetchone()
            return result[0] if result else []

# === NLP & AI ===

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

    res = requests.post(NLP_URL, json=payload, headers=HEADERS, timeout=60)
    if res.status_code == 200:
        data = res.json().get("nlp_response_output", {})
        raw_phrases = data.get("phraseScorelist", [])
        return [clean_phrase(p[0]) for p in sorted(raw_phrases, key=lambda x: -x[1])][:20]
    else:
        print("⚠️ NLP failed:", res.status_code)
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
    res = requests.post(AI_URL, headers=HEADERS, json=payload, timeout=200)
    return res.json() if res.status_code == 200 else None

# === MAIN CONTROLLER ===

def process_course_sections(course_id):
    video_ids, section_ids = get_course_vids_secs(course_id, SERVER_TYPE, VIDEO_TYPE)

    section_map = defaultdict(list)
    for vid, sec in zip(video_ids, section_ids):
        section_map[sec].append(vid)

    all_section_questions = {}
    all_keywords = []

    for sec_id, vids in section_map.items():
        print(f"\n🔍 Processing Section: {sec_id}")
        section_keywords = []
        for vid in vids:
            keywords = fetch_all_keywords(vid)
            if isinstance(keywords, list):
                section_keywords.extend(keywords)

        text_blob = " ".join(section_keywords)
        top_keywords = get_weighted_keywords(text_blob, SUBJECT, LEVEL)
        all_keywords.extend(top_keywords)

        print(f"🧠 Top 20 keywords for section {sec_id}: {top_keywords}")
        questions = generate_mcqs_from_keywords(top_keywords, QUESTIONS_PER_SECTION)
        all_section_questions[sec_id] = questions

    # Chapter level
    print("\n📘 Generating Chapter-Level MCQs...")
    chapter_keywords = list(dict.fromkeys(all_keywords))
    chapter_questions = generate_mcqs_from_keywords(chapter_keywords, QUESTIONS_PER_CHAPTER)

    # Final Output
    output = {
        "section_questions": all_section_questions,
        "chapter_questions": chapter_questions
    }

    with open("quiz_output.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\n✅ Quiz generation complete. Results saved to quiz_output.json")
    return output

# Run
if __name__ == "__main__":
    process_course_sections(COURSE_ID)
