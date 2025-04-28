import random
from collections import defaultdict
from fetch_videos import get_course_vids_secs
from fetch_keywords import fetch_keywords
from nlp_keywords import cleanPhraseFirst, get_weighted_queries
from v2 import SectionQuizBuilder

class SectionQuizGenerator:
    def __init__(self, solr_url, server_type='dev', video_type=2):
        self.server_type = server_type
        self.video_type = video_type
        self.solr_url = solr_url
        self.quiz_builder = SectionQuizBuilder(solr_url)

    def fetch_section_keywords(self, course_id, section_id=None):
        video_ids, section_ids = get_course_vids_secs(course_id, self.server_type, self.video_type)

        if section_id:
            video_ids = [vid for vid, sec in zip(video_ids, section_ids) if sec == section_id]

        print(f"Video IDs for Section {section_id or course_id}:", video_ids)

        all_keywords = []
        for vid in video_ids:
            keywords = fetch_keywords(vid)
            all_keywords.extend(keywords)

        flat_keywords = []
        for kw in all_keywords:
            if isinstance(kw, list):
                flat_keywords.extend(kw)
            else:
                flat_keywords.append(kw)

        cleaned_keywords = [cleanPhraseFirst(kw) for kw in flat_keywords if isinstance(kw, str)]

        combined_text = ". ".join(cleaned_keywords[:200])  # Limit to top 200 keywords to speed up NLP

        try:
            weighted_query, phrase_score_list, entity_weight, plus_words = get_weighted_queries(combined_text, y=len(combined_text), subject='computer science', level='computer science')
            phrase_score_list = sorted(phrase_score_list, key=lambda x: x[1], reverse=True)
            top_concepts = [phrase for phrase, score in phrase_score_list if len(phrase.split()) > 1][:8]
        except Exception as e:
            print(f"Warning: Failed to fetch from NLP server. Falling back. Error: {e}")
            top_concepts = list(set([kw for kw in cleaned_keywords if len(kw.split()) > 1]))[:8]

        print("Selected conceptual keywords:", top_concepts)

        return top_concepts

    def generate_quiz(self, keywords, total_questions=15):
        if not keywords:
            print("❗ No keywords provided to generate quiz.")
            return []

        strict_query = " OR ".join([f'"{kw}"' for kw in keywords])  # Batch all keywords in one query
        qf = 'chapter_name^5 section_name^5 question^3 explanation'

        print(f"Fetching questions for keywords: {keywords}")
        docs = self.quiz_builder.query_solr(strict_query, qf=qf, rows=total_questions)

        random.shuffle(docs)

        return docs[:total_questions]

if __name__ == "__main__":
    solr_url = 'http://164.52.201.193:8983/solr/rp-quiz'
    course_id = 212
    section_id = None

    generator = SectionQuizGenerator(solr_url)

    keywords = generator.fetch_section_keywords(course_id, section_id)

    if not keywords:
        print("❗ No conceptual keywords found. Cannot generate quiz.")
    else:
        selected_keywords = keywords

        print("\nSelected keywords:", selected_keywords)

        quiz = generator.generate_quiz(selected_keywords, total_questions=15)

        print("\n--- FINAL QUIZ ---")
        for i, q in enumerate(quiz, 1):
            print(f"Q{i}: {q.get('question')}")
            print(f"   A: {q.get('answer')}")
            print(f"   Options: {q.get('option1')}, {q.get('option2')}, {q.get('option3')}, {q.get('option4')}\n")
