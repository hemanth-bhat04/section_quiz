import requests
import json
import re
from collections import Counter

# Setup
url = "http://164.52.212.233:8010/pi-chat-prod"
headers = {"Content-Type": "application/json"}

# Your input text
input_text = """
Welcome to today's session on Pandas, one of the most powerful libraries in Python for data manipulation and analysis.

Pandas introduces two key data structures: the DataFrame and the Series. These make it easy to handle structured data, such as CSV files or SQL tables. 
Now imagine you're working with a huge dataset about customer behavior — instead of manually filtering records (or climbing a volcano 🏔️), you can use simple Pandas methods like `groupby` and `merge` to analyze the data efficiently.

Another important feature is the ability to reshape your data using `pivot_table`, which is extremely helpful in reporting and analytics. Remember, being able to transform your data quickly is like having an astronaut's superpower 🚀 in the world of data science.

Okay, quick recap: DataFrames, Series, groupby, merge, pivot_table — these are your new best friends. Ignore distractions like unicorns 🦄, lemonade stands 🍋, or even pumpkin festivals 🎃 during your analysis!

In the next module, we'll dive deeper into performance optimization and memory management techniques in Pandas.

Thank you, and don’t forget — consistency beats random bananas 🍌 every time!
"""

# Step 1: Basic keyword extraction
# Remove special characters, make lowercase
clean_text = re.sub(r'[^a-zA-Z\s]', '', input_text).lower()
words = clean_text.split()

# Common stopwords to ignore
stopwords = set([
    'the', 'and', 'to', 'of', 'in', 'for', 'a', 'on', 'is', 'with', 'your', 'as', 'be', 'such', 'or', 'you', 'can',
    'being', 'now', 'like', 'these', 'are', 'it', 'every', 'we', 'will', 'during', 'into'
])

# Filter words
filtered_words = [word for word in words if word not in stopwords]

# Count most common words
word_counts = Counter(filtered_words)
top_keywords = [word for word, count in word_counts.most_common(20)]
print("Top Keywords:", top_keywords)

# Step 2: Create prompt
prompt = f'''
Using the following list of keywords, generate 10 multiple-choice questions (MCQs) suitable for degree-level students.

Instructions:
- Each MCQ must have 1 correct answer and 3 plausible distractors.
- Assign a difficulty level to each question: Easy, Medium, or Hard.
- Create two types of questions:
    1. Questions testing **individual topics** — focus on the understanding of a single keyword or concept.
    2. Questions testing **combinations of topics** — where two or more keywords are logically connected; frame integrated questions that test the relationship or combined application.
- After listing all 10 MCQs, **specify for each question** whether it is based on an "Individual topic" or a "Combination of topics," and mention the keywords involved.
- Include a balanced mix of conceptual, application-based, and factual questions.
- Ignore any irrelevant or out-of-context keywords if present.
- Focus only on meaningful keywords that represent important concepts or skills.
- Present all MCQs clearly, with professional wording.

Keywords:
{', '.join(top_keywords)}
'''


# Step 3: Send request
payload = {
    "prompt": prompt
}

response = requests.post(url, headers=headers, json=payload, timeout=500)

# Step 4: Handle response
if response.status_code == 200:
    response_data = json.loads(response.text)
    print(response_data)
else:
    print(f"Error: {response.status_code}")
