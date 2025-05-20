import streamlit as st
import psycopg2
import random

# === DB CONFIG ===
DB_CONFIG = {
    "dbname": "quiz_chaptermaster",
    "user": "postgres",
    "password": "Hemanth",
    "host": "localhost",
    "port": "5432"
}

# === Batch Scheme ===
BATCH_SCHEME = {
    1: {'L1': 3, 'L2': 1, 'L3': 1},
    2: {'L1': 2, 'L2': 2, 'L3': 1},
    3: {'L1': 1, 'L2': 3, 'L3': 1},
    4: {'L1': 1, 'L2': 2, 'L3': 2},
    5: {'L1': 0, 'L2': 2, 'L3': 3},
}

# === DB Functions ===

def fetch_available_chapter():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT chapter FROM (
                    SELECT DISTINCT chapter
                    FROM "BaseModel_quizchaptermaster"
                ) AS sub
                ORDER BY RANDOM()
                LIMIT 1
            ''')
            return cur.fetchone()

def fetch_questions_by_level(chapter, level, limit):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id, question_text, option_a, option_b, option_c, option_d, correct_answer,
                       correct_answer_text, answer_explanation
                FROM "BaseModel_quizchaptermaster"
                WHERE chapter = %s AND difficulty_level = %s
                ORDER BY RANDOM()
                LIMIT %s
            ''', (chapter, level, limit))
            return cur.fetchall()

def build_batch(chapter, batch_number):
    for current in range(batch_number, 6):  # Try upward batches only from current to 5
        levels_needed = BATCH_SCHEME.get(current, {})
        batch = []
        all_available = True
        for level, count in levels_needed.items():
            questions = fetch_questions_by_level(chapter, level, count)
            if not questions or len(questions) < count:
                all_available = False
                break
            batch.extend(questions)
        if all_available:
            random.shuffle(batch)
            return batch, current
    return [], None

def get_next_batch_number(current_batch, score):
    if score >= 4:
        return min(current_batch + 1, 5)
    elif score <= 2:
        return max(current_batch - 1, 1)
    return current_batch

# === Streamlit UI ===
st.set_page_config(page_title="Adaptive Practice Quiz", layout="wide")
st.title("🎯 Adaptive Practice Quiz")

if 'quiz_started' not in st.session_state:
    st.session_state.quiz_started = False

if not st.session_state.quiz_started:
    st.markdown("""
        Welcome to the **Adaptive Practice Quiz**!

        🧠 You'll be guided through a series of questions that adjust in difficulty based on your performance.

        Click the button below when you're ready to begin.
    """)
    if st.button("Start Quiz"):
        st.session_state.quiz_started = True
        st.session_state.batch_number = 1
        st.session_state.score = 0
        st.session_state.progress = []
        st.session_state.answers_submitted = False
        st.session_state.responses = {}
        st.session_state.current_question_idx = 0
        st.rerun()
else:
    chapter_data = fetch_available_chapter()

    if not chapter_data:
        st.error("⚠️ No chapter data available in the database.")
        st.session_state.quiz_started = False
        st.stop()
    else:
        chapter = chapter_data[0]
        st.markdown(f"**📘 Chapter:** {chapter}**")

        if 'questions' not in st.session_state or not st.session_state.questions:
            questions, actual_batch = build_batch(chapter, st.session_state.batch_number)
            if not questions:
                st.error("🚫 No questions available for the selected or higher batches.")
                st.session_state.quiz_started = False
                st.stop()
            else:
                st.session_state.questions = questions
                st.session_state.batch_number = actual_batch  # Update to the actual batch used
                st.session_state.current_question_idx = 0

        questions = st.session_state.questions
        idx = st.session_state.current_question_idx
        q = questions[idx]

        st.markdown(f"### Q{idx + 1}: {q[1]}")
        options = {"A": q[2], "B": q[3], "C": q[4], "D": q[5]}

        selected_option = st.radio(
            "Choose your answer:",
            list(options.keys()),
            index=None,
            key=f"q{q[0]}_b{st.session_state.batch_number}",
            format_func=lambda k: f"{k}. {options[k]}"
        )

        if selected_option:
            st.session_state.responses[q[0]] = selected_option
            if st.button("Next"):
                if idx + 1 < len(questions):
                    st.session_state.current_question_idx += 1
                    st.rerun()
                else:
                    st.session_state.answers_submitted = True
                    st.rerun()

        if st.session_state.answers_submitted:
            score = 0
            for i, q in enumerate(st.session_state.questions):
                selected = st.session_state.responses.get(q[0])
                if not selected:
                    st.warning(f"You did not answer Question {i+1}")
                    continue
                if selected == q[6]:
                    st.success(f"Q{i+1}: ✅ Correct! {q[7]}")
                    score += 1
                else:
                    st.error(f"Q{i+1}: ❌ Incorrect. Correct answer is {q[6]}: {q[7]}")
                st.info(f"📝 Explanation: {q[8]}")
                st.markdown("---")

            st.session_state.score = score
            st.session_state.progress.append((st.session_state.batch_number, score))
            st.success(f"🎓 You scored {score} out of {len(st.session_state.questions)}")

            next_batch = get_next_batch_number(st.session_state.batch_number, score)
            if next_batch > 5:
                st.balloons()
                st.success("🎉 You've completed all batches!")
                st.write("📊 Your batch-wise scores:")
                for b, s in st.session_state.progress:
                    st.write(f"Batch {b}: {s}/5")
                st.session_state.quiz_started = False
                st.stop()
            else:
                if st.button("Continue to Next Quiz"):
                    st.session_state.answers_submitted = False
                    questions, actual_batch = build_batch(chapter, next_batch)
                    if not questions:
                        st.error(f"🚫 No questions available for Batch {next_batch} or higher.")
                        st.session_state.quiz_started = False
                        st.stop()
                    else:
                        st.session_state.questions = questions
                        st.session_state.batch_number = actual_batch
                        st.session_state.responses = {}
                        st.session_state.current_question_idx = 0
                        st.rerun()
