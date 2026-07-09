from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Item, Recording, TargetSegment


class TargetSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TargetSegment
        fields = ["phone", "speaker", "f1_mean", "f1_sd", "f2_mean", "f2_sd"]


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


class ProfileUpdateSerializer(serializers.Serializer):
    """Editierbare Profilfelder — Nickname (username) und Token bleiben fest."""

    vorname = serializers.CharField(max_length=150)
    nachname = serializers.CharField(max_length=150)
    muttersprache = serializers.RegexField(
        r"^[A-Za-z]{2}$",
        error_messages={"invalid": "Muttersprache als ISO-639-1-Code angeben, z. B. fr, en, it."})


class ItemSerializer(serializers.ModelSerializer):
    has_audio = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = ["id", "text", "ipa", "level", "kind", "gruppe",
                  "beschreibung", "has_audio", "focus_segments"]

    def get_has_audio(self, item):
        # True → App darf /api/items/{id}/audio/ abrufen (auth. Streaming).
        return bool(item.reference_audio)


class RecordingSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)
    item_id = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.all(), source="item", write_only=True)

    class Meta:
        model = Recording
        fields = ["id", "item", "item_id", "audio", "speaker",
                  "status", "result", "ist_referenz", "created_at"]
        read_only_fields = ["status", "result", "ist_referenz", "created_at"]
