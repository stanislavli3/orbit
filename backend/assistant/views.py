import os
from typing import List

import anthropic
from django.shortcuts import get_object_or_404
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

        ChatMessage.objects.create(session=session, role="user", content=message)

        relevant_files = find_relevant_files(
            query=message,
            user=request.user,
            project_id=project.id if project else None,
            top_k=5,
        )
        context_block = build_context_prompt(relevant_files)
        system_prompt = build_system_prompt(context_block)

        history: List[dict] = list(
            session.messages.order_by("-created_at")[:10].values("role", "content")
        )
        history = list(reversed(history))

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return self._graceful_failure(
                session, relevant_files, "AI assistant is not configured."
            )

        client = anthropic.Anthropic(api_key=api_key)
        messages_payload = [{"role": "system", "content": system_prompt}]
        for item in history:
            messages_payload.append({"role": item["role"], "content": item["content"]})
        messages_payload.append({"role": "user", "content": message})

        try:
            completion = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
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
