import os
import random
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import isodate
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest
from django.core.paginator import Paginator
from django.shortcuts import render

from django.utils.translation import gettext as _
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sklearn.feature_extraction.text import TfidfVectorizer
from janome.tokenizer import Tokenizer

from .models import SearchHistory, WatchHistory



# ============================================================================
# YouTube API クライアント初期化
# ============================================================================
def get_api_client():
    api_key = getattr(settings, 'YOUTUBE_API_KEY', None)
    if not api_key:
        api_key = os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        raise RuntimeError('YOUTUBE_API_KEY is not configured in Django settings or environment.')

    return build('youtube', 'v3', developerKey=api_key)


# ============================================================================
# 日付パラメータ処理
# ============================================================================
def get_iso_date(days_ago: int) -> str:
    target_date = datetime.utcnow() - timedelta(days=days_ago)
    return target_date.isoformat() + 'Z'


def get_query_parameters(request: HttpRequest) -> dict:
    return {
        'target': request.GET.get('target', 'video'),
        'query': request.GET.get('query', 'Python 自動化'),
        'max_results': int(request.GET.get('max_results', 50) or 50),
        'order': request.GET.get('order', 'viewCount'),
        'lower_threshold': int(request.GET.get('lower_threshold', 100000) or 100000),
        'upper_threshold': int(request.GET.get('upper_threshold', 500000) or 500000),
        'min_duration': int(request.GET.get('min_duration', 0) or 0),
        'max_duration': int(request.GET.get('max_duration', 60) or 60),
        'date_option': request.GET.get('date_option', 'none'),
        'selected_video_id': request.GET.get('select', ''),
    }


# ============================================================================
# リクエストパラメータ処理
# ============================================================================
def build_published_after(date_option: str):
    if date_option == '24h':
        return get_iso_date(1)
    if date_option == '7d':
        return get_iso_date(7)
    if date_option == '30d':
        return get_iso_date(30)
    return None


# ============================================================================
# 検索結果抽出・初期データ処理
# ============================================================================
def extract_items_from_search(response):
    items = response.get('items', [])
    results = []
    for item in items:
        video_id = item.get('id', {}).get('videoId')
        if not video_id:
            continue
        snippet = item.get('snippet', {})
        thumbnail = snippet.get('thumbnails', {}).get('medium', {}).get('url', '')
        results.append({
            'video_id': video_id,
            'channel_id': snippet.get('channelId', ''),
            'thumbnail_url': thumbnail,
        })
    return results


# ============================================================================
# API レスポンス キャッシング
# ============================================================================
def cached_api_call(cache_key, loader, timeout=1200):
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    result = loader()
    cache.set(cache_key, result, timeout)
    return result


# ============================================================================
# チャンネル・動画詳細情報取得
# ============================================================================
def collect_subscriber_counts(youtube, channel_ids):
    if not channel_ids:
        return {}

    cache_key = f'yt_subscriber_counts::{"|".join(channel_ids)}'

    api_items = cached_api_call(cache_key, lambda: youtube.channels().list(
        id=','.join(channel_ids),
        part='statistics',
        fields='items(id,statistics(subscriberCount))'
    ).execute().get('items', []), timeout=300)

    return {
        item.get('id'): int(item.get('statistics', {}).get('subscriberCount', 0) or 0)
        for item in api_items
    }


def collect_video_details(youtube, video_ids):
    if not video_ids:
        return []

    cache_key = f'yt_video_details::{"|".join(video_ids)}'
    # fields に snippet(channelTitle,tags) を追加
    return cached_api_call(cache_key, lambda: youtube.videos().list(
        id=','.join(video_ids),
        part='snippet,statistics,contentDetails,liveStreamingDetails,status',
        fields='items(id,snippet(title,publishedAt,channelTitle,tags),statistics(viewCount),contentDetails(duration),liveStreamingDetails(concurrentViewers,actualStartTime),status(embeddable))'
    ).execute().get('items', []), timeout=300)


# ============================================================================
# 動画データ変換・フォーマット処理
# ============================================================================
def parse_duration_seconds(raw_duration: str) -> int:
    if not raw_duration:
        return 0
    return int(isodate.parse_duration(raw_duration).total_seconds())


def format_elapsed_time(start_time_str: str) -> str:
    if not start_time_str:
        return _('不明')

    start_time = isodate.parse_datetime(start_time_str)
    now = datetime.now(timezone.utc)
    elapsed = now - start_time
    hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)
    return f'{hours}時間{minutes}分'


