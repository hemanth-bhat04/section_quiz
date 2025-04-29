import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def load_questions(file):
    return pd.read_csv(file)


def update_ability_irt(ability, difficulty, is_correct):
    if is_correct:
        ability += 0.5 * (1 - 1 / (1 + np.exp(-(ability - difficulty))))
    else:
        ability -= 0.5 * (1 / (1 + np.exp(-(ability - difficulty))))
    return ability


def update_bkt(p_knows, is_correct, P_T=0.3, P_G=0.2, P_S=0.1):
    if is_correct:
        p_knows = (p_knows * (1 - P_S)) / (p_knows * (1 - P_S) + (1 - p_knows) * P_G)
    else:
        p_knows = (p_knows * P_S) / (p_knows * P_S + (1 - p_knows) * (1 - P_G))
    p_knows = p_knows + (1 - p_knows) * P_T
    return p_knows


def select_next_question(questions, ability, answered_questions):
    available_questions = questions[~questions.index.isin(answered_questions)]
    if len(available_questions) == 0:
        return None
    available_questions['distance'] = abs(available_questions['difficulty'] - ability)
    return available_questions.loc[available_questions['distance'].idxmin()]


def adaptive_quiz(questions):
    st.title("Python Adaptive Quiz 📚")
    st.write("Practice Python concepts with adaptive questions. Track your progress!")

    # Initialize session state
    if 'ability' not in st.session_state:
        st.session_state.ability = 0.0  # Initial ability estimate
    if 'skills' not in st.session_state:
        st.session_state.skills = {skill: 0.2 for skill in questions['skill'].unique()}  # Initial BKT probabilities
    if 'answered_questions' not in st.session_state:
        st.session_state.answered_questions = set()
    if 'score' not in st.session_state:
        st.session_state.score = 0
    if 'question_count' not in st.session_state:
        st.session_state.question_count = 0
    if 'ability_progress' not in st.session_state:
        st.session_state.ability_progress = []  # Stores ability values over time

    
    st.sidebar.header("Quiz Progress")
    st.sidebar.metric("Current Score", f"{st.session_state.score}/{st.session_state.question_count}")

    
    next_question = select_next_question(questions, st.session_state.ability, st.session_state.answered_questions)

    if next_question is not None:
        st.subheader(f"Question {st.session_state.question_count + 1}")
        st.write(next_question['question'])

       
        options = [next_question['option1'], next_question['option2'], next_question['option3'], next_question['option4']]
        user_answer = st.radio("Choose the correct answer:", options)

       
        if st.button("Submit"):
            is_correct = user_answer == next_question['correct_answer']
            if is_correct:
                st.success("Correct! 🎉")
                st.session_state.score += 1
            else:
                st.error("Incorrect! 😢")

            
            st.session_state.ability = update_ability_irt(st.session_state.ability, next_question['difficulty'], is_correct)
            st.session_state.skills[next_question['skill']] = update_bkt(st.session_state.skills[next_question['skill']], is_correct)

           
            st.session_state.ability_progress.append(st.session_state.ability)
            st.session_state.answered_questions.add(next_question.name)
            st.session_state.question_count += 1

            st.rerun()  

    else:
        st.balloons()
        st.subheader("No more questions available! 🎉")
        st.write(f"Your final score is: {st.session_state.score}/{st.session_state.question_count}")

        
        st.write("📊 **Mastery Levels by Skill:**")
        for skill, p_knows in st.session_state.skills.items():
            st.write(f"🔹 {skill}: {p_knows:.2f}")

        
        st.subheader("Score Breakdown 📊")
        st.bar_chart({"Correct": [st.session_state.score], "Incorrect": [st.session_state.question_count - st.session_state.score]})

        
        st.subheader("Progress Over Time 📈")
        if len(st.session_state.ability_progress) > 1:
            ability_df = pd.DataFrame({"Attempt": range(1, len(st.session_state.ability_progress) + 1),
                                       "Ability": st.session_state.ability_progress})
            st.line_chart(ability_df.set_index("Attempt"))

        
        if st.button("Retake Test"):
            st.session_state.answered_questions = set()
            st.session_state.question_count = 0
            st.session_state.score = 0
            st.session_state.ability_progress = []
            st.experimental_rerun()

# Main function
def main():
    st.sidebar.title("Adaptive Quiz Setup")
    uploaded_file = st.sidebar.file_uploader("Upload a CSV file with questions", type=["csv"])

    if uploaded_file is not None:
        questions = load_questions(uploaded_file)
        adaptive_quiz(questions)
    else:
        st.write("📥 Please upload a CSV file to start the quiz.")

if __name__ == "__main__":
    main()
