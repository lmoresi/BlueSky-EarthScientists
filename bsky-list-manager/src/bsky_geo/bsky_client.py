"""AT Protocol wrapper for Bluesky operations."""

from __future__ import annotations

import time

from atproto import Client, IdResolver
from atproto_client.models.app.bsky.actor.defs import ProfileViewDetailed
from atproto_client.models.app.bsky.graph.list import Record as ListRecord


class RateLimitError(Exception):
    """Raised when we hit a rate limit and need to back off."""


class BskyClient:
    """Wrapper around atproto.Client for list-management operations."""

    def __init__(self, handle: str, app_password: str) -> None:
        self.client = Client()
        self.profile = self.client.login(handle, app_password)
        self.did = self.profile.did
        self._resolver = IdResolver()

    def _handle_rate_limit(self, exc: Exception) -> None:
        """Sleep and retry on rate-limit responses."""
        # atproto raises exceptions with status codes; extract if possible
        msg = str(exc)
        if "429" in msg or "RateLimitExceeded" in msg:
            # Default backoff: 30 seconds
            time.sleep(30)
        else:
            raise exc

    def resolve_handle(self, handle: str) -> str:
        """Resolve a handle to a DID."""
        return self._resolver.handle.resolve(handle)

    def get_profile(self, actor: str) -> dict:
        """Fetch a profile by handle or DID.

        Returns dict with: did, handle, display_name, description (bio).
        """
        resp: ProfileViewDetailed = self.client.app.bsky.actor.get_profile(
            {"actor": actor}
        )
        return {
            "did": resp.did,
            "handle": resp.handle,
            "display_name": resp.display_name or "",
            "description": resp.description or "",
            "avatar": resp.avatar or "",
            "followers_count": resp.followers_count or 0,
            "follows_count": resp.follows_count or 0,
            "posts_count": resp.posts_count or 0,
        }

    def get_profiles(self, actors: list[str]) -> list[dict]:
        """Fetch up to 25 profiles by handle or DID in a single call.

        Returns list of dicts with: did, handle, display_name, description, etc.
        Profiles that fail to resolve are silently omitted.
        """
        resp = self.client.app.bsky.actor.get_profiles({"actors": actors})
        results = []
        for p in resp.profiles:
            results.append({
                "did": p.did,
                "handle": p.handle,
                "display_name": p.display_name or "",
                "description": p.description or "",
                "avatar": p.avatar or "",
                "followers_count": p.followers_count or 0,
                "follows_count": p.follows_count or 0,
                "posts_count": p.posts_count or 0,
            })
        return results

    def get_all_follows(self, actor: str | None = None) -> list[dict]:
        """Get all accounts that `actor` follows (paginated).

        Returns list of dicts with: did, handle, display_name, description.
        """
        actor = actor or self.did
        follows = []
        cursor = None
        while True:
            params = {"actor": actor, "limit": 100}
            if cursor:
                params["cursor"] = cursor
            try:
                resp = self.client.app.bsky.graph.get_follows(params)
            except Exception as exc:
                self._handle_rate_limit(exc)
                continue
            for f in resp.follows:
                follows.append({
                    "did": f.did,
                    "handle": f.handle,
                    "display_name": f.display_name or "",
                    "description": f.description or "",
                })
            cursor = resp.cursor
            if not cursor:
                break
        return follows

    def get_list_members(self, list_uri: str) -> list[dict]:
        """Get all members of a list (paginated).

        Returns list of dicts with: did, handle, display_name, listitem_uri.
        """
        members = []
        cursor = None
        while True:
            params = {"list": list_uri, "limit": 100}
            if cursor:
                params["cursor"] = cursor
            try:
                resp = self.client.app.bsky.graph.get_list(params)
            except Exception as exc:
                self._handle_rate_limit(exc)
                continue
            for item in resp.items:
                members.append({
                    "did": item.subject.did,
                    "handle": item.subject.handle,
                    "display_name": item.subject.display_name or "",
                    "listitem_uri": item.uri,
                })
            cursor = resp.cursor
            if not cursor:
                break
        return members

    def get_lists(self, actor: str | None = None) -> list[dict]:
        """Get all lists owned by actor.

        Returns list of dicts with: uri, name, description, purpose.
        """
        actor = actor or self.did
        lists = []
        cursor = None
        while True:
            params = {"actor": actor, "limit": 50}
            if cursor:
                params["cursor"] = cursor
            try:
                resp = self.client.app.bsky.graph.get_lists(params)
            except Exception as exc:
                self._handle_rate_limit(exc)
                continue
            for lst in resp.lists:
                lists.append({
                    "uri": lst.uri,
                    "name": lst.name,
                    "description": lst.description or "",
                    "purpose": lst.purpose or "",
                })
            cursor = resp.cursor
            if not cursor:
                break
        return lists

    def add_to_list(self, list_uri: str, member_did: str) -> str:
        """Add a member to a list. Returns the listitem record URI."""
        # Parse the list AT-URI to get the rkey
        # list_uri format: at://did:plc:xxx/app.bsky.graph.list/rkey
        resp = self.client.app.bsky.graph.listitem.create(
            self.did,
            {
                "subject": member_did,
                "list": list_uri,
                "createdAt": self.client.get_current_time_iso(),
            },
        )
        return resp.uri

    def remove_from_list(self, listitem_uri: str) -> None:
        """Remove a member from a list by deleting the listitem record.

        listitem_uri format: at://did:plc:xxx/app.bsky.graph.listitem/rkey
        """
        # Parse the AT-URI to extract the rkey
        parts = listitem_uri.split("/")
        rkey = parts[-1]
        self.client.app.bsky.graph.listitem.delete(self.did, rkey)

    def get_author_posts(self, actor: str, limit: int = 50) -> list[str]:
        """Fetch recent post texts from an author.

        Returns list of post text strings.
        """
        posts = []
        cursor = None
        collected = 0
        while collected < limit:
            fetch_limit = min(limit - collected, 50)
            params = {"actor": actor, "limit": fetch_limit}
            if cursor:
                params["cursor"] = cursor
            try:
                resp = self.client.app.bsky.feed.get_author_feed(params)
            except Exception as exc:
                self._handle_rate_limit(exc)
                continue
            for item in resp.feed:
                post = item.post
                if post.record and hasattr(post.record, "text"):
                    posts.append(post.record.text)
                    collected += 1
                    if collected >= limit:
                        break
            cursor = resp.cursor
            if not cursor:
                break
        return posts

    def follow(self, did: str) -> str:
        """Follow an account. Returns the follow record URI."""
        resp = self.client.app.bsky.graph.follow.create(
            self.did,
            {
                "subject": did,
                "createdAt": self.client.get_current_time_iso(),
            },
        )
        return resp.uri

    def get_dm_conversations(self, limit: int = 50) -> list[dict]:
        """Fetch recent DM conversations.

        Requires DM-scoped app password.
        Returns list of dicts with: id, members, last_message.
        """
        try:
            dm_client = self.client.with_bsky_chat_proxy()
            resp = dm_client.chat.bsky.convo.list_convos({"limit": limit})
            convos = []
            for convo in resp.convos:
                members = []
                for m in convo.members:
                    members.append({
                        "did": m.did,
                        "handle": m.handle,
                        "display_name": m.display_name or "",
                    })
                last_msg = ""
                if convo.last_message and hasattr(convo.last_message, "text"):
                    last_msg = convo.last_message.text
                convos.append({
                    "id": convo.id,
                    "members": members,
                    "last_message": last_msg,
                })
            return convos
        except Exception as exc:
            raise RuntimeError(
                f"Failed to access DMs. Ensure your app password has DM access enabled. Error: {exc}"
            ) from exc

    def get_dm_messages(self, convo_id: str, limit: int = 50) -> list[dict]:
        """Fetch messages from a specific DM conversation.

        Returns list of dicts with: sender_did, text, sent_at.
        """
        dm_client = self.client.with_bsky_chat_proxy()
        resp = dm_client.chat.bsky.convo.get_messages(
            {"convo_id": convo_id, "limit": limit}
        )
        messages = []
        for msg in resp.messages:
            if hasattr(msg, "text"):
                messages.append({
                    "sender_did": msg.sender.did if hasattr(msg, "sender") else "",
                    "text": msg.text,
                    "sent_at": msg.sent_at if hasattr(msg, "sent_at") else "",
                })
        return messages
