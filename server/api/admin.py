from django.contrib import admin

from .models import (FeedbackRule, Item, LearnerProfile, Recording,
                     TargetSegment)


@admin.register(FeedbackRule)
class FeedbackRuleAdmin(admin.ModelAdmin):
    list_display = ("phone", "dim", "direction", "text")
    list_filter = ("phone", "dim", "direction")
    search_fields = ("text",)


@admin.register(LearnerProfile)
class LearnerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "native_language")
    list_filter = ("native_language",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("text", "ipa", "kind", "level", "focus_segments",
                    "mfa_pron", "hat_varianten")
    list_filter = ("kind", "level")
    search_fields = ("text", "ipa")

    @admin.display(boolean=True, description="Fehlervarianten")
    def hat_varianten(self, item):
        return bool(item.variant_list())


@admin.register(TargetSegment)
class TargetSegmentAdmin(admin.ModelAdmin):
    list_display = ("phone", "speaker", "f1_mean", "f1_sd", "f2_mean", "f2_sd")
    list_filter = ("speaker",)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "item", "speaker", "status",
                    "ist_referenz", "created_at")
    list_editable = ("ist_referenz",)
    list_filter = ("status", "speaker", "ist_referenz", "user")
    readonly_fields = ("result", "created_at")
