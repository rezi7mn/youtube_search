from django.db import models
from django.contrib.auth.models import User


class SearchHistory(models.Model):
    target = models.CharField(max_length=16, default='video')
    query = models.CharField(max_length=255)
    max_results = models.PositiveSmallIntegerField(default=50)
    order = models.CharField(max_length=32, default='viewCount')
    lower_threshold = models.PositiveIntegerField(default=100000)
    upper_threshold = models.PositiveIntegerField(default=500000)
    min_duration = models.PositiveIntegerField(default=0)
    max_duration = models.PositiveIntegerField(default=60)
    date_option = models.CharField(max_length=16, default='none')
    results_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_histories', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.query} ({self.target}) - {self.created_at:%Y-%m-%d %H:%M}'



class WatchHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watch_histories', null=True, blank=True)
    video_id = models.CharField(max_length=20) # unique=True を削除（ユーザーごとに持つため）
    # ... existing fields ...

    class Meta:
        ordering = ['-watched_at']
        unique_together = ('user', 'video_id') # ユーザーと動画IDのペアで一意にする

    def get_order_display_text(self):
        mapping = {
            'date': '新しい順',
            'viewCount': '表示回数の多い順',
            'rating': '評価が高い順',
            'relevance': '関連性が高い順',
        }
        # マッピングになければ「関連度順」をデフォルトにする
        return mapping.get(self.order, '関連性が高い順')


class WatchHistory(models.Model):
    video_id = models.CharField(max_length=20)
    title = models.CharField(max_length=255)
    thumbnail_url = models.URLField()
    channel_title = models.CharField(max_length=255)
    tags = models.JSONField(default=list, blank=True)
    view_count = models.PositiveBigIntegerField(default=0)
    subscriber_count = models.PositiveBigIntegerField(default=0)
    video_type = models.CharField(max_length=16, default='video')
    watched_at = models.DateTimeField(auto_now=True) # auto_now に変更（更新時に現在時刻へ自動更新）
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watch_histories', null=True, blank=True)

    class Meta:
        ordering = ['-watched_at']
        unique_together = ('user', 'video_id') # 同じユーザーが同じ動画を複数保存しないように
        
    def __str__(self):
        return f'{self.title}'

