from pydoover.docker import run_app

from .application import EagleioPlatformInterfaceApplication
from .app_config import EagleioPlatformInterfaceConfig

def main():
    """
    Run the application.
    """
    run_app(EagleioPlatformInterfaceApplication(config=EagleioPlatformInterfaceConfig()))
