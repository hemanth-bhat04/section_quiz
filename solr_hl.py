import requests
import re
import math
import numpy as np
from difflib import get_close_matches
from collections import OrderedDict

def solr_direct_video_search(keywords: list, solr_core: str, subject: str, fq_lang_list: list) -> list:
    """
    Function to query solr for direct keywords based search for videos.
    """

    solr_url = 'http://164.52.201.193:8983/solr/' + solr_core

    query = '"' + '" "'.join(keywords) + '"'

    '''fqval = '-accent:(oriental international) AND text:[* TO *]  AND ' \
            '-channel_id:(UCX440GeRutiFNrkjuQAyw_A UCkDw-LPU1Nnd2WRsfnDbUcA UCcErZD9wUPQONYaoRXWX-hw ' \
            'UCFSgCD7s77pJVfXU_TJiRXg UCsvqVGtbbyHaMoevxPAq9Fg UCkw4JCwteGrDHIsyIIKo4tQ UCCktnahuRFYIBtNnKT5IYyg ' \
            'UCQVdp4WkoUXiYn1jEFejePA UCnTeXg4Pck9JGhZvCmEQAiQ)' '''
    fqval = 'question:[* TO *]'


    if fq_lang_list:
        #fqval += ' AND -title:("' + '" "'.join(fq_lang_list) + '")'
        fqval += ' AND -subject:("' + '" "'.join(fq_lang_list) + '")'

    query_params = {
        'q': query,
        'qf': 'title^1.5 critical_all_keywords^1.25 yt_tags',
        'fq': fqval,
        'fl': 'contentId,score,title',
        'defType': 'edismax',
        'indent': 'on',
        'hl': 'true',
        'hl.fl': 'fieldspellcheck_en',
        'hl.q': query,
        'hl.usePhraseHighlighter': 'true',
        'hl.method': 'unified',
        'hl.snippets': '1000',
        'wt': 'json',
        'rows': 30
    }

    try:

        r = requests.get('%s/select' % solr_url, params=query_params, timeout=10)

    except requests.exceptions.HTTPError:
        raise Exception("Http Error")
    except requests.exceptions.ConnectionError:
        raise Exception("Error Connecting")
    except requests.exceptions.Timeout:
        raise Exception("Timeout Error")

    r_docs = eval(r.text).get('response', {}).get('docs', {})
    r_docs = sorted(r_docs, key=lambda i: i['score'], reverse=True)
    ordered_video_list = [each_record['contentId'] for each_record in r_docs]
    hl_words = eval(r.text).get('highlighting', {})

    video_highlighted_words = get_highlighted_words(hl_words, ordered_video_list)
    filtered_videos = filter_videos(r_docs, video_highlighted_words, keywords)

    return filtered_videos


def filter_videos(solr_docs: list, video_highlights: OrderedDict, query_words: list) -> list:
    """
    Function to filter videos based on a match threshold.
    """

    keyword_count = len(query_words)

    if keyword_count == 1:
        cutoff = 1
    elif keyword_count <= 3:
        cutoff = keyword_count - 1
    else:
        cutoff = math.floor(0.5 * keyword_count)

    result = []
    temp = []
    for each_doc in solr_docs:
        if each_doc['contentId'] in video_highlights.keys() and each_doc['contentId'] not in temp:
            compare_temp = []
            for word in query_words:
                matched_keywords = video_highlights[each_doc['contentId']]
                best_match = get_close_matches(word, matched_keywords, 1, cutoff=0.8)
                if best_match:
                    compare_temp += best_match

            if len(compare_temp) >= cutoff:
                each_doc['critical_keywords'] = compare_temp
                temp.append(each_doc['contentId'])
                result.append(each_doc)

    return result


def get_highlighted_words(highlights: dict, ord_vid_list: list, multi_valued_hl_fl: bool = True,
                          is_slideshow: bool = False) -> OrderedDict:
    """
    Function to get an ordered dictionary of videos and their matched keywords
    using the highlighting returned by Solr.
    Also can be used in extracting matches from other Solr Queries.
    """

    video_highlights = {}
    ordered_highlights = OrderedDict()

    if not highlights:
        return ordered_highlights

    for content_id, highlighted in highlights.items():

        highlights_string = ''
        if highlighted.items():
            if not multi_valued_hl_fl:
                highlights_string = str(list(highlighted.items())[0][1]).lower()
            else:
                highlights_string = str(' '.join(list(highlighted.items())[0][1])).lower()
            highlights_string = highlights_string.replace('"', '')

        # Highlights of matched Keywords from Solr needs this Regex as it has a particular style of highlighting.
        highlighted_lines = re.findall(r'<em>(\w+)</em> *<em>(\w+)</em> *<em>(\w+)</em> *<em>(\w+)</em> *<em>(\w+)'
                                       r'</em>|<em>(\w+)</em> *<em>(\w+)</em> *<em>(\w+)</em> *<em>(\w+)</em>|<em>'
                                       r'(\w+)</em> *<em>(\w+)</em> *<em>(\w+)</em>|<em>(\w+)</em> *<em>(\w+)'
                                       r'</em>|<em>(\w+)</em>', highlights_string)

        # We have stored video id as a combination of video_id and primary_id in Solr, needs splitting.
        if is_slideshow:
            unique_id = content_id
        else:
            unique_id = re.sub(r'__.*', '', content_id)

        video_keywords = []
        for line_keywords in highlighted_lines:
            keywords = [keyword for keyword in line_keywords if keyword and keyword.strip()]
            video_keywords.append(" ".join(keywords))

        if unique_id in video_highlights.keys():
            temp_keywords = video_highlights[unique_id]
            video_highlights[unique_id] = list(set(temp_keywords + video_keywords))
        else:
            video_highlights[unique_id] = list(set(video_keywords))

    for video in ord_vid_list:
        if video in video_highlights.keys():
            ordered_highlights[video] = video_highlights[video]

    return ordered_highlights

result = solr_direct_video_search(['tuples','sets','lists', 'dictionaries', 'arrays', 'stacks', 'queues', 'hashmaps', 'linked lists', 'trees', 'graphs', 'heaps', 'recursion', 'iteration', 'functions', 'methods', 'classes', 'objects', 'inheritance', 'encapsulation', 'polymorphism', 'abstraction', 'loops', 'for loop', 'while loop', 'conditionals', 'if else', 'exceptions', 'try except', 'file handling', 'generators', 'comprehensions', 'lambda functions'], 'rp-quiz', 'computer science', [''])
print(result)