from django.conf import settings

import osometweet

from bloc.generator import gen_bloc_for_users
from bloc.generator import add_bloc_sequences
from bloc.util import get_default_symbols
from bloc.util import get_bloc_params
from bloc.subcommands import run_subcommands
from argparse import Namespace

from . import bloc_extension
from . import symbols

from .file_handling import *

TOP_WORD_LIMIT = 100

def verify_user_exists(user_list):
    oauth2 = osometweet.OAuth2(bearer_token=settings.BEARER_TOKEN, manage_rate_limits=False)
    ot = osometweet.OsomeTweet(oauth2)

    # Returns dict list with 'id' 'name' and 'username' fields
    user_data = ot.user_lookup_usernames(user_list)

    if (user_data.get('errors')):
        error_details = {
            'errors': []
        }
        for error in user_data['errors']:
            error_details['errors'].append({
                'account_username': error['value'],
                'error_title': error['title'],
                # Remove the brackets from the account error detail around the username
                'error_detail': error['detail'].replace("[", "").replace("]", "")
            })
        return len(error_details['errors']), error_details
    elif user_data.get('title') == 'Client Forbidden':
        error_details = {
            'errors': [{
                'error_title': user_data['title'],
                'error_detail': 'Unable to access the Twitter API due to recent changes by Twitter that are hostile towards developers.'
            }]
        }
        return 1, error_details

    return 0, user_data['data']


def analyze_tweet_file(files = None):
    if(files):
        tweets = []
        for file in files:
            file_contents = getDictArrayFromFile(file)
            tweets.extend(file_contents)

        # Sort Tweets by user
        users = {}
        for tweet in tweets:
            user_id = tweet['user']['id']
            if user_id in users.keys():
                users[user_id]['tweets'].append(tweet)
            else:
                users[user_id] = {
                    'id': user_id,
                    'username': tweet['user']['screen_name'],
                    'name': tweet['user']['name'],
                    'tweets': [tweet]
                }
        

        user_data = []
        all_bloc_output = []
        all_bloc_symbols = get_default_symbols()

        bloc_params = select_bloc_params(source='File')

        for user in users.values():
            bloc_params['screen_names_or_ids'] = user['id']

            all_bloc_output.append(add_bloc_sequences(user['tweets'], all_bloc_symbols=all_bloc_symbols, **bloc_params))
            user_data.append(
                {
                    'id': user['id'],
                    'username': user['username'],
                    'name': user['name'],
                    'length': len(user['tweets'])
                }
            )
    
        user_ids = [user['id'] for user in user_data]
        bloc_params['screen_names_or_ids'] = user_ids

        return bloc_analysis(all_bloc_output, user_data, bloc_params, count_elapsed = False)


def analyze_user(usernames):
    usernames = usernames.replace(',', ' ').split()

    # Remove duplicate usernames while maintaining order
    unique_usernames = set()
    usernames = [u for u in usernames if not (u in unique_usernames or unique_usernames.add(u))]

    error_count, user_data = verify_user_exists(usernames)

    if error_count > 0:
        result = {
            'successful_generation': False,
            'query': usernames,
            'errors': user_data['errors']
        }
    else:
        user_ids = [user['id'] for user in user_data]

        gen_bloc_params = select_bloc_params(ids=user_ids, bearer_token=settings.BEARER_TOKEN, source='Account')
        
        bloc_payload = gen_bloc_for_users(**gen_bloc_params)
        all_bloc_output = bloc_payload.get('all_users_bloc', [])
        result = bloc_analysis(all_bloc_output, user_data, gen_bloc_params)

    return result

