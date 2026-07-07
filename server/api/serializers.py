from rest_framework import serializers

from .models import Item, Recording


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "text", "ipa", "level", "focus_segments"]


class RecordingSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)
    item_id = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.all(), source="item", write_only=True)

    class Meta:
        model = Recording
        fields = ["id", "item", "item_id", "audio", "speaker",
                  "status", "result", "created_at"]
        read_only_fields = ["status", "result", "created_at"]
