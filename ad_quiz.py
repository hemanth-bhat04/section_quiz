import streamlit as st
import pandas as pd

# Load questions from a CSV file
def load_questions(file):
    questions = pd.read_csv(file)
    return questions

# Adaptive quiz logic
def adaptive_quiz(questions):
    st.title("Adaptive Quiz")
    st.write("Answer the following questions. The quiz will adapt based on your performance.")

    if 'score' not in st.session_state:
        st.session_state.score = 0
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    if 'difficulty_level' not in st.session_state:
        st.session_state.difficulty_level = "medium"  # Start with medium difficulty

    # Filter questions based on difficulty level
    filtered_questions = questions[questions['difficulty'] == st.session_state.difficulty_level]

    if st.session_state.current_question < len(filtered_questions):
        question = filtered_questions.iloc[st.session_state.current_question]
        st.subheader(f"Question {st.session_state.current_question + 1}")
        st.write(question['question'])

        # Display options
        options = [question['option1'], question['option2'], question['option3'], question['option4']]
        user_answer = st.radio("Choose the correct answer:", options)

        # Check answer
        if st.button("Submit"):
            if user_answer == question['correct_answer']:
                st.success("Correct! 🎉")
                st.session_state.score += 1
                # Increase difficulty if the answer is correct
                if st.session_state.difficulty_level == "easy":
                    st.session_state.difficulty_level = "medium"
                elif st.session_state.difficulty_level == "medium":
                    st.session_state.difficulty_level = "hard"
            else:
                st.error("Incorrect! 😢")
                # Decrease difficulty if the answer is incorrect
                if st.session_state.difficulty_level == "hard":
                    st.session_state.difficulty_level = "medium"
                elif st.session_state.difficulty_level == "medium":
                    st.session_state.difficulty_level = "easy"

            st.session_state.current_question += 1

    else:
        st.balloons()
        st.subheader("Quiz Completed! 🎉")
        st.write(f"Your final score is: {st.session_state.score}/{len(filtered_questions)}")

# Main function
def main():
    st.sidebar.title("Adaptive Quiz Setup")
    uploaded_file = st.sidebar.file_uploader("Upload a CSV file with questions", type=["csv"])

    if uploaded_file is not None:
        questions = load_questions(uploaded_file)
        adaptive_quiz(questions)
    else:
        st.write("Please upload a CSV file to start the quiz.")

if __name__ == "__main__":
    main()