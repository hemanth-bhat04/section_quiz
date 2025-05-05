import psycopg2
import requests
import json
import time
import re

# === CONFIG ===
COURSE_ID = 212
CHAPTER = "Chapter 1"
SECTION = "Section A"
SUBJECT = "computer science"
LEVEL = "computer science"

AI_URL = "http://164.52.212.233:8010/pi-chat-prod"
HEADERS = {"Content-Type": "application/json"}
AI_DELAY_SECONDS = 5
MAX_KEYWORDS = 15

# === DB CONFIG (LOCAL) ===
LOCAL_DB_CONFIG = {
    "dbname": "quiz_gen",
    "user": "postgres",
    "password": "Inetframe",
    "host": "localhost",
    "port": "5432"
}

# === Insert Questions ===
def insert_questions(course_id, chapter, section, questions):
    if not questions:
        print("⚠️ No questions to insert")
        return

    try:
        with psycopg2.connect(**LOCAL_DB_CONFIG) as conn:
            with conn.cursor() as cur:
                for q in questions:
                    cur.execute("""
                        INSERT INTO public."BaseModel_quizchaptermaster" (
                            content, questions, option_a, option_b, option_c, option_d,
                            correct_answer, answer_explanation, course, chapter,
                            section_name, subject, difficulty_level, tags
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        q.get('question'),  # content
                        q.get('question'),  # questions
                        q['options'][0] if len(q['options']) > 0 else '',
                        q['options'][1] if len(q['options']) > 1 else '',
                        q['options'][2] if len(q['options']) > 2 else '',
                        q['options'][3] if len(q['options']) > 3 else '',
                        q['correct_option'],
                        f"Keywords: {', '.join(q.get('keywords', []))}",
                        str(course_id),
                        chapter or '',
                        section or '',
                        "computer science",
                        q.get('difficulty', 'L1'),
                        json.dumps(q.get('keywords', [])),
                    ))
        print(f"✅ Successfully inserted {len(questions)} questions into local DB.")
    except Exception as e:
        print(f"❌ DB Insertion Error: {e}")
        print("❌ Last question attempted:", q)

# === Get MCQs from GPT ===
def generate_mcqs_from_keywords(keywords, count=5):
    if not keywords:
        print("[Warning] No keywords provided")
        return None

    keywords = keywords[:MAX_KEYWORDS]
    prompt = f'''
Using the following list of keywords, generate {count} high-quality multiple-choice questions (MCQs) tailored for undergraduate Computer Science students.

Instructions:
- Each MCQ must consist of a clear question stem, 4 answer choices (1 correct + 3 well-reasoned distractors), and a difficulty level tag: L1 (basic), L2 (intermediate), or L3 (advanced).
- Ensure the options are conceptually close and challenge critical thinking.
- After each MCQ, add metadata:
  - Type: Single / Multi
  - Keywords used
  - Difficulty: L1 / L2 / L3

Keywords:
{', '.join(keywords)}
'''

    print(f"[Info] Generating MCQs from GPT | Prompt length: {len(prompt)}")
    time.sleep(AI_DELAY_SECONDS)

    try:
        res = requests.post(AI_URL, headers=HEADERS, json={"prompt": prompt}, timeout=60)
        if res.status_code == 200:
            return res.json()
        else:
            print(f"[Error] GPT API response code: {res.status_code}")
    except Exception as e:
        print(f"[Error] GPT API call failed: {e}")

    return None

# === Clean/Parse GPT MCQ Output ===
def parse_mcq_output(data):
    """
    Expects GPT response like: {"choices": [ {question, options, correct_option, ...}, ... ]}
    """
    if not data or "choices" not in data:
        return []

    result = []
    for item in data["choices"]:
        try:
            # Basic validation
            if 'question' in item and 'options' in item and len(item['options']) == 4:
                result.append({
                    "question": item["question"],
                    "options": item["options"],
                    "correct_option": item.get("correct_option", "A"),
                    "difficulty": item.get("difficulty", "L1"),
                    "type": item.get("type", "Single"),
                    "keywords": item.get("keywords", []),
                })
        except Exception as e:
            print(f"[Warning] Skipping malformed item: {e}")

    return result

# === Main Flow ===
def main():
    sample_keywords = [
        "algorithm", "data structure", "recursion", "complexity",
        "sorting", "hashing", "stack", "queue", "binary tree"
    ]

    raw = generate_mcqs_from_keywords(sample_keywords, count=5)
    parsed_questions = parse_mcq_output(raw)
    insert_questions(COURSE_ID, CHAPTER, SECTION, parsed_questions)

if __name__ == "__main__":
    main()
