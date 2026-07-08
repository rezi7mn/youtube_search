from django.contrib import admin

from .models import SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('query', 'target', 'results_count', 'created_at')
    list_filter = ('target', 'date_option', 'created_at')
    search_fields = ('query',)
    readonly_fields = ('created_at',)