# ============================================================================
# YouTube 検索 API 呼び出し
# ============================================================================
def search_videos(youtube, q: str, max_results: int, order: str, published_after: str):
    cache_key = f'yt_search_video::{q}::{max_results}::{order}::{published_after or "none"}'

    def loader():
        params = {
            'q': q,
            'part': 'id,snippet',
            'order': order,
            'type': 'video',
            'maxResults': max_results,
        }
        if published_after:
            params['publishedAfter'] = published_after
        return youtube.search().list(**params).execute()

    response = cached_api_call(cache_key, loader, timeout=300)
    return extract_items_from_search(response)


def search_live_streams(youtube, q: str, max_results: int, order: str):
    cache_key = f'yt_search_live::{q}::{max_results}::{order}'

    def loader():
        return youtube.search().list(
            q=q,
            part='id,snippet',
            order=order,
            type='video',
            eventType='live',
            maxResults=max_results,
        ).execute()

    response = cached_api_call(cache_key, loader, timeout=300)
    return extract_items_from_search(response)


# ============================================================================
# 検索結果の構築・フィルタリング（登録者数、時間フィルタなど）
# ============================================================================
def build_search_results(youtube, raw_items, threshold, min_dur, max_dur, is_live: bool):
    channel_ids = [item['channel_id'] for item in raw_items if item.get('channel_id')]
    subscriber_counts = collect_subscriber_counts(youtube, channel_ids)

    filtered_items = []
    for item in raw_items:
        subscriber_count = subscriber_counts.get(item['channel_id'], 0)
        if subscriber_count < threshold[0] or subscriber_count > threshold[1]:
            continue
        filtered_items.append({
            **item,
            'subscriber_count': subscriber_count,
        })

    if not filtered_items:
        return []

    video_ids = [item['video_id'] for item in filtered_items]
    details = collect_video_details(youtube, video_ids)
    detail_map = {item['id']: item for item in details}

    results = []
    for item in filtered_items:
        detail = detail_map.get(item['video_id'])
        if not detail:
            continue

        snippet = detail.get('snippet', {})
        statistics = detail.get('statistics', {})
        content_details = detail.get('contentDetails', {})
        live_details = detail.get('liveStreamingDetails', {})

        if is_live:
            view_count = int(live_details.get('concurrentViewers', 0) or 0)
            display_time = format_elapsed_time(live_details.get('actualStartTime'))
            buzz_rate = round((view_count / item['subscriber_count'] * 1000) if item['subscriber_count'] else 0, 2)
        else:
            duration_seconds = parse_duration_seconds(content_details.get('duration'))
            if duration_seconds < min_dur * 60 or duration_seconds > max_dur * 60:
                continue
            view_count = int(statistics.get('viewCount', 0) or 0)
            display_time = snippet.get('publishedAt', '').split('T')[0].replace('-', '/') if snippet.get('publishedAt') else _('不明')
            buzz_rate = round((view_count / item['subscriber_count'] * 100) if item['subscriber_count'] else 0, 2)

        results.append({
            'video_id': item['video_id'],
            'title': snippet.get('title', 'タイトルなし'),
            'channel_title': snippet.get('channelTitle', '不明'), # チャンネル名を追加
            'tags': snippet.get('tags', []),                     # タグを追加
            'thumbnail_url': item['thumbnail_url'],
            'view_count': view_count,
            'subscriber_count': item['subscriber_count'],
            'buzz_rate': buzz_rate,
            'display_time': display_time,
            'duration_formatted': content_details.get('duration', ''), # 生のISO8601形式を保持
            'embeddable': detail.get('status', {}).get('embeddable', True),
        })

    return results


def get_error_message(exception: HttpError) -> str:
    status_code = exception.resp.status
    if status_code == 403:
        return _('APIの利用制限（Quota）を超えたか、権限がありません。')
    if status_code == 404:
        return _('リソースが見つかりませんでした。')

    details = ''
    try:
        details = exception.error_details[0].get('reason', '')
    except Exception:
        pass

    if details == 'quotaExceeded':
        return _('【原因：クォータ切れ】本日のAPI利用制限を超えました。明日まで待つか、別のAPIキーを使用してください。')

    return _('YouTube APIエラーが発生しました (Status: %(status)s)') % {'status': status_code}


