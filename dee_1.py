import psycopg2
import json

# === DB CONFIG (LOCAL) ===
LOCAL_DB_CONFIG = {
    "dbname": "quiz_gen",
    "user": "postgres",
    "password": "Inetframe",
    "host": "localhost",
    "port": "5432"
}

def insert_questions(course_id, chapter, section, questions):
    """
    Insert a list of questions into the local DB (BaseModel_quizchaptermaster table).
    
    Each question should be a dict with:
        question, options (list of 4), correct_option, difficulty, type, keywords (list)
    """
    if not questions:
        print("⚠️ No questions to insert")
        return

    try:
        with psycopg2.connect(**LOCAL_DB_CONFIG) as conn:
            with conn.cursor() as cur:
                for q in questions:
                    # Map the question data to the database schema
                    cur.execute("""
                        INSERT INTO public."BaseModel_quizchaptermaster" (
                            content, questions, option_a, option_b, option_c, option_d,
                            correct_answer, answer_explanation, course, chapter,
                            section_name, subject, difficulty_level, tags
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        q.get('question'),  # content
                        q.get('question'),  # questions
                        q['options'][0] if len(q['options']) > 0 else '',  # option_a
                        q['options'][1] if len(q['options']) > 1 else '',  # option_b
                        q['options'][2] if len(q['options']) > 2 else '',  # option_c
                        q['options'][3] if len(q['options']) > 3 else '',  # option_d
                        q['correct_option'],  # correct_answer
                        f"Keywords: {', '.join(q.get('keywords', []))}",  # answer_explanation
                        str(course_id),  # course
                        chapter if chapter else '',  # chapter
                        section if section else '',  # section_name
                        "computer science",  # subject
                        q.get('difficulty', 'L1'),  # difficulty_level
                        json.dumps(q.get('keywords', [])),  # tags
                    ))
        print(f"✅ Successfully inserted {len(questions)} questions into local DB.")
    except Exception as e:
        print(f"❌ Error inserting questions: {e}")