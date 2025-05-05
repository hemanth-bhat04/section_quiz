import requests
import re
import html  # For decoding HTML entities

def query_solr_with_highlighting(solr_url, query, qf, fq, hl_fl):
    try:
        params = {
            'q': query,
            'qf': qf,
            'fq': fq,
            'defType': 'edismax',
            'indent': 'on',
            'fl': 'id,score,question,option1,option2,option3,option4,answer,explanation',
            'wt': 'json',
            'rows': 10,
            'hl': 'true',
            'hl.q': query,
            'hl.fl': hl_fl,  # use variable passed in
            'hl.usePhraseHighlighter': 'true',
            'hl.method': 'unified',
            'hl.snippets': '1000',
        }

        response = requests.get(f'{solr_url}/select', params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        print("=== DEBUG: Highlighting block ===")
        print(data.get('highlighting', {}))

        return data.get('response', {}).get('docs', []), data.get('highlighting', {})
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error querying Solr with highlighting: {e}")

def generate_quiz_from_solr_highlighting(solr_url, query, qf, fq, hl_fl='question'):
    docs, highlights = query_solr_with_highlighting(solr_url, query, qf, fq, hl_fl)

    quiz_questions = []
    for doc in docs:
        doc_id = str(doc.get('id'))  # 🔧 Convert to string to match highlighting keys
        highlight = highlights.get(doc_id, {})

        print(f"--- DEBUG: Highlights for ID {doc_id} ---")
        print(highlight)

        matched_fragments = []

        # Extract highlighted terms from specified field(s)
        for field, snippets in highlight.items():
            for snippet in snippets:
                snippet = html.unescape(snippet)  # Decode HTML entities
                matches = re.findall(r'<em>(.*?)</em>', snippet)
                matched_fragments.extend(matches)

        matched_keywords = ', '.join(sorted(set(matched_fragments))) if matched_fragments else "None"

        question = doc.get('question', 'No question available')
        options = [doc.get(f'option{i}', '') for i in range(1, 5)]
        answer = doc.get('answer', '')
        explanation = doc.get('explanation', '')

        quiz_question = {
            'question': question,
            'options': options,
            'answer': answer,
            'explanation': explanation,
            'matched_keywords': matched_keywords
        }
        quiz_questions.append(quiz_question)

    return quiz_questions

# === Example usage ===

solr_url = 'http://164.52.201.193:8983/solr/rp-quiz'
query = 'tuples AND python'
qf = 'question^5 chapter_name^2 explanation'
fq = 'level:degree'
hl_fl = 'fieldspellcheck_en'  # ✅ Make sure this is the field you want highlighted

quiz = generate_quiz_from_solr_highlighting(solr_url, query, qf, fq, hl_fl)

# Print quiz output
for q in quiz:
    print(f"Q: {q['question']}")
    print("Options:", q['options'])
    print("Answer:", q['answer'])
    print("Explanation:", q['explanation'])
    print("Matched Keywords:", q['matched_keywords'])
    print("-" * 40)