# ============================================================================
# おすすめ動画生成アルゴリズム
# ============================================================================
def get_recommendation_queries(watch_history, search_history):
    """履歴を解析して検索クエリのリストを生成する"""

        # 1. 視聴履歴のタイトルから重要単語を抽出 (TF-IDF)
    titles = [h.title for h in watch_history[:10]]
    tfidf_words = []
    if titles:
        t = Tokenizer()
        def japanese_tokenizer(text):
            # Janomeを使用して名詞のみを抽出
            return [token.surface for token in t.tokenize(text) if token.part_of_speech.startswith('名詞')]

        # 文字列が空でないものだけをフィルタリング
        valid_titles = [t for t in titles if japanese_tokenizer(t)]

        if valid_titles:
            vectorizer = TfidfVectorizer(tokenizer=japanese_tokenizer, token_pattern=None, max_features=10)
            try:
                # 行列としてフィットさせる
                tfidf_matrix = vectorizer.fit_transform(valid_titles)
                # get_feature_names_out を使用して単語リストを取得
                tfidf_words = vectorizer.get_feature_names_out().tolist()
            except ValueError:
                tfidf_words = []

    # 2. 視聴履歴から頻出タグを抽出
    all_tags = []
    for h in watch_history[:10]:
        if h.tags:
            all_tags.extend(h.tags)
    common_tags = [tag for tag, count in Counter(all_tags).most_common(10)]

    # 3. 直近の検索クエリを抽出
    search_queries = [h.query for h in search_history[:5]]

    # クエリ生成
    generated_queries = []

    # 4. (TF-IDF単語) + (共通タグ)
    if tfidf_words and common_tags:
        for _ in range(2):
            q = f"{random.choice(tfidf_words)} {random.choice(common_tags)}"
            generated_queries.append(q)

    # 5. (共通タグ) + (過去検索クエリ)
    if common_tags and search_queries:
        for _ in range(2):
            q = f"{random.choice(common_tags)} {random.choice(search_queries)}"
            generated_queries.append(q)

    return list(set(generated_queries)) # 重複除去

def recommendations_view(request):
    """おすすめ動画を表示する専用ビュー"""
    cache_key = 'user_recommendations_data'
    results = cache.get(cache_key)

    if results is None:
        watch_history = WatchHistory.objects.all()
        search_history = SearchHistory.objects.all()

        if not watch_history and not search_history:
            return render(request, 'youtube_app/recommendations.html', {'results': [], 'message': '履歴が足りないためおすすめを表示できません。'})

        queries = get_recommendation_queries(watch_history, search_history)
        youtube = get_api_client()


        raw_results = []
        watched_ids = set(WatchHistory.objects.values_list('video_id', flat=True))

        for q in queries:
            try:
                # YouTube API 検索実行
                search_response = youtube.search().list(
                    q=q,
                    part='id,snippet',
                    maxResults=5,
                    type='video'
                ).execute()

                for item in search_response.get('items', []):
                    v_id = item['id'].get('videoId')
                    if v_id and v_id not in watched_ids:
                        raw_results.append({
                            'video_id': v_id,
                            'channel_id': item['snippet']['channelId'],
                            'thumbnail_url': item['snippet']['thumbnails']['medium']['url'],
                        })
            except Exception:
                continue # APIエラー時はスキップ

        # 重複除去と詳細情報の取得
        unique_raw = {res['video_id']: res for res in raw_results}.values()
        if unique_raw:
            results = build_search_results(
                youtube,
                list(unique_raw),
                threshold=(0, 100000000),
                min_dur=3, max_dur=1000,
                is_live=False
            )
        else:
            results = []
            
        # 1時間キャッシュ
        cache.set(cache_key, results, 3600)

    return render(request, 'youtube_app/recommendations.html', {'results': results})
# ============================================================================
# ヘルパー関数（URL パラメータ処理）
# ============================================================================
def build_query_string_without_select(request):
    params = request.GET.copy()
    params.pop('select', None)
    return params.urlencode()
