from django.apps import AppConfig


class BomAgentConfig(AppConfig):
    name = "bom_agent"

    def ready(self):
        from . import checks  # noqa: F401  registers system checks
