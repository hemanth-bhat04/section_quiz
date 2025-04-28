import requests
from nlp_keywords import get_weighted_queries

def query_solr(solr_url, query, qf,fq):
    try:
        params = {
            'q': query,
            'qf': qf,
            'fq': fq,
            # 'bq': bq,
            'defType': 'edismax',
            'indent': 'on',
            'fl': 'id,score,question,option1,option2,option3,option4,answer,explanation,question_html,explanation_html',
            'wt': 'json',
            'rows': 1,
        }
        response = requests.get(f'{solr_url}/select', params=params, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json().get('response', {}).get('docs', [])
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error querying Solr: {e}")

# Example usage
solr_url = 'http://164.52.201.193:8983/solr/rp-quiz'
#query = 'tuples AND python AND list'
query = 'tuples AND python'
qf = 'question^5 chapter_name section_name^2 explanation'
fq = 'level:degree'
# bq = ''
docs = query_solr(solr_url, query, qf,fq)
print(docs)