# ============================================================================
# メインビュー：検索フォーム表示・検索実行・結果表示
# ============================================================================
def search_view(request):
    context = get_query_parameters(request)
    context['base_query_string'] = build_query_string_without_select(request)
    context['is_video_mode'] = context['target'] == 'video'
    context['results'] = []
    context['error_message'] = ''

    if request.GET:
        try:
            youtube = get_api_client()
            published_after = build_published_after(context['date_option'])

            if context['target'] == 'video':
                raw_results = search_videos(
                    youtube,
                    q=context['query'],
                    max_results=context['max_results'],
                    order=context['order'],
                    published_after=published_after,
        )
                context['results'] = build_search_results(
                    youtube,
                    raw_results,
                    threshold=(context['lower_threshold'], context['upper_threshold']),
                    min_dur=context['min_duration'],
                    max_dur=context['max_duration'],
                    is_live=False,
                )
            else:
                raw_results = search_live_streams(
                    youtube,
                    q=context['query'],
                    max_results=context['max_results'],
                    order=context['order'],
                )
                context['results'] = build_search_results(
                    youtube,
                    raw_results,
                    threshold=(context['lower_threshold'], context['upper_threshold']),
                    min_dur=0,
                    max_dur=0,
                    is_live=True,
                )

            # 検索結果をセッションに保存（target情報を付与）
            for r in context['results']:
                r['target'] = context['target']
            request.session['search_results'] = context['results']

            context['selected_video_id'] = context['selected_video_id'] or (context['results'][0]['video_id'] if context['results'] else '')

            if 'query' in request.GET and 'select' not in request.GET:
                # 最新100件を残して古い検索履歴を削除
                history_ids = SearchHistory.objects.values_list('id', flat=True)[:99]
                SearchHistory.objects.exclude(id__in=list(history_ids)).delete()

                SearchHistory.objects.create(
                    target=context['target'],
                    query=context['query'],
                    max_results=context['max_results'],
                    order=context['order'],
                    lower_threshold=context['lower_threshold'],
                    upper_threshold=context['upper_threshold'],
                    min_duration=context['min_duration'],
                    max_duration=context['max_duration'],
                    date_option=context['date_option'],
                    results_count=len(context['results']),
                )

        except HttpError as e:
            context['error_message'] = get_error_message(e)
        except Exception as e:
            context['error_message'] = str(e)

    context['recent_history'] = SearchHistory.objects.all()[:5]
    return render(request, 'youtube_app/search.html', context)


# ============================================================================
# 履歴表示ビュー
# ============================================================================
def history_view(request):
    """検索履歴と動画視聴履歴を一覧表示する。"""
    search_list = SearchHistory.objects.all()
    watch_list = WatchHistory.objects.all()

    # ページネーション設定
    search_page_num = request.GET.get('s_page', 1)
    watch_page_num = request.GET.get('w_page', 1)

    search_paginator = Paginator(search_list, 20)  # 検索履歴は1ページ20件
    watch_paginator = Paginator(watch_list, 14)    # 動画履歴は1ページ14件

    context = {
        'search_history': search_paginator.get_page(search_page_num),
        'watch_history': watch_paginator.get_page(watch_page_num),
    }
    return render(request, 'youtube_app/history.html', context)



# ============================================================================
# HTMX エンドポイント：動画選択時にプレイヤーHTMLフラグメントを返す
# ============================================================================
def select_video(request):
    """HTMX からの動画選択リクエストに応じて、YouTube プレイヤーの HTML フラグメントを返す。"""
    video_id = request.GET.get('video_id', '')
    if not video_id:
        return render(request, 'youtube_app/player_fragment.html', {'selected_video_id': ''})

    # 1. セッション（検索結果）から動画データを取得
    search_results = request.session.get('search_results', [])
    video_data = next((item for item in search_results if item['video_id'] == video_id), None)

    # 2. セッションにない場合、キャッシュ（おすすめ動画）から動画データを取得
    if not video_data:
        recommendations = cache.get('user_recommendations_data', [])
        video_data = next((item for item in recommendations if item['video_id'] == video_id), None)

    if video_data:
        # 最新100件を残して古い視聴履歴を削除
        history_ids = WatchHistory.objects.values_list('id', flat=True)[:99]
        WatchHistory.objects.exclude(id__in=list(history_ids)).delete()

        # WatchHistory に channel_title と tags を確実に保存
        WatchHistory.objects.update_or_create(
            video_id=video_id,
            defaults={
                'title': video_data.get('title', 'タイトルなし'),
                'thumbnail_url': video_data.get('thumbnail_url', ''),
                'channel_title': video_data.get('channel_title', '不明'),
                'tags': video_data.get('tags', []),
                'view_count': video_data.get('view_count', 0),
                'subscriber_count': video_data.get('subscriber_count', 0),
                'video_type': video_data.get('target', 'video'),
            }
        )
    return render(request, 'youtube_app/player_fragment.html', {'selected_video_id': video_id})

