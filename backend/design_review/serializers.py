from rest_framework import serializers

from .models import Change, ChangeEvent, InterferenceCheck, ProjectMember


class ProjectMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(write_only=True, required=False)

    class Meta:
        model = ProjectMember
        fields = ["id", "user", "username", "email", "role", "created_at"]
        read_only_fields = ["id", "user", "username", "created_at"]


class ChangeEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username")

    class Meta:
        model = ChangeEvent
        fields = ["id", "actor", "action", "comment", "data", "created_at"]


class InterferenceCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterferenceCheck
        fields = [
            "id", "changed_part", "neighbours", "source", "results",
            "elapsed_ms", "manual_baseline_minutes", "created_at",
        ]


class ChangeSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username", read_only=True)
    events = ChangeEventSerializer(many=True, read_only=True)
    interference_checks = InterferenceCheckSerializer(many=True, read_only=True)

    class Meta:
        model = Change
        fields = [
            "id", "project", "title", "description", "author", "files", "parts",
            "state", "created_at", "events", "interference_checks",
        ]
        read_only_fields = ["id", "project", "author", "state", "created_at"]

    def validate_files(self, files):
        project = self.context["project"]
        if any(f.project_id != project.id for f in files):
            raise serializers.ValidationError("Files must belong to this project.")
        return files

    def validate_parts(self, parts):
        if not isinstance(parts, list) or not all(isinstance(p, str) for p in parts):
            raise serializers.ValidationError("parts must be a list of strings.")
        return parts
