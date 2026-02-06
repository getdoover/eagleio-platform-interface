from typing import Any

from pydoover.cloud.processor import run_app

from .application import EagleioPlatformInterfaceApplication
from .app_config import EagleioPlatformInterfaceConfig


def handler(event: dict[str, Any], context):
    """Lambda handler entry point."""
    EagleioPlatformInterfaceConfig.clear_elements()
    run_app(
        EagleioPlatformInterfaceApplication(config=EagleioPlatformInterfaceConfig()),
        event,
        context,
    )