def bloc_analysis(all_bloc_output, user_data, bloc_params, count_elapsed = True):
    # Useful statistics
    gen_bloc_args = Namespace(**bloc_params)
    query_count = len(user_data)
    total_tweets = sum([user_bloc['more_details']['total_tweets'] for user_bloc in all_bloc_output])

    # Get the top BLOC words per account
    top_bloc_words = run_subcommands(gen_bloc_args, 'top_ngrams', all_bloc_output)
    user_bloc_words = {}
    if total_tweets > 0:
        for words, user in zip(top_bloc_words['per_doc'], top_bloc_words['users']):
            user_bloc_words[user] = words

    # Get the top BLOC words for all acounts and sort by frequency
    group_bloc_words = top_bloc_words.get('all_docs', [])
    if group_bloc_words:
        group_bloc_words = sorted(group_bloc_words, key=lambda x: x['term_freq'], reverse=True)

    group_top_actions = []
    group_top_syntactic = []
    group_top_semantic = []
    group_top_sentiment = []
    group_top_time = []
    group_top_change = []

    n = 1
    for word in group_bloc_words:
        type = symbols.get_symbol_type(word['term'])
        word['rank'] = n
        n = n + 1
        if type == 'Action':
            group_top_actions.append(word)
        elif type == 'Syntactic':
            group_top_syntactic.append(word)
        elif type == 'Semantic':
            group_top_semantic.append(word)
        elif type == 'Sentiment':
            group_top_sentiment.append(word)
        elif type == 'Time':
            group_top_time.append(word)
        elif type == 'Change':
            group_top_change.append(word)

    recalculate_bloc_word_rate(group_top_actions)
    recalculate_bloc_word_rate(group_top_syntactic)
    recalculate_bloc_word_rate(group_top_semantic)
    recalculate_bloc_word_rate(group_top_sentiment)
    recalculate_bloc_word_rate(group_top_time)
    recalculate_bloc_word_rate(group_top_change)

    # Generate and sort the pairwise comparisons
    pairwise_sim_report = run_subcommands(gen_bloc_args, 'sim', all_bloc_output)
    pairwise_sim_report = sorted(pairwise_sim_report, key=lambda x: x['sim'], reverse=True)

    # Generate change reports
    gen_bloc_args.keep_tweets = False
    gen_bloc_args.bloc_alphabets = ['action', 'content_syntactic']
    raw_change_report = run_subcommands(gen_bloc_args, 'change', all_bloc_output)

    result = {
        'successful_generation': True,
        'query_count': query_count,
        'total_tweets': total_tweets,
        'account_blocs': [],
        'group_top_bloc_words': group_bloc_words[:TOP_WORD_LIMIT],
        'group_top_actions': group_top_actions,
        'group_top_syntactic': group_top_syntactic,
        'group_top_semantic': group_top_semantic,
        'group_top_sentiment': group_top_sentiment,
        'group_top_time': group_top_time,
        'pairwise_sim': pairwise_sim_report,
    }

    for account_bloc, account_data in zip(all_bloc_output, user_data):
        bloc_words = user_bloc_words.get(account_data['username'], [])

        top_actions = []
        top_syntactic = []
        top_semantic = []
        top_sentiment = []
        top_time = []
        top_change = []

        n = 1
        for word in bloc_words:
            type = symbols.get_symbol_type(word['term'])
            word['rank'] = n
            n = n + 1
            if type == 'Action':
                top_actions.append(word)
            elif type == 'Syntactic':
                top_syntactic.append(word)
            elif type == 'Semantic':
                top_semantic.append(word)
            elif type == 'Sentiment':
                top_sentiment.append(word)
            elif type == 'Time':
                top_time.append(word)
            elif type == 'Change':
                top_change.append(word)

        recalculate_bloc_word_rate(top_actions)
        recalculate_bloc_word_rate(top_syntactic)
        recalculate_bloc_word_rate(top_semantic)
        recalculate_bloc_word_rate(top_sentiment)
        recalculate_bloc_word_rate(top_time)
        recalculate_bloc_word_rate(top_change)

        all_tweets = account_bloc['tweets']

        if count_elapsed:
            elapsed_time = account_bloc['elapsed_time']['gen_tweets_total_seconds'] + account_bloc['elapsed_time']['gen_bloc_total_seconds']
        else: 
            elapsed_time = -1

        change_report = {}
        for report in raw_change_report:
            if(report['screen_name'] == account_data['username']):
                change_report = link_change_report(report)

        linked_data = bloc_extension.link_data(all_tweets)

        result['account_blocs'].append({
            'user_exists': True,
            # User Data
            'account_name': account_data['name'],
            'account_username': account_data['username'],
            # BLOC Statistics
            'tweet_count': account_bloc['more_details']['total_tweets'],
            'first_tweet_date': account_bloc['more_details']['first_tweet_created_at_local_time'],
            'last_tweet_date': account_bloc['more_details']['last_tweet_created_at_local_time'],
            'elapsed_time':  elapsed_time,
            # Analysis
            'bloc_action': account_bloc['bloc']['action'],
            'bloc_syntactic': account_bloc['bloc']['content_syntactic'],
            'bloc_semantic_entity': account_bloc['bloc']['content_semantic_entity'],
            'bloc_semantic_sentiment': account_bloc['bloc']['content_semantic_sentiment'],
            'bloc_change': account_bloc['bloc']['change'],
            'change_report': change_report,
            # Top Words
            'top_bloc_words': bloc_words[:TOP_WORD_LIMIT],
            'top_actions': top_actions,
            'top_syntactic': top_syntactic,
            'top_semantic': top_semantic,
            'top_sentiment': top_sentiment,
            'top_time': top_time,
            'top_change': top_change,
            # Linked Data
            'linked_data': linked_data
            })

    return result



