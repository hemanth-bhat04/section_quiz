from concurrent.futures import ThreadPoolExecutor

from scripts.predefined_junk import *
from pisearch_v2 import pisearch

from .utils import *

high_school_list = ['class 8-10', 'class 8', 'class 9', 'class 10', 'class 08', 'class 09', 'class-8', 'class-9',
                    'class-08', 'class-09', 'class-10', 'class8', 'class9', 'class08', 'class09', 'class10', 'grade-8',
                    'grade-9', 'grade-08', 'grade-09', 'grade-10', 'grade 8', 'grade 08', 'grade 9', 'grade 08',
                    'grade 10', 'std 8', 'std 9', 'std 08', 'std 09', 'std 10', '8th standard', '9th standard',
                    '10th standard', '8th std', '9th std', '10th std', 'class VIII', 'class IX', 'class X', '8th class',
                    '9th class', '10th class']

middle_school_list = ['class 5-7', 'class 5', 'class 6', 'class 7', 'class 05', 'class 06', 'class 07', 'class-5',
                      'class-6', 'class-7', 'class-05', 'class-06', 'class-07', 'class5', 'class6', 'class7',
                      'class05', 'class06', 'class07', 'grade-5', 'grade-6', 'grade-7', 'grade-05',
                      'grade-06', 'grade-07', 'grade 5', 'grade 6', 'grade 7', 'grade 05', 'grade 06', 'grade 07',
                      'std 5', 'std 6', 'std 7', 'std 05', 'std 06', 'std 07', '5th standard', '6th standard',
                      '7th standard', '5th std', '6th std', '7th std', 'class V', 'class VI', 'class VII', '5th class',
                      '6th class', '7th class']

cs_sub_list = ['computer science', 'electronics']

deg_sub_list = ['business', 'accountancy', 'marketing']

deg_cs_list = ["usld", "engineering - information science (be | btech)", "computer science",
               "computer application (bca)", "information science", "engineering - computer science (be | btech)",
               "computer application", "computer application(pg)", "computer application (mca)",
               "computer science (bsc)", "electronics and communication",
               "engineering - electronics and communication (be | btech)"]

deg_com_list = ["commerce", "commerce (bcom | bba)", "management (mba)"]


def get_query_from_pisearch(para_dict):

    url_or_text = ''
    pdftext = para_dict['pdftext']
    level = para_dict['level']
    subject = para_dict['subject']

    result = json.loads(pisearch(url_or_text, level=level, pdftext=pdftext, pastsubject=subject,
                                 is_new=True, extract_query=True))

    try:
        return result['rescaled_query']
    except KeyError:
        return ''


def PiQuizAuthor(pdftext, course_name='', topic='', sub_topic='', level='computer science', subject='computer science'):

    pdftext = '.\n'.join([x.strip('.') for x in pdftext.split('\n')])
    cleaned_course_name = cleanPhraseSecond(cleanPhraseFirst(course_name))
    cleaned_topic = cleanPhraseSecond(cleanPhraseFirst(topic))
    cleaned_sub_topic = cleanPhraseSecond(cleanPhraseFirst(sub_topic))

    text_paras = []
    line_len = len(pdftext.split('.'))
    para_nos = line_len//5

    for i in range(para_nos):
        pisearch_dict = {}
        if i == para_nos - 1:
            pisearch_text = '.'.join(pdftext.split('.')[5*i:])
        else:
            pisearch_text = '.'.join(pdftext.split('.')[5*i:5*(i+1)])

        final_pisearch_text = '%%@#%@#%%' + \
                              '\n' + course_name + \
                              '\n' + topic + \
                              '\n' + sub_topic + \
                              '\n' + '%%@#%@#%%' + \
                              '\n' + '@@#%@#%@@' + '\n'

        if level.strip().lower() in deg_cs_list + deg_com_list:

            final_pisearch_text += topic.upper() + '\n' + \
                                   sub_topic.upper() + '\n' + \
                                   pisearch_text + '\n' + \
                                   '@@#%@#%@@'
        else:
            final_pisearch_text += sub_topic.upper() + '\n' + \
                                   pisearch_text + '\n' + \
                                   '@@#%@#%@@'

        pisearch_dict['pdftext'] = final_pisearch_text
        pisearch_dict['level'] = level
        pisearch_dict['subject'] = subject
        text_paras.append(pisearch_dict)

    chapter_check = check_chapter(cleaned_sub_topic, cleaned_topic, level)

    with ThreadPoolExecutor() as executor:
        queries = executor.map(get_query_from_pisearch, text_paras)

    result = {}
    solr_call_resp = []

    for query in queries:
        if not query.strip():
            continue
        r_docs = solr_quiz_call(query, cleaned_course_name, cleaned_sub_topic, level, chapter_check)
        solr_call_resp.append(r_docs)

    new_r_docs = []

    for doc in solr_call_resp:
        new_r_docs += doc[:3]
    for doc in solr_call_resp:
        new_r_docs += doc[3:6]
    for doc in solr_call_resp:
        new_r_docs += doc[6:]

    questions_list = []
    completed_questions = []
    new_temp = {}

    for doc in new_r_docs:
        if len(questions_list) == 10:
            break
        if doc['id'] in completed_questions:
            continue

        temp = {}

        try:
            temp['ID'] = doc['id']
            completed_questions.append(doc['id'])
        except KeyError:
            continue

        try:
            new_temp['Question'] = doc['question']
        except KeyError:
            continue

        try:
            temp['Answer'] = doc['answer']
        except KeyError:
            continue

        try:
            temp['question_html'] = doc['question_html']
        except KeyError:
            continue

        try:
            temp['Option1'] = doc['option1']
        except KeyError:
            temp['Option1'] = ''

        try:
            temp['Option2'] = doc['option2']
        except KeyError:
            temp['Option2'] = ''

        try:
            temp['Option3'] = doc['option3']
        except KeyError:
            temp['Option3'] = ''

        try:
            temp['Option4'] = doc['option4']
        except KeyError:
            temp['Option4'] = ''

        # try:
        #     temp['Explanation'] = doc['explanation']
        # except KeyError:
        #     temp['Explanation'] = 'None.'

        try:
            temp['explanation_html'] = doc['explanation_html']
            if temp['explanation_html'] == ">":
                temp['explanation_html'] = '<div> None. </div>'
        except KeyError:
            temp['explanation_html'] = '<div> None. </div>'

        questions_list.append(temp)

    result['QuestionList'] = questions_list

    return json.dumps(result, indent=4)


if __name__ == "__main__":

    example_pdf_text = """
    A decorator takes in a function, adds some functionality and returns it. In this tutorial,
    you will learn how you can create a decorator and why you should use it. Python has an interesting feature called 
    decorators to add functionality to an existing code.This is also called metaprogramming because a part of the
    program tries to modify another part of the program at compile time. Functions and methods are called callable as
    they can be called. In fact, any object which implements the special __call__() method is termed callable.
    So, in the most basic sense, a decorator is a callable that returns a callable. Basically, a decorator takes in a
    function, adds some functionality and returns it. Multiple decorators can be chained in Python.
    This is to say, a function can be decorated multiple times with different (or same) decorators. We simply place
    the decorators above the desired function.
    """
    example_course = 'Python Programming'
    example_topic = 'Classes,Files and Exceptions'
    example_sub_topic = 'Decorators'
    example_level = 'computer science'
    example_subject = 'computer science'

    print(PiQuizAuthor(example_pdf_text, example_course, example_topic,
                       example_sub_topic, example_level, example_subject))
