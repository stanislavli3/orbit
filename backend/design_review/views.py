import time

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project

from . import interference
from .models import Change, ChangeEvent, InterferenceCheck, ProjectMember
from .serializers import ChangeSerializer, InterferenceCheckSerializer, ProjectMemberSerializer


def get_project(user, pk):
    """Projects visible to the owner (team lead) and to members."""
    return get_object_or_404(
        Project.objects.filter(Q(owner=user) | Q(members__user=user)).distinct(), pk=pk
    )


def role_of(project, user):
    m = ProjectMember.objects.filter(project=project, user=user).first()
    return m.role if m else None


class MemberListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_project(request.user, pk)
        members = project.members.select_related("user").order_by("created_at")
        return Response({
            "is_owner": project.owner_id == request.user.id,
            "my_role": role_of(project, request.user),
            "members": ProjectMemberSerializer(members, many=True).data,
        })

    def post(self, request, pk):
        project = get_project(request.user, pk)
        if project.owner_id != request.user.id:
            raise PermissionDenied("Only the project owner can assign roles.")
        ser = ProjectMemberSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=ser.validated_data.get("email", "")).first()
        if user is None:
            return Response({"email": ["No user with that email."]}, status=status.HTTP_400_BAD_REQUEST)
        member, _ = ProjectMember.objects.update_or_create(
            project=project, user=user, defaults={"role": ser.validated_data["role"]}
        )
        return Response(ProjectMemberSerializer(member).data, status=status.HTTP_201_CREATED)


class MemberDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, member_id):
        project = get_project(request.user, pk)
        if project.owner_id != request.user.id:
            raise PermissionDenied("Only the project owner can remove members.")
        get_object_or_404(ProjectMember, pk=member_id, project=project).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _changes(project):
    return project.changes.select_related("author").prefetch_related(
        "events__actor", "interference_checks", "files"
    )


class ChangeListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_project(request.user, pk)
        changes = _changes(project).order_by("-created_at")
        return Response(ChangeSerializer(changes, many=True).data)

    def post(self, request, pk):
        project = get_project(request.user, pk)
        if project.owner_id != request.user.id and role_of(project, request.user) != ProjectMember.DESIGNER:
            raise PermissionDenied("Only designers (or the project owner) can submit changes.")
        ser = ChangeSerializer(data=request.data, context={"project": project})
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            change = ser.save(project=project, author=request.user)
            ChangeEvent.objects.create(change=change, actor=request.user, action=ChangeEvent.CREATED)
        return Response(ChangeSerializer(_changes(project).get(pk=change.pk)).data, status=status.HTTP_201_CREATED)


class ChangeDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk, change_id):
        project = get_project(request.user, pk)
        return Response(ChangeSerializer(get_object_or_404(_changes(project), pk=change_id)).data)


class ChangeDecisionView(APIView):
    """POST {"decision": "approved"|"rejected", "comment": "..."} — reviewers only."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, change_id):
        project = get_project(request.user, pk)
        decision = request.data.get("decision")
        if decision not in (Change.APPROVED, Change.REJECTED):
            return Response({"decision": ["Must be 'approved' or 'rejected'."]}, status=status.HTTP_400_BAD_REQUEST)
        if role_of(project, request.user) != ProjectMember.REVIEWER:
            raise PermissionDenied("Only reviewers can approve or reject changes.")
        with transaction.atomic():
            change = get_object_or_404(Change.objects.select_for_update(), pk=change_id, project=project)
            if change.author_id == request.user.id:
                raise PermissionDenied("Authors cannot review their own change.")
            if change.state != Change.PENDING:
                return Response({"detail": f"Change is already {change.state}."}, status=status.HTTP_409_CONFLICT)
            change.state = decision
            change.save(update_fields=["state"])
            ChangeEvent.objects.create(
                change=change, actor=request.user, action=decision,
                comment=str(request.data.get("comment", ""))[:5000],
            )
        return Response(ChangeSerializer(_changes(project).get(pk=change.pk)).data)


class InterferenceCheckView(APIView):
    """Run a bounding-box interference check for a part of this change.

    Body: {"changed_part": str, "neighbours": [str]?, "manual_baseline_minutes": number?,
           "layout": [{"id", "origin": [x,y,z], "size": [dx,dy,dz]}]?}
    Without ``layout`` the sample STEP assembly in samples/ is used.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, change_id):
        project = get_project(request.user, pk)
        change = get_object_or_404(Change, pk=change_id, project=project)
        changed = request.data.get("changed_part") or (change.parts[0] if change.parts else None)
        neighbours = request.data.get("neighbours") or None
        baseline = request.data.get("manual_baseline_minutes")
        if not changed:
            return Response({"changed_part": ["Required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            baseline = float(baseline) if baseline not in (None, "") else None
            start = time.perf_counter()
            boxes, source = interference.load_layout(request.data.get("layout"))
            results = interference.check(boxes, changed, neighbours)
            elapsed_ms = (time.perf_counter() - start) * 1000
        except KeyError as e:
            return Response({"detail": f"Unknown part(s): {e.args[0]}"}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            run = InterferenceCheck.objects.create(
                change=change, run_by=request.user, changed_part=changed,
                neighbours=[r["part_b"] for r in results], source=source, results=results,
                elapsed_ms=elapsed_ms, manual_baseline_minutes=baseline,
            )
            hits = [r for r in results if r["interferes"]]
            ChangeEvent.objects.create(
                change=change, actor=request.user, action=ChangeEvent.INTERFERENCE_CHECK,
                comment=f"{len(hits)} of {len(results)} neighbours interfere with {changed}",
                data={"check_id": run.id},
            )
        data = InterferenceCheckSerializer(run).data
        data["method"] = interference.APPROXIMATION_NOTE
        return Response(data, status=status.HTTP_201_CREATED)
