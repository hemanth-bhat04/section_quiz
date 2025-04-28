import requests
import json

url = "http://164.52.212.233:8010/pi-chat-prod"

headers = {
    "Content-Type": "application/json"
}

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

# Create the prompt asking the model to generate MCQs
prompt = f'''Given the following text, create 5 multiple-choice questions (MCQs).
Focus only on important keywords and concepts from the text.
Each MCQ should have 1 correct answer and 3 plausible incorrect options (distractors).
Ignore unrelated or random words.
Present the MCQs in a clear and concise format.

Text:
{input_text}'''

payload = {
    "prompt": prompt
}

response = requests.post(url, headers=headers, json=payload, timeout=500)

if response.status_code == 200:
    response_data = json.loads(response.text)
    print(response_data)
else:
    print(f"Error: {response.status_code}")
