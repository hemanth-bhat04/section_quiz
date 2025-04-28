import requests
from collections import defaultdict

def query_solr(solr_url, query, qf, fq, rows=5):
    try:
        params = {
            'q': query,
            'qf': qf,
            'fq': fq,
            'defType': 'edismax',
            'indent': 'on',
            'fl': 'id,score,question,option1,option2,option3,option4,answer,explanation,chapter_name,section_name',
            'wt': 'json',
            'rows': rows,
        }
        response = requests.get(f'{solr_url}/select', params=params, timeout=10)
        response.raise_for_status()
        return response.json().get('response', {}).get('docs', [])
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error querying Solr: {e}")

def simple_quiz_query(concept, solr_url, fq="level:degree"):
    quizzes = defaultdict(list)
    qf = 'question chapter_name^5 section_name^2'
    query = concept  # simpler unboosted query

    docs = query_solr(solr_url, query, qf, fq, rows=10)
    for doc in docs:
        section = doc.get('section_name', 'General')
        quizzes[section].append(doc)

    return quizzes

# === Example usage ===
if __name__ == "__main__":
    solr_url = 'http://164.52.201.193:8983/solr/rp-quiz'
    concept = "Recursion"  # Example concept to search for

    section_quizzes = simple_quiz_query(concept, solr_url)

    for section, questions in section_quizzes.items():
        print(f"\n--- Section: {section} ---")
        for i, q in enumerate(questions, 1):
            print(f"Q{i}: {q['question']}")
            print(f"   A: {q['answer']}")
            print("   Options:")
            print(f"     1. {q.get('option1', '')}")
            print(f"     2. {q.get('option2', '')}")
            print(f"     3. {q.get('option3', '')}")
            print(f"     4. {q.get('option4', '')}")