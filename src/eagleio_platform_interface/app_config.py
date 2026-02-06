from pathlib import Path

from pydoover import config
from pydoover.cloud.processor import ManySubscriptionConfig, ScheduleConfig


class TagMappingObject(config.Object):
    """A single mapping between a Doover tag and an Eagle.io parameter node."""

    def __init__(self):
        super().__init__("Tag Mapping")
        self.tag_name = config.String(
            "Tag Name",
            description="Doover tag name to read/write",
        )
        self.eagleio_node_id = config.String(
            "Eagle.io Node ID",
            description="Eagle.io parameter node ID (24-char alphanumeric or @customId)",
        )
        self.direction = config.Enum(
            "Direction",
            choices=["to_eagleio", "from_eagleio", "both"],
            default="both",
            description="Data sync direction",
        )
        self.source_app_key = config.String(
            "Source App Key",
            description="Doover app key to read the tag from (for outbound). If not set, reads from own tags",
            default="",
        )


class EagleioPlatformInterfaceConfig(config.Schema):
    def __init__(self):
        self.api_key = config.String(
            "API Key",
            description="Eagle.io API key for authentication",
        )

        self.base_url = config.String(
            "Base URL",
            description="Eagle.io API base URL",
            default="https://api.eagle.io/api/v1",
        )

        self.poll_enabled = config.Boolean(
            "Poll Enabled",
            description="Enable scheduled polling of Eagle.io parameters",
            default=True,
        )

        self.outbound_enabled = config.Boolean(
            "Outbound Enabled",
            description="Enable pushing tag updates to Eagle.io",
            default=True,
        )

        self.tag_mappings = config.Array(
            "Tag Mappings",
            element=TagMappingObject(),
            description="List of tag-to-Eagle.io parameter mappings",
        )

        self.subscription = ManySubscriptionConfig()

        self.schedule = ScheduleConfig()


def export():
    EagleioPlatformInterfaceConfig().export(
        Path(__file__).parents[2] / "doover_config.json",
        "eagleio_platform_interface",
    )


if __name__ == "__main__":
    export()
