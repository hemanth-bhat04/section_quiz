import requests
import json

url = "http://164.52.212.233:8010/pi-chat-prod"

headers = {
    "Content-Type": "application/json"
}

# Your input text
input_text = """
floor plan
standard cells
routing
netlist
design rule check
layout
technology file
synthesis
timing requirements
constraints
placement
power network
design flow
timing model
parasitic extraction models
capacitance
resistance
layout static timing analysis
design violation
physical verification decks
hierarchical implementation flow
macro
flip-flops
hard macros
memories
gate level
minimum width
spacing
core ring
via
"""

# Create the prompt asking the model to generate MCQs
prompt = f'''Given the following list of keywords related to advanced physical design video of electronics, create 20 multiple-choice questions (MCQs).
Each MCQ should have 1 correct answer and 3 plausible incorrect options (distractors).
Present the MCQs in a clear and concise format.
The questions should be relevant to the topic of advanced physical design in electronics.
Give questions that are complex, application-based, and require reasoning.
Make sure to include code snippets or code-based reasoning, and computation based in at least 60% of the questions.


Keywords:
{input_text}'''

payload = {
    "prompt": prompt
}

response = requests.post(url, headers=headers, json=payload, timeout=500)

if response.status_code == 200:
    response_data = json.loads(response.text)
    print("Raw AI Response:", response_data)

    # Try to parse and print questions in a neat, structured format
    def print_structured_mcqs(mcqs):
        for idx, q in enumerate(mcqs, 1):
            # Try common field names
            question = q.get('question') or q.get('question_text') or q.get('Q') or "No question found"
            print(f"\nQ{idx}: {question}")
            # Try options as list or as separate fields
            options = q.get('options')
            if not options:
                options = [q.get(f'option_{c}') or q.get(f'option{c}') or q.get(f'option_{chr(65+i).lower()}') or q.get(f'option{chr(65+i).lower()}') or q.get(f'option{chr(65+i)}') for i, c in enumerate(['a', 'b', 'c', 'd'])]
                options = [opt for opt in options if opt]
            for opt_idx, opt in enumerate(options, ord('A')):
                print(f"   {chr(opt_idx)}. {opt}")
            answer = q.get('answer') or q.get('correct_answer') or q.get('correct_option')
            if answer:
                print(f"   Answer: {answer}")
            explanation = q.get('answer_explanation') or q.get('explanation')
            if explanation:
                print(f"   Explanation: {explanation}")

    if isinstance(response_data, list):
        print_structured_mcqs(response_data)
    elif isinstance(response_data, dict) and 'questions' in response_data:
        print_structured_mcqs(response_data['questions'])
    else:
        # Try to extract JSON list from a string blob
        import re
        match = re.search(r'\[\s*{.*}\s*\]', str(response_data), re.DOTALL)
        if match:
            try:
                mcqs = json.loads(match.group(0))
                print_structured_mcqs(mcqs)
            except Exception:
                print("\nAI Output (unstructured):\n", response_data)
        else:
            print("\nAI Output (unstructured):\n", response_data)
else:
    print(f"Error: {response.status_code}")
