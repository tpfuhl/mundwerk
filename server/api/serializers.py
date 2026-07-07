from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Item, Recording


class RegisterSerializer(serializers.Serializer):
    vorname = serializers.CharField(max_length=150)
    nachname = serializers.CharField(max_length=150)
    nickname = serializers.CharField(max_length=150)
    muttersprache = serializers.RegexField(
        r"^[A-Za-z]{2}$",
        error_messages={"invalid": "Muttersprache als ISO-639-1-Code angeben, z. B. fr, en, it."})

    def validate_nickname(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Dieser Nickname ist schon vergeben.")
        return value


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
