from django.contrib import admin

from .models import Item, LearnerProfile, Recording, TargetSegment


@admin.register(LearnerProfile)
class LearnerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "native_language")
    list_filter = ("native_language",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("text", "ipa", "level", "focus_segments")
    list_filter = ("level",)
    search_fields = ("text", "ipa")


@admin.register(TargetSegment)
class TargetSegmentAdmin(admin.ModelAdmin):
    list_display = ("phone", "speaker", "f1_mean", "f1_sd", "f2_mean", "f2_sd")
    list_filter = ("speaker",)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "speaker", "status", "created_at")
    list_filter = ("status", "speaker")
    readonly_fields = ("result", "created_at")
