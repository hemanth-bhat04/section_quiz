import psycopg2
import json

# === DB CONFIG ===
LOCAL_DB_CONFIG = {
    "dbname": "quiz_gen",
    "user": "postgres",
    "password": "Inetframe",
    "host": "localhost",
    "port": "5432"
}

def insert_questions(course_id, chapter, section, questions):
    if not questions:
        print("⚠️ No questions to insert.")
        return

    print(f"📥 Inserting {len(questions)} question(s) into database...")

    try:
        with psycopg2.connect(**LOCAL_DB_CONFIG) as conn:
            with conn.cursor() as cur:
                for q in questions:
                    print(f"📝 Inserting: {q.get('question')[:60]}...")
                    cur.execute("""
                        INSERT INTO quiz_question (
                            question_text, option_a, option_b, option_c, option_d,
                            correct_answer, explanation, course_id, chapter,
                            section, subject, difficulty, keywords
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        q.get('question'),
                        q['options'][0] if len(q['options']) > 0 else '',
                        q['options'][1] if len(q['options']) > 1 else '',
                        q['options'][2] if len(q['options']) > 2 else '',
                        q['options'][3] if len(q['options']) > 3 else '',
                        q.get('correct_option', ''),
                        "Keywords: " + ", ".join(q.get('keywords', [])),
                        course_id,
                        chapter,
                        section,
                        "computer science",
                        q.get('difficulty', 'L1'),
                        json.dumps(q.get('keywords', [])),
                    ))
        print("✅ All questions inserted successfully.")
    except Exception as e:
        print("❌ ERROR inserting into DB:", e)
