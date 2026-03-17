import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional

try:
    from supabase import create_client  # type: ignore
except Exception:  # pragma: no cover
    create_client = None  # type: ignore

MENTION_OR_ID_RE = re.compile(r"(\d{15,25})")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_user_id(text: str) -> int:
    m = MENTION_OR_ID_RE.search(text.strip())
    if not m:
        raise ValueError("Could not parse a user ID/mention.")
    return int(m.group(1))


class SupabaseStore:
    """
    Expected tables (minimal):

    - cases:
        id (bigint/serial, PK)
        reporter_id (bigint)
        report_content (text)
        attachment_urls (jsonb, nullable)
        status (text)                 -- "OPEN" / "CLOSED"
        created_at (timestamptz)
        closed_at (timestamptz, nullable)
        guild_id (bigint, nullable)
        staff_channel_id (bigint, nullable)
        staff_message_id (bigint, nullable, unique)
        thread_id (bigint, nullable)

    - blacklist:
        user_id (bigint, PK)
        created_at (timestamptz)

    - dm_sessions:
        user_id (bigint, PK)
        expires_at (timestamptz)
    """

    def __init__(self, url: str, key: str):
        if create_client is None:
            raise RuntimeError("supabase is not installed. Install with: pip install -r requirements.txt")
        self._client = create_client(url, key)

    async def _run(self, fn):
        return await asyncio.to_thread(fn)

    async def is_blacklisted(self, user_id: int) -> bool:
        def _q():
            res = self._client.table("blacklist").select("user_id").eq("user_id", user_id).limit(1).execute()
            return bool(getattr(res, "data", None))

        return await self._run(_q)

    async def add_blacklist(self, user_id: int) -> None:
        def _q():
            self._client.table("blacklist").upsert({"user_id": user_id}).execute()

        await self._run(_q)

    async def create_or_refresh_session(self, user_id: int, ttl_seconds: int) -> None:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        def _q():
            self._client.table("dm_sessions").upsert(
                {"user_id": user_id, "expires_at": expires_at.isoformat() + "Z"}
            ).execute()

        await self._run(_q)

    async def pop_session_if_active(self, user_id: int) -> bool:
        now = datetime.utcnow().isoformat() + "Z"

        def _q():
            res = (
                self._client.table("dm_sessions")
                .select("user_id, expires_at")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            data = getattr(res, "data", None) or []
            if not data:
                return False

            expires_at = str(data[0].get("expires_at") or "")
            if expires_at and expires_at < now:
                self._client.table("dm_sessions").delete().eq("user_id", user_id).execute()
                return False

            self._client.table("dm_sessions").delete().eq("user_id", user_id).execute()
            return True

        return await self._run(_q)

    async def create_case(self, reporter_id: int, report_content: str, attachment_urls: list[str]) -> int:
        payload: dict[str, Any] = {
            "reporter_id": reporter_id,
            "report_content": report_content,
            "attachment_urls": attachment_urls or None,
            "status": "OPEN",
        }

        def _q():
            res = self._client.table("cases").insert(payload).execute()
            data = getattr(res, "data", None) or []
            if not data or "id" not in data[0]:
                raise RuntimeError("Supabase insert did not return case id.")
            return int(data[0]["id"])

        return await self._run(_q)

    async def attach_case_message_context(
        self,
        case_id: int,
        guild_id: Optional[int],
        staff_channel_id: int,
        staff_message_id: int,
        thread_id: Optional[int],
    ) -> None:
        payload: dict[str, Any] = {
            "guild_id": guild_id,
            "staff_channel_id": staff_channel_id,
            "staff_message_id": staff_message_id,
            "thread_id": thread_id,
        }

        def _q():
            self._client.table("cases").update(payload).eq("id", case_id).execute()

        await self._run(_q)

    async def get_case_by_staff_message_id(self, staff_message_id: int) -> Optional[dict[str, Any]]:
        def _q():
            res = (
                self._client.table("cases")
                .select("*")
                .eq("staff_message_id", staff_message_id)
                .limit(1)
                .execute()
            )
            data = getattr(res, "data", None) or []
            return data[0] if data else None

        return await self._run(_q)

    async def close_case(self, case_id: int) -> None:
        payload = {"status": "CLOSED", "closed_at": datetime.utcnow().isoformat() + "Z"}

        def _q():
            self._client.table("cases").update(payload).eq("id", case_id).execute()

        await self._run(_q)

