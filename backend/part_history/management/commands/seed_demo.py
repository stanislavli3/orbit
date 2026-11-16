"""Seed the SAMPLE dataset for the hosted demo user. Safe to run on every deploy.

Reads DEMO_SEED_USERNAME (or the --username flag). When neither is set this is a
no-op, so the release step never fails on environments without a demo user.
The user is created if missing; Clerk users are stored as ``clerk_<clerk user id>``,
so seeding that username ahead of the first sign-in lands the data in their workspace.
Re-running replaces the earlier SAMPLE rows (seed_part_history is idempotent).
"""

import os

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed SAMPLE part-cost history for the demo user named by DEMO_SEED_USERNAME (no-op when unset)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None, help="Overrides DEMO_SEED_USERNAME")

    def handle(self, *args, username=None, **options):
        username = (username or os.getenv("DEMO_SEED_USERNAME", "")).strip()
        if not username:
            self.stdout.write("DEMO_SEED_USERNAME not set; skipping demo seed.")
            return
        user, created = User.objects.get_or_create(username=username)
        if created:
            self.stdout.write(f"Created demo user {username}.")
        call_command("seed_part_history", user.username, stdout=self.stdout)
