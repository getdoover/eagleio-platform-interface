"""
Basic tests for an application.

This ensures all modules are importable and that the config is valid.
"""

def test_import_app():
    from eagleio_platform_interface.application import EagleioPlatformInterfaceApplication
    assert EagleioPlatformInterfaceApplication

def test_config():
    from eagleio_platform_interface.app_config import EagleioPlatformInterfaceConfig

    config = EagleioPlatformInterfaceConfig()
    assert isinstance(config.to_dict(), dict)

def test_ui():
    from eagleio_platform_interface.app_ui import EagleioPlatformInterfaceUI
    assert EagleioPlatformInterfaceUI

def test_state():
    from eagleio_platform_interface.app_state import EagleioPlatformInterfaceState
    assert EagleioPlatformInterfaceState