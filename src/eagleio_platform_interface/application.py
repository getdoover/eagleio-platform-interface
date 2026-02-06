import json
import logging
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from pydoover.cloud.processor import Application, MessageCreateEvent
from pydoover.cloud.processor.types import ScheduleEvent

from .app_config import EagleioPlatformInterfaceConfig

log = logging.getLogger(__name__)


class EagleioPlatformInterfaceApplication(Application):
    config: EagleioPlatformInterfaceConfig

    async def setup(self):
        """Initialize per-invocation state and validate configuration."""
        self._api_key = self.config.api_key.value
        self._base_url = (self.config.base_url.value or "https://api.eagle.io/api/v1").rstrip("/")
        self._poll_enabled = self.config.poll_enabled.value
        self._outbound_enabled = self.config.outbound_enabled.value

        # Parse tag mappings into a convenient list of dicts
        self._mappings = []
        if self.config.tag_mappings.elements:
            for mapping_obj in self.config.tag_mappings.elements:
                self._mappings.append({
                    "tag_name": mapping_obj.tag_name.value,
                    "eagleio_node_id": mapping_obj.eagleio_node_id.value,
                    "direction": mapping_obj.direction.value or "both",
                    "source_app_key": mapping_obj.source_app_key.value,
                })

        # Load persisted sync stats
        self._sync_stats = await self.get_tag("sync_stats", {
            "inbound_ok": 0,
            "inbound_fail": 0,
            "outbound_ok": 0,
            "outbound_fail": 0,
        })

        # Validate API key
        if not self._api_key:
            log.warning("No API key configured - Eagle.io operations will fail")
            await self.set_tag("connection_status", "error")
            await self.set_tag("last_error", "No API key configured")
        else:
            await self._check_connection()

    async def close(self):
        """Clean up after invocation."""
        pass

    # ── Event Handlers ──────────────────────────────────────────────────

    async def on_message_create(self, event: MessageCreateEvent):
        """Handle tag value updates from subscribed channels (outbound sync)."""
        if not self._outbound_enabled:
            log.debug("Outbound sync disabled, skipping message")
            return

        if not self._api_key:
            log.warning("No API key configured, cannot push to Eagle.io")
            return

        data = event.message.data
        if not isinstance(data, dict):
            try:
                data = json.loads(data) if isinstance(data, str) else {}
            except (json.JSONDecodeError, TypeError):
                log.debug("Message data is not a dict or JSON string, skipping")
                return

        outbound_mappings = [
            m for m in self._mappings
            if m["direction"] in ("to_eagleio", "both")
        ]

        if not outbound_mappings:
            return

        success_count = 0
        fail_count = 0

        for mapping in outbound_mappings:
            tag_name = mapping["tag_name"]
            node_id = mapping["eagleio_node_id"]
            source_app_key = mapping["source_app_key"]

            # Try to get the value from the message data first
            value = data.get(tag_name)

            # If not in the message, read the tag directly
            if value is None:
                if source_app_key:
                    # Read from another app's tag namespace
                    value = self._get_tag_from_app(source_app_key, tag_name)
                else:
                    value = await self.get_tag(tag_name)

            if value is None:
                log.debug(f"No value found for tag '{tag_name}', skipping outbound sync")
                continue

            ok = await self._put_eagleio_value(node_id, value)
            if ok:
                success_count += 1
            else:
                fail_count += 1

        self._sync_stats["outbound_ok"] = self._sync_stats.get("outbound_ok", 0) + success_count
        self._sync_stats["outbound_fail"] = self._sync_stats.get("outbound_fail", 0) + fail_count
        await self._update_sync_status("outbound", success_count, fail_count)

    async def on_schedule(self, event: ScheduleEvent):
        """Poll Eagle.io for current parameter values (inbound sync)."""
        if not self._poll_enabled:
            log.debug("Inbound polling disabled, skipping schedule")
            return

        if not self._api_key:
            log.warning("No API key configured, cannot poll Eagle.io")
            return

        inbound_mappings = [
            m for m in self._mappings
            if m["direction"] in ("from_eagleio", "both")
        ]

        if not inbound_mappings:
            return

        # Load cached values to detect changes
        cached_values = await self.get_tag("eagleio_values", {})
        success_count = 0
        fail_count = 0

        for mapping in inbound_mappings:
            tag_name = mapping["tag_name"]
            node_id = mapping["eagleio_node_id"]

            result = await self._get_eagleio_value(node_id)
            if result is None:
                fail_count += 1
                continue

            value = result.get("value")
            cached_value = cached_values.get(node_id, {}).get("value")

            # Update Doover tag with the fetched value
            await self.set_tag(tag_name, value)

            # Update cache
            cached_values[node_id] = {
                "value": value,
                "time": result.get("time"),
                "quality": result.get("quality"),
            }
            success_count += 1

        # Persist updated cache
        await self.set_tag("eagleio_values", cached_values)

        self._sync_stats["inbound_ok"] = self._sync_stats.get("inbound_ok", 0) + success_count
        self._sync_stats["inbound_fail"] = self._sync_stats.get("inbound_fail", 0) + fail_count
        await self._update_sync_status("inbound", success_count, fail_count)

    # ── Tag Helpers ───────────────────────────────────────────────────────

    def _get_tag_from_app(self, app_key: str, tag_name: str, default=None):
        """Read a tag from another app's namespace via _tag_values."""
        try:
            return self._tag_values[app_key][tag_name]
        except (KeyError, TypeError):
            return default

    # ── Eagle.io API Methods ────────────────────────────────────────────

    async def _check_connection(self):
        """Validate API key by making a lightweight request."""
        try:
            # Use a simple GET to validate the key; we just check for auth success
            url = f"{self._base_url}/nodes?attr=name&filter=_class(Source)&$limit=1"
            req = Request(url, method="GET")
            req.add_header("X-Api-Key", self._api_key)
            req.add_header("Content-Type", "application/json")

            response = urlopen(req, timeout=10)
            if response.status == 200:
                await self.set_tag("connection_status", "connected")
                await self.set_tag("last_error", None)
                log.info("Eagle.io connection validated successfully")
            else:
                await self.set_tag("connection_status", "error")
                await self.set_tag("last_error", f"Unexpected response status: {response.status}")
        except HTTPError as e:
            if e.code == 401:
                await self.set_tag("connection_status", "error")
                await self.set_tag("last_error", "Authentication failed - invalid API key")
                log.error("Eagle.io authentication failed - invalid API key")
            else:
                await self.set_tag("connection_status", "error")
                await self.set_tag("last_error", f"HTTP error {e.code}: {e.reason}")
                log.error(f"Eagle.io connection check failed: HTTP {e.code} {e.reason}")
        except (URLError, OSError) as e:
            await self.set_tag("connection_status", "error")
            await self.set_tag("last_error", f"Connection error: {str(e)}")
            log.error(f"Eagle.io connection check failed: {e}")

    async def _get_eagleio_value(self, node_id: str) -> dict | None:
        """
        Read a parameter's current value from Eagle.io.

        Returns dict with 'value', 'time', 'quality' keys or None on failure.
        """
        try:
            url = f"{self._base_url}/nodes/{node_id}?attr=currentValue"
            req = Request(url, method="GET")
            req.add_header("X-Api-Key", self._api_key)
            req.add_header("Content-Type", "application/json")

            response = urlopen(req, timeout=30)
            body = json.loads(response.read().decode("utf-8"))
            current_value = body.get("currentValue", {})
            return {
                "value": current_value.get("value"),
                "time": current_value.get("time"),
                "quality": current_value.get("quality"),
            }
        except HTTPError as e:
            await self._handle_api_error(e, f"GET node {node_id}")
            return None
        except (URLError, OSError, json.JSONDecodeError) as e:
            log.error(f"Failed to get Eagle.io node {node_id}: {e}")
            await self.set_tag("last_error", f"GET node {node_id}: {str(e)}")
            return None

    async def _put_eagleio_value(self, node_id: str, value) -> bool:
        """
        Set a parameter's current value in Eagle.io.

        Returns True on success, False on failure.
        """
        try:
            url = f"{self._base_url}/nodes/{node_id}/historic/data/value"
            payload = json.dumps({"value": value}).encode("utf-8")

            req = Request(url, data=payload, method="PUT")
            req.add_header("X-Api-Key", self._api_key)
            req.add_header("Content-Type", "application/json")

            response = urlopen(req, timeout=30)
            if response.status in (200, 202):
                log.debug(f"Successfully set Eagle.io node {node_id} to {value}")
                return True
            else:
                log.warning(f"Unexpected status {response.status} setting node {node_id}")
                return False
        except HTTPError as e:
            await self._handle_api_error(e, f"PUT node {node_id}")
            return False
        except (URLError, OSError) as e:
            log.error(f"Failed to set Eagle.io node {node_id}: {e}")
            await self.set_tag("last_error", f"PUT node {node_id}: {str(e)}")
            return False

    async def _handle_api_error(self, error: HTTPError, context: str):
        """Handle Eagle.io API errors with appropriate logging and tag updates."""
        if error.code == 401:
            await self.set_tag("connection_status", "error")
            await self.set_tag("last_error", f"Authentication failed during {context}")
            log.error(f"Eagle.io auth failed during {context}")
        elif error.code == 429:
            await self.set_tag("last_error", f"Rate limited during {context}")
            log.warning(f"Eagle.io rate limit hit during {context}")
        else:
            await self.set_tag("last_error", f"HTTP {error.code} during {context}: {error.reason}")
            log.error(f"Eagle.io API error during {context}: HTTP {error.code} {error.reason}")

    # ── Status Helpers ──────────────────────────────────────────────────

    async def _update_sync_status(self, direction: str, success_count: int, fail_count: int):
        """Update sync status tags after a sync operation."""
        now = datetime.now(timezone.utc).isoformat()
        await self.set_tag("last_sync_time", now)
        await self.set_tag("last_sync_direction", direction)
        await self.set_tag("sync_stats", self._sync_stats)

        if fail_count == 0:
            await self.set_tag("last_error", None)
        else:
            await self.set_tag(
                "last_error",
                f"{direction} sync: {fail_count} failed, {success_count} succeeded",
            )

        log.info(
            f"Eagle.io {direction} sync complete: {success_count} ok, {fail_count} failed"
        )
