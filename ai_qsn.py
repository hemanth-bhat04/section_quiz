import requests
import json

url = "http://164.52.212.233:8010/pi-chat-prod"

headers = {
    "Content-Type": "application/json"
}

# Your input text
input_text = """
Top 30 Physical Design Keywords (with frequency):
tool – 17

standard cells – 10

flip-flops – 10

violations – 9

synthesis stage – 9

static timing analysis – 8

netlist – 8

routing – 8

placement – 8

physical design – 7

automatic place – 7

constraints – 7

core area – 7

design rule check – 7

clock tree synthesis – 6

gate-level netlist – 6

interconnections – 6

power planning – 6

floor planning – 4

power grid – 4

clock nets – 4

clock skew – 4

power – 4

capacitance – 4

timing – 3

parasitic extraction – 3

optical proximity correction – 3

place-and-route – 5

layout – 5

macro cells – 5
"""

# Create the prompt asking the model to generate MCQs
prompt = f'''Given the following list of keywords related to a physical design video of electronics, create 20 multiple-choice questions (MCQs).
Focus only on important keywords and concepts from the text.
Each MCQ should have 1 correct answer and 3 plausible incorrect options (distractors).
Ignore unrelated or random words.
Present the MCQs in a clear and concise format.
The questions should be relevant to the topic of physical design in electronics.
Give questions that are complex, application-based, and require reasoning.
Make sure to include code snippets or code-based reasoning, and computation based in at least 70% of the questions.


Keywords:
{input_text}'''

payload = {
    "prompt": prompt
}

response = requests.post(url, headers=headers, json=payload, timeout=500)

if response.status_code == 200:
    response_data = json.loads(response.text)
    # Print the raw response for debugging
    print("Raw AI Response:", response_data)

    # Try to print questions in a neat format if possible
    if isinstance(response_data, list):
        for idx, q in enumerate(response_data, 1):
            print(f"\nQ{idx}: {q.get('question', 'No question found')}")
            options = q.get('options', [])
            for opt_idx, opt in enumerate(options, ord('A')):
                print(f"   {chr(opt_idx)}. {opt}")
            answer = q.get('answer')
            if answer:
                print(f"   Answer: {answer}")
    else:
        # If not structured, just print the text
        print("\nAI Output:\n", response_data)
else:
    print(f"Error: {response.status_code}")