def recalculate_bloc_word_rate(bloc_words):
    total_freq = sum([x['term_freq'] for x in bloc_words])

    for word in bloc_words:
        term_freq = word['term_freq']
        # Seperate thousands-place using comma operator
        word['term_freq'] = f"{term_freq:,}"
        term_freq = term_freq / total_freq
        # Convert to percent but omit % symbol
        word['term_rate'] = f"{term_freq:.1%}"[:-1]


def select_bloc_params(ids=[], bearer_token='', source='Account'):
    if source == 'Account':
        account_src = 'Twitter Search'
        tweet_order = 'reverse'
    elif source == 'File':
        account_src = 'Tweet File'
        tweet_order = 'noop'

    bloc_params, _ = get_bloc_params(ids, 
                                     bearer_token, 
                                     sort_action_words=True, 
                                     keep_bloc_segments=True, 
                                     tweet_order=tweet_order, 
                                     account_src=account_src,
                                     bloc_alphabets=['action', 'content_syntactic', 'content_semantic_entity', 'content_semantic_sentiment', 'change'], 
                                     keep_tweets=True)
    return bloc_params


def link_change_report(raw_report):
    bloc_segments = raw_report['bloc_segments']
    values = {}
    # Combine details for segments (dates) and segment details (BLOC content)
    for key in bloc_segments['segments'].keys():
        values[str(key)] = bloc_segments['segments'][key] | bloc_segments['segments_details'][key]


    report = {}

    for alphabet in ['action', 'content_syntactic']:
        report[alphabet] = {}
        reports = []
        for change_event in raw_report['change_report']['self_sim'][alphabet]:
            # Add start and end details to the report
            change_event['first_segment'] = values[change_event['fst_doc_seg_id']]
            change_event['second_segment'] = values[change_event['sec_doc_seg_id']]
            # Change local_dates from a dictionary to an array
            change_event['first_segment']['local_dates'] = list(change_event['first_segment']['local_dates'])
            change_event['second_segment']['local_dates'] = list(change_event['second_segment']['local_dates'])
            # Delete report segment ID keys
            del(change_event['fst_doc_seg_id'])
            del(change_event['sec_doc_seg_id'])
            # Round change profile
            change_event['change_profile']['pause'] = round_format(change_event["change_profile"]["pause"] / 100)
            change_event['change_profile']['word'] = round_format(change_event["change_profile"]["word"] / 100)
            change_event['change_profile']['activity'] = round_format(change_event["change_profile"]["activity"] / 100)
            reports.append(change_event)

        report[alphabet]['change_events'] = reports
        report[alphabet]['change_profile'] = {
            'change_rate': round_format(raw_report['change_report']['change_rates'][alphabet]),
            'average_change': {
                'word': round_format(raw_report['change_report']['avg_change_profile_no_filter'][alphabet]['word'] / 100),
                'pause': round_format(raw_report['change_report']['avg_change_profile_no_filter'][alphabet]['pause'] / 100),
                'activity': round_format(raw_report['change_report']['avg_change_profile_no_filter'][alphabet]['activity'] / 100),
            }
        }

    return report

def round_format(value):
    return f'{float(value):.2%}'[:-1]