import requests
from collections import defaultdict
import random

class SectionQuizBuilder:
    def __init__(self, solr_url, timeout=10):
        self.solr_url = solr_url
        self.timeout = timeout

    def query_solr(self, query, qf, fq=None, rows=10):
        try:
            params = {
                'q': query,
                'qf': qf,
                'defType': 'edismax',
                'indent': 'on',
                'fl': 'id,score,question,option1,option2,option3,option4,answer,explanation,chapter_name,section_name',
                'wt': 'json',
                'rows': rows,
            }
            if fq:
                params['fq'] = fq

            response = requests.get(f'{self.solr_url}/select', params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get('response', {}).get('docs', [])
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error querying Solr: {e}")

    def build_quiz_by_concept(self, concept, level="degree", rows=10, shuffle=True):
        """
        Build a quiz grouped by sections based on a concept.

        Args:
            concept (str): Concept or keyword to search
            level (str, optional): Level filter, default 'degree'
            rows (int, optional): Number of questions to fetch
            shuffle (bool, optional): Shuffle questions inside each section

        Returns:
            dict: {section_name: [questions]}
        """
        quizzes = defaultdict(list)
        qf = 'question chapter_name^2 section_name^5 explanation'
        fq = f"level:{level}" if level else None

        docs = self.query_solr(concept, qf, fq, rows)

        for doc in docs:
            section = doc.get('section_name', 'General')
            quizzes[section].append(doc)

        if shuffle:
            for section_docs in quizzes.values():
                random.shuffle(section_docs)

        return quizzes

if __name__ == "__main__":
    solr_url = 'http://164.52.201.193:8983/solr/rp-quiz'
    quiz_builder = SectionQuizBuilder(solr_url)

    concept = "tuples"  # The concept/topic you want to build quiz on
    section_quizzes = quiz_builder.build_quiz_by_concept(concept, rows=10)

    for section, questions in section_quizzes.items():
        print(f"\n--- Section: {section} ---")
        for i, q in enumerate(questions, 1):
            print(f"Q{i}: {q['question']}")
            print(f"   A: {q['answer']}")
            print(f"   Options:")
            print(f"     1. {q.get('option1', '')}")
            print(f"     2. {q.get('option2', '')}")
            print(f"     3. {q.get('option3', '')}")
            print(f"     4. {q.get('option4', '')}")
