import random
from itertools import cycle
from typing import List, Dict

# ------------------------
# Configuration
# ------------------------
SECTION = "Photosynthesis"
TOPICS = [
    "Light-dependent reactions",
    "Calvin cycle",
    "Chloroplast structure",
    "Factors affecting photosynthesis"
]
TOTAL_QUESTIONS = 12
DIFFICULTY_DISTRIBUTION = {
    "easy": 4,
    "medium": 4,
    "hard": 4
}

# ------------------------
# Simulated Database
# ------------------------
MOCK_DATABASE = [
    {"question": "Where do the light-dependent reactions take place?", "options": ["Stroma", "Thylakoid membrane", "Nucleus", "Cytoplasm"], "correct_answer": "Thylakoid membrane", "topic": "Light-dependent reactions", "difficulty": "easy"},
    {"question": "What gas is produced during the light-dependent reactions?", "options": ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"], "correct_answer": "Oxygen", "topic": "Light-dependent reactions", "difficulty": "medium"},
    {"question": "What pigment is crucial for capturing light energy?", "options": ["Carotene", "Xanthophyll", "Chlorophyll", "Melanin"], "correct_answer": "Chlorophyll", "topic": "Chloroplast structure", "difficulty": "easy"},
    {"question": "What is the primary role of the Calvin cycle?", "options": ["To generate ATP", "To fix carbon dioxide into sugars", "To split water", "To produce oxygen"], "correct_answer": "To fix carbon dioxide into sugars", "topic": "Calvin cycle", "difficulty": "medium"},
    {"question": "Which organelle is the site of photosynthesis?", "options": ["Mitochondria", "Chloroplast", "Nucleus", "Vacuole"], "correct_answer": "Chloroplast", "topic": "Chloroplast structure", "difficulty": "easy"},
    {"question": "What environmental factor directly affects the rate of photosynthesis?", "options": ["Wind speed", "Light intensity", "Soil pH", "Gravity"], "correct_answer": "Light intensity", "topic": "Factors affecting photosynthesis", "difficulty": "hard"},
    {"question": "How many turns of the Calvin cycle are required to produce one glucose molecule?", "options": ["2", "4", "6", "3"], "correct_answer": "6", "topic": "Calvin cycle", "difficulty": "hard"},
]

# ------------------------
# Simulated AI Generator
# ------------------------
def generate_ai_question(topic: str, difficulty: str) -> Dict:
    prompts = {
        "easy": f"What is a basic concept from {topic} in photosynthesis?",
        "medium": f"Explain a key process in {topic} during photosynthesis.",
        "hard": f"Analyze a complex effect related to {topic} in photosynthesis."
    }
    options = ["Option A", "Option B", "Option C", "Option D"]
    return {
        "question": prompts[difficulty],
        "options": options,
        "correct_answer": "Option A",
        "topic": topic,
        "difficulty": difficulty,
        "source": "ai"
    }

# ------------------------
# Fetch Questions from DB
# ------------------------
def fetch_questions_from_db(topic: str, difficulty: str, count: int) -> List[Dict]:
    results = [
        {**q, "source": "database"}
        for q in MOCK_DATABASE
        if q["topic"] == topic and q["difficulty"] == difficulty
    ]
    return random.sample(results, min(len(results), count))

# ------------------------
# Quiz Builder
# ------------------------
def build_quiz(section: str, topics: List[str], difficulty_dist: Dict[str, int]) -> List[Dict]:
    quiz_questions = []
    topic_cycle = cycle(topics)

    for difficulty, total_count in difficulty_dist.items():
        db_count = total_count // 2
        ai_count = total_count - db_count

        # Fetch DB questions
        for _ in range(db_count):
            topic = next(topic_cycle)
            db_qs = fetch_questions_from_db(topic, difficulty, 1)
            if db_qs:
                quiz_questions.extend(db_qs)

        # Generate AI questions
        for _ in range(ai_count):
            topic = next(topic_cycle)
            ai_q = generate_ai_question(topic, difficulty)
            quiz_questions.append(ai_q)

    random.shuffle(quiz_questions)
    return quiz_questions

# ------------------------
# Run and Print Quiz
# ------------------------
if __name__ == "__main__":
    quiz = build_quiz(SECTION, TOPICS, DIFFICULTY_DISTRIBUTION)

    for idx, q in enumerate(quiz, 1):
        print(f"\nQuestion {idx} ({q['difficulty'].capitalize()} - {q['topic']}) [{q['source']}]")
        print(q["question"])
        for i, opt in enumerate(q["options"], start=1):
            print(f"  {i}. {opt}")
        print(f"Answer: {q['correct_answer']}")