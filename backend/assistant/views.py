import os
from typing import List

import anthropic
from django.db.models import Subquery, OuterRef
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from files_api.models import UploadedFile
from .models import ChatSession, ChatMessage
from .rag import find_relevant_files, build_context_prompt, build_system_prompt


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "").strip()
        project_id = request.data.get("project_id")
        incoming_session_id = request.data.get("session_id")

        if not message:
            return Response(
                {"error": "Message is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = None
        if project_id:
            project = get_object_or_404(Project, id=project_id, owner=request.user)

        session = None
        if incoming_session_id:
            session = ChatSession.objects.filter(
                session_id=incoming_session_id, user=request.user
            ).first()

        if not session:
            session = ChatSession.objects.create(user=request.user, project=project)

        # Load history BEFORE saving the current message to avoid duplication
        history: List[dict] = list(
            session.messages.order_by("-created_at")[:9].values("role", "content")
        )
        history = list(reversed(history))

        ChatMessage.objects.create(session=session, role="user", content=message)

        relevant_files = find_relevant_files(
            query=message,
            user=request.user,
            project_id=project.id if project else None,
            top_k=5,
        )
        context_block = build_context_prompt(relevant_files)
        system_prompt = build_system_prompt(context_block)

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return self._graceful_failure(
                session, relevant_files, "AI assistant is not configured."
            )

        client = anthropic.Anthropic(api_key=api_key)
        messages_payload = []
        for item in history:
            messages_payload.append({"role": item["role"], "content": item["content"]})
        messages_payload.append({"role": "user", "content": message})

        try:
            completion = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                messages=messages_payload,
            )
            content = completion.content[0].text.strip()
        except Exception:
            return self._graceful_failure(
                session, relevant_files, "AI assistant is not configured."
            )

        ChatMessage.objects.create(session=session, role="assistant", content=content)

        sources = [file.id for file in relevant_files]
        source_files = [
            {"id": file.id, "name": file.original_name} for file in relevant_files
        ]

        return Response(
            {
                "response": content,
                "session_id": str(session.session_id),
                "sources": sources,
                "source_files": source_files,
            },
            status=status.HTTP_200_OK,
        )

    def _graceful_failure(
        self, session: ChatSession, relevant_files: List[UploadedFile], error: str
    ) -> Response:
        content = error
        ChatMessage.objects.create(session=session, role="assistant", content=content)
        sources = [file.id for file in relevant_files]
        source_files = [
            {"id": file.id, "name": file.original_name} for file in relevant_files
        ]
        return Response(
            {
                "response": content,
                "session_id": str(session.session_id),
                "sources": sources,
                "source_files": source_files,
                "error": error,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class SessionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sessions = ChatSession.objects.filter(user=request.user).order_by("-created_at")

        filter_type = request.query_params.get("filter", "all")
        if filter_type == "today":
            today = timezone.now().date()
            sessions = sessions.filter(created_at__date=today)
        elif filter_type == "starred":
            sessions = sessions.filter(is_starred=True)

        first_msg_subq = (
            ChatMessage.objects.filter(session=OuterRef("pk"), role="user")
            .order_by("created_at")
            .values("content")[:1]
        )
        sessions = sessions.annotate(first_message=Subquery(first_msg_subq))

        data = []
        for session in sessions:
            raw = session.first_message or ""
            title = (raw[:60] + "…" if len(raw) > 60 else raw) if raw else "New conversation"
            data.append(
                {
                    "session_id": str(session.session_id),
                    "title": title,
                    "is_starred": session.is_starred,
                    "created_at": session.created_at.isoformat(),
                }
            )

        return Response(data)


class SessionMessagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ChatSession, session_id=session_id, user=request.user)
        messages = session.messages.all()
        data = [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ]
        return Response({"session_id": str(session.session_id), "messages": data})


class SessionStarView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, session_id):
        session = get_object_or_404(ChatSession, session_id=session_id, user=request.user)
        session.is_starred = not session.is_starred
        session.save(update_fields=["is_starred"])
        return Response(
            {"session_id": str(session.session_id), "is_starred": session.is_starred}
        )
