import csv
import io

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import TeamContact
from .serializers import TeamContactSerializer


class TeamContactListCreateView(generics.ListCreateAPIView):
    serializer_class = TeamContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = TeamContact.objects.filter(workspace_owner=self.request.user)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(full_name__icontains=search) | qs.filter(
                role__icontains=search
            )
        tag = self.request.query_params.get("tag", "").strip()
        if tag:
            qs = qs.filter(expertise_tags__contains=tag)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            workspace_owner=self.request.user,
            added_by=self.request.user,
        )


class TeamContactRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TeamContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return TeamContact.objects.filter(workspace_owner=self.request.user)


class TeamContactImportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    # Expected CSV columns (case-insensitive)
    REQUIRED_COLS = {"name", "email", "role"}
    OPTIONAL_COLS = {"department", "tags"}

    def post(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return Response(
                {"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        dry_run = request.query_params.get("preview", "false").lower() == "true"

        try:
            text = csv_file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response(
                {"detail": "File must be UTF-8 encoded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return Response(
                {"detail": "CSV file is empty."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Normalise header names
        col_map = {h.strip().lower(): h for h in reader.fieldnames}
        missing = self.REQUIRED_COLS - set(col_map.keys())
        if missing:
            return Response(
                {"detail": f"Missing required columns: {', '.join(sorted(missing))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows = []
        errors = []
        for i, row in enumerate(reader, start=2):  # row 1 = header
            name = row.get(col_map.get("name", ""), "").strip()
            email = row.get(col_map.get("email", ""), "").strip()
            role = row.get(col_map.get("role", ""), "").strip()
            department = row.get(col_map.get("department", ""), "").strip()
            tags_raw = row.get(col_map.get("tags", ""), "").strip()
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

            row_errors = []
            if not name:
                row_errors.append("Name is required")
            if not email:
                row_errors.append("Email is required")
            if not role:
                row_errors.append("Role is required")

            if row_errors:
                errors.append({"row": i, "errors": row_errors, "data": {"name": name, "email": email}})
            else:
                rows.append(
                    {
                        "full_name": name,
                        "email": email,
                        "role": role,
                        "department": department,
                        "expertise_tags": tags,
                    }
                )

        if dry_run:
            return Response(
                {
                    "preview": rows,
                    "errors": errors,
                    "valid_count": len(rows),
                    "error_count": len(errors),
                },
                status=status.HTTP_200_OK,
            )

        # Commit valid rows
        created = []
        skipped = []
        for entry in rows:
            obj, made = TeamContact.objects.get_or_create(
                workspace_owner=request.user,
                email=entry["email"],
                defaults={
                    **entry,
                    "added_by": request.user,
                },
            )
            if made:
                created.append(TeamContactSerializer(obj).data)
            else:
                skipped.append(entry["email"])

        return Response(
            {
                "created": created,
                "skipped": skipped,
                "errors": errors,
                "created_count": len(created),
                "skipped_count": len(skipped),
                "error_count": len(errors),
            },
            status=status.HTTP_201_CREATED,
        )


class TeamContactMatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        question_type = request.query_params.get("question_type", "").strip().lower()
        if not question_type:
            return Response(
                {"detail": "question_type parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contacts = TeamContact.objects.filter(
            workspace_owner=request.user, allow_automated=True
        )

        # Exact tag match first, then partial name/role match
        exact = [c for c in contacts if question_type in [t.lower() for t in c.expertise_tags]]
        if exact:
            return Response(TeamContactSerializer(exact[0]).data)

        partial = [
            c
            for c in contacts
            if question_type in c.role.lower() or question_type in c.department.lower()
        ]
        if partial:
            return Response(TeamContactSerializer(partial[0]).data)

        return Response(
            {"detail": "No matching contact found."}, status=status.HTTP_404_NOT_FOUND
        )
