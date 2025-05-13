import requests
import re
import html
import psycopg2
import json
from itertools import combinations
from datetime import datetime
from collections import defaultdict, Counter
from nlp_keywords import get_weighted_queries, cleanPhraseFirst

# === CONFIG ===
NLP_URL = "http://164.52.192.242:8001/search-nlp-keywords/"
HEADERS = {"Content-Type": "application/json"}
MAX_KEYWORDS = 20
COMBINED_KEYWORDS_LIMIT = 50
SOLR_URL = 'http://164.52.201.193:8983/solr/rp-quiz'
SUBJECT = "computer science"
LEVEL = "computer science"
VIDEO_TYPE = 2
COURSE_ID = 212

# === DB CONFIG ===
LOCAL_DB_CONFIG = {
    "dbname": "quiz_chaptermaster",
    "user": "postgres",
    "password": "Hemanth",
    "host": "localhost",
    "port": "5432"
}

# === DB FUNCTIONS ===
def fetch_all_keywords(video_id):
    try:
        with psycopg2.connect(dbname="piruby_automation", user="postgres", host="164.52.194.25",
                              password="piruby@157", port="5432") as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT critical_all_keywords FROM public.cs_ee_5m_test
                               WHERE video_id = %s LIMIT 1""", (video_id,))
                result = cur.fetchone()
                if result and isinstance(result[0], list):
                    return result[0][:MAX_KEYWORDS]
    except Exception as e:
        print(f"[DB Keyword Fetch Error] {e}")
    return []

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

# === SOLR UTILS ===
def query_solr_with_boosted_keywords(keyword_weight_dict):
    query_parts = []
    for phrase, weight in keyword_weight_dict.items():
        weight = min(round(weight, 2), 3.5)
        if ' ' in phrase:
            query_parts.append(f'"{phrase}"^{weight}')
        else:
            query_parts.append(f'{phrase}^{weight}')
    query = ' OR '.join(query_parts)

    fq = 'level:degree'
    qf = 'question^5 chapter_name^2 explanation'
    hl_fl = 'fieldspellcheck_en'
    params = {
        'q': query,
        'qf': qf,
        'fq': fq,
        'defType': 'edismax',
        'indent': 'on',
        'fl': 'id,score,question,option1,option2,option3,option4,answer,explanation',
        'wt': 'json',
        'rows': 100,
        'hl': 'true',
        'hl.q': query,
        'hl.fl': hl_fl,
        'hl.usePhraseHighlighter': 'true',
        'hl.method': 'unified',
        'hl.snippets': '1000',
    }
    try:
        res = requests.get(f'{SOLR_URL}/select', params=params, timeout=30)
        res.raise_for_status()
        data = res.json()
        return data.get('response', {}).get('docs', [])
    except Exception as e:
        print(f"[Solr Error] {e}")
        return []

# === MAIN FLOW ===
def process_section(section_name, chapter_name, video_ids):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Processing section: {section_name}")
    phrase_weights = defaultdict(list)
    phrase_counts = Counter()

    for vid in video_ids:
        print(f"[DEBUG] Video ID {vid} - fetching 5-min keywords")
        five_min_kws = fetch_all_keywords(vid)
        print(f"[DEBUG] 5-min Keywords: {five_min_kws}")
        text_blob = ' '.join(five_min_kws)
        _, phrasescorelist, _, _ = get_weighted_queries(text_blob, len(text_blob), SUBJECT, LEVEL)
        print(f"[DEBUG] NLP PhraseScoreList: {phrasescorelist}")

        for phrase, score in phrasescorelist:
            cleaned = cleanPhraseFirst(phrase)
            if score > 1.0 or (' ' in cleaned and score >= 1.0):  # only accept strong or multiword
                phrase_weights[cleaned].append(score)
                phrase_counts[cleaned] += 1

    final_weights = {}
    print(f"[INFO] Weighted keyword candidates for section '{section_name}':")
    for phrase, scores in phrase_weights.items():
        avg_weight = sum(scores) / len(scores)
        if phrase_counts[phrase] > 1 and avg_weight == 1.0:
            boost = min(0.1 * (phrase_counts[phrase] - 1), 0.5)
            avg_weight = min(avg_weight + boost, 1.5)
            final_weights[phrase] = min(avg_weight, 3.5)
        print(f" - {phrase}: {final_weights[phrase]:.2f}")

    top_phrases = dict(sorted(final_weights.items(), key=lambda x: -x[1])[:COMBINED_KEYWORDS_LIMIT])

    if not top_phrases:
        print(f"[Skip] No strong keywords for section {section_name}")
        return

    docs = query_solr_with_boosted_keywords(top_phrases)

    quiz_questions = []
    for doc in docs:
        options = [doc.get(f'option{i}', '') for i in range(1, 5)]
        correct_text = doc.get('answer', '')
        correct_letter = next((chr(65+i) for i, opt in enumerate(options) if opt.strip() == correct_text.strip()), 'A')

        quiz_questions.append({
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
            "chapter": chapter_name,
            "section_name": section_name
        })

    insert_questions_to_db(quiz_questions)

# === DRIVER ===
def run():
    structure = fetch_course_structure(COURSE_ID)
    data_by_chapter = defaultdict(lambda: defaultdict(list))
    for chapter, section, vid in structure:
        data_by_chapter[chapter][section].append(vid)

    for chap, sections in data_by_chapter.items():
        for section, vids in sections.items():
            process_section(section, chap, vids)

if __name__ == "__main__":
    run()
