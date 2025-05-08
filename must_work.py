import psycopg2
import requests
import time
import json

# Config
AI_URL = "http://164.52.212.233:8010/pi-chat-prod"
HEADERS = {"Content-Type": "application/json"}
LOCAL_DB_CONFIG = {
    "dbname": "quiz_chaptermaster",
    "user": "postgres",
    "password": "Hemanth",
    "host": "localhost",
    "port": "5432"
}

# Sample test keywords
keywords = ["supervised learning", "Q-learning", "reinforcement"]

def generate_mcqs(keywords, count=1):
    prompt = f'''
Generate {count} computer science MCQs using the following keywords:
{', '.join(keywords)}

Return ONLY a valid JSON list where each question has this format:
{{
  "question_text": "Your question here",
  "option_a": "Option A",
  "option_b": "Option B",
  "option_c": "Option C",
  "option_d": "Option D",
  "correct_answer": "C",
  "correct_answer_text": "Full answer text of correct option",
  "answer_explanation": "Why this is correct",
  "difficulty_level": "L1",
  "questiontype": "Single",
  "subject": "computer science",
  "course": "computer science",
  "chapter": "Test Chapter",
  "section_name": "Test Section"
}}
Only output the JSON list — no explanation.
'''
    payload = {"prompt": prompt}
    time.sleep(2)
    try:
        res = requests.post(AI_URL, headers=HEADERS, json=payload, timeout=60)
        res.raise_for_status()
        full_response = res.json()
        print("=== RAW FULL RESPONSE ===")
        print(full_response)

        response_text = full_response.get("response") or full_response.get("content", "")
        return json.loads(response_text)
    except Exception as e:
        print(f"[AI Error] {e}")
        return []

def insert_question(q):
    try:
        conn = psycopg2.connect(**LOCAL_DB_CONFIG)
        cur = conn.cursor()

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
        conn.commit()
        print("[Success] Question inserted.")
    except Exception as e:
        print(f"[DB Error] {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

# === Run test ===
questions = generate_mcqs(keywords, 1)
for q in questions:
    insert_question(q)