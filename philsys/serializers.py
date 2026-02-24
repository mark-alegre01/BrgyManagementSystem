from rest_framework import serializers
from .models import PhilSysVerificationAttempt


class PhilSysVerificationAttemptSerializer(serializers.ModelSerializer):
    resident_name = serializers.CharField(
        source="resident.get_full_name", read_only=True
    )
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = PhilSysVerificationAttempt
        fields = [
            "id",
            "user",
            "user_username",
            "resident",
            "resident_name",
            "verification_method",
            "status",
            "philSys_number",
            "philSys_card_number",
            "response_data",
            "error_message",
            "ip_address",
            "created_at",
            "completed_at",
        ]
        read_only_fields = ["id", "created_at", "completed_at"]
