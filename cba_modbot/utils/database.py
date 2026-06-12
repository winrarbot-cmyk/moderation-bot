"""
Database layer – Motor async MongoDB wrapper.
All collections live here; cogs call only these methods.
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen_case_id() -> str:
    """Generate a unique 5-digit numeric case ID string."""
    return str(random.randint(10000, 99999))


class Database:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        # Collections
        self.warnings   = db["warnings"]
        self.cases      = db["cases"]
        self.evidence   = db["evidence"]
        self.reports    = db["reports"]
        self.appeals    = db["appeals"]
        self.queue_bans = db["queue_bans"]
        self.punishments = db["punishments"]   # general timeouts / queue locks

    # ── Indexes ───────────────────────────────────────────────────────────────
    async def create_indexes(self) -> None:
        await self.warnings.create_index("case_id",  unique=True)
        await self.warnings.create_index("user_id")
        await self.warnings.create_index("created_at")
        await self.cases.create_index("case_id",     unique=True)
        await self.evidence.create_index("case_id")
        await self.reports.create_index("case_id",   unique=True)
        await self.reports.create_index("reported_id")
        await self.reports.create_index("created_at")
        await self.appeals.create_index("case_id")
        await self.queue_bans.create_index("user_id")
        await self.punishments.create_index("user_id")
        await self.punishments.create_index("expires_at")

    # ── Case ID helpers ───────────────────────────────────────────────────────
    async def unique_case_id(self) -> str:
        """Return a 5-digit case ID that is not yet used in any collection."""
        for _ in range(100):
            cid = _gen_case_id()
            existing = await self.cases.find_one({"case_id": cid})
            if not existing:
                return cid
        raise RuntimeError("Could not generate a unique case ID after 100 attempts.")

    # ─────────────────────────────────────────────────────────────────────────
    # WARNINGS
    # ─────────────────────────────────────────────────────────────────────────

    async def create_warning(
        self,
        *,
        user_id: int,
        user_name: str,
        mod_id: int,
        mod_name: str,
        reason: str,
        category: str,
        punishment: dict,
        guild_id: int,
        notes: str = "",
        warning_type: str = "queue",   # "queue" | "community"
    ) -> dict:
        case_id = await self.unique_case_id()
        doc = {
            "case_id":       case_id,
            "user_id":       user_id,
            "user_name":     user_name,
            "mod_id":        mod_id,
            "mod_name":      mod_name,
            "reason":        reason,
            "category":      category,
            "punishment":    punishment,   # {"type": ..., "label": ..., "duration_minutes": ...}
            "notes":         notes,
            "warning_type":  warning_type,
            "status":        "Open",
            "guild_id":      guild_id,
            "created_at":    _now(),
            "expires_at":    None,         # set by cog after expiry calculation
            "active":        True,
        }
        await self.warnings.insert_one(doc)
        # Mirror into cases collection
        await self.create_case_from_warning(doc)
        return doc

    async def create_case_from_warning(self, warning: dict) -> None:
        case = {
            "case_id":    warning["case_id"],
            "type":       "warning",
            "user_id":    warning["user_id"],
            "user_name":  warning["user_name"],
            "mod_id":     warning["mod_id"],
            "mod_name":   warning["mod_name"],
            "reason":     warning["reason"],
            "category":   warning["category"],
            "punishment": warning["punishment"],
            "status":     "Open",
            "guild_id":   warning["guild_id"],
            "created_at": warning["created_at"],
            "notes":      [],
            "appeal_ids": [],
        }
        await self.cases.insert_one(case)

    async def get_warnings(self, user_id: int, guild_id: int) -> list[dict]:
        cursor = self.warnings.find(
            {"user_id": user_id, "guild_id": guild_id}
        ).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def get_active_warnings(
        self, user_id: int, guild_id: int, reason: str | None = None
    ) -> list[dict]:
        query: dict = {
            "user_id":  user_id,
            "guild_id": guild_id,
            "active":   True,
        }
        if reason:
            query["reason"] = reason
        cursor = self.warnings.find(query).sort("created_at", 1)
        return await cursor.to_list(length=None)

    async def count_active_warnings_by_reason(
        self, user_id: int, guild_id: int, reason: str
    ) -> int:
        return await self.warnings.count_documents(
            {"user_id": user_id, "guild_id": guild_id, "active": True, "reason": reason}
        )

    async def count_active_community_warnings(self, user_id: int, guild_id: int) -> int:
        return await self.warnings.count_documents(
            {"user_id": user_id, "guild_id": guild_id, "active": True, "warning_type": "community"}
        )

    async def expire_old_warnings(self) -> int:
        """Mark warnings as inactive if their expires_at has passed. Returns count."""
        now = _now()
        result = await self.warnings.update_many(
            {"active": True, "expires_at": {"$lte": now}},
            {"$set": {"active": False}},
        )
        return result.modified_count

    async def set_warning_expiry(self, case_id: str, expires_at: datetime) -> None:
        await self.warnings.update_one(
            {"case_id": case_id},
            {"$set": {"expires_at": expires_at}},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # CASES
    # ─────────────────────────────────────────────────────────────────────────

    async def get_case(self, case_id: str) -> dict | None:
        return await self.cases.find_one({"case_id": case_id})

    async def update_case_status(self, case_id: str, status: str) -> None:
        await self.cases.update_one(
            {"case_id": case_id},
            {"$set": {"status": status, "updated_at": _now()}},
        )

    async def add_case_note(self, case_id: str, mod_id: int, mod_name: str, note: str) -> None:
        note_doc = {
            "mod_id":   mod_id,
            "mod_name": mod_name,
            "note":     note,
            "added_at": _now(),
        }
        await self.cases.update_one(
            {"case_id": case_id},
            {"$push": {"notes": note_doc}},
        )

    async def link_appeal_to_case(self, case_id: str, appeal_id: str) -> None:
        await self.cases.update_one(
            {"case_id": case_id},
            {"$addToSet": {"appeal_ids": appeal_id}},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EVIDENCE
    # ─────────────────────────────────────────────────────────────────────────

    async def add_evidence(
        self,
        *,
        case_id: str,
        mod_id: int,
        mod_name: str,
        link: str = "",
        notes: str = "",
        attachments: list[str] | None = None,
    ) -> dict:
        doc = {
            "case_id":     case_id,
            "mod_id":      mod_id,
            "mod_name":    mod_name,
            "link":        link,
            "notes":       notes,
            "attachments": attachments or [],
            "added_at":    _now(),
        }
        result = await self.evidence.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def get_evidence(self, case_id: str) -> list[dict]:
        cursor = self.evidence.find({"case_id": case_id}).sort("added_at", 1)
        return await cursor.to_list(length=None)

    async def delete_evidence(self, evidence_id: str) -> bool:
        from bson import ObjectId
        result = await self.evidence.delete_one({"_id": ObjectId(evidence_id)})
        return result.deleted_count > 0

    async def get_evidence_by_index(self, case_id: str, index: int) -> dict | None:
        items = await self.get_evidence(case_id)
        if 0 <= index < len(items):
            return items[index]
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # REPORTS
    # ─────────────────────────────────────────────────────────────────────────

    async def create_report(
        self,
        *,
        reporter_id: int,
        reporter_name: str,
        reported_id: int,
        reported_name: str,
        match_id: str,
        description: str,
        evidence_link: str,
        guild_id: int,
    ) -> dict:
        case_id = await self.unique_case_id()
        doc = {
            "case_id":        case_id,
            "type":           "report",
            "reporter_id":    reporter_id,
            "reporter_name":  reporter_name,
            "reported_id":    reported_id,
            "reported_name":  reported_name,
            "match_id":       match_id,
            "description":    description,
            "evidence_link":  evidence_link,
            "status":         "Open",
            "guild_id":       guild_id,
            "created_at":     _now(),
            "notes":          [],
            "appeal_ids":     [],
        }
        await self.reports.insert_one(doc)
        # Also mirror to cases
        await self.cases.insert_one({**doc})
        return doc

    async def get_reports_for_user(self, user_id: int, guild_id: int) -> list[dict]:
        cursor = self.reports.find(
            {"reported_id": user_id, "guild_id": guild_id}
        ).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def count_recent_reports(
        self, user_id: int, guild_id: int, window_days: int
    ) -> int:
        from datetime import timedelta
        since = _now() - timedelta(days=window_days)
        return await self.reports.count_documents({
            "reported_id": user_id,
            "guild_id":    guild_id,
            "created_at":  {"$gte": since},
        })

    async def update_report_status(self, case_id: str, status: str) -> None:
        await self.reports.update_one(
            {"case_id": case_id},
            {"$set": {"status": status, "updated_at": _now()}},
        )
        await self.cases.update_one(
            {"case_id": case_id},
            {"$set": {"status": status, "updated_at": _now()}},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # APPEALS
    # ─────────────────────────────────────────────────────────────────────────

    async def create_appeal(
        self,
        *,
        user_id: int,
        user_name: str,
        case_id: str,
        reason: str,
        additional_info: str,
        guild_id: int,
    ) -> dict:
        appeal_id = await self.unique_case_id()
        doc = {
            "appeal_id":       appeal_id,
            "case_id":         case_id,
            "user_id":         user_id,
            "user_name":       user_name,
            "reason":          reason,
            "additional_info": additional_info,
            "status":          "Pending",
            "guild_id":        guild_id,
            "created_at":      _now(),
            "reviewed_by":     None,
            "reviewed_at":     None,
            "review_note":     None,
        }
        await self.appeals.insert_one(doc)
        await self.link_appeal_to_case(case_id, appeal_id)
        await self.update_case_status(case_id, "Appealed")
        return doc

    async def get_appeal(self, appeal_id: str) -> dict | None:
        return await self.appeals.find_one({"appeal_id": appeal_id})

    async def update_appeal_status(
        self,
        appeal_id: str,
        status: str,
        reviewer_id: int,
        reviewer_name: str,
        review_note: str = "",
    ) -> None:
        await self.appeals.update_one(
            {"appeal_id": appeal_id},
            {"$set": {
                "status":       status,
                "reviewed_by":  reviewer_id,
                "reviewer_name": reviewer_name,
                "reviewed_at":  _now(),
                "review_note":  review_note,
            }},
        )

    async def get_pending_appeals(self, guild_id: int) -> list[dict]:
        cursor = self.appeals.find(
            {"guild_id": guild_id, "status": "Pending"}
        ).sort("created_at", 1)
        return await cursor.to_list(length=None)

    # ─────────────────────────────────────────────────────────────────────────
    # QUEUE BANS
    # ─────────────────────────────────────────────────────────────────────────

    async def create_queue_ban(
        self,
        *,
        user_id: int,
        user_name: str,
        mod_id: int,
        mod_name: str,
        reason: str,
        duration_minutes: int | None,
        case_id: str,
        guild_id: int,
    ) -> dict:
        from datetime import timedelta
        expires_at = (
            _now() + timedelta(minutes=duration_minutes)
            if duration_minutes is not None
            else None
        )
        doc = {
            "case_id":          case_id,
            "user_id":          user_id,
            "user_name":        user_name,
            "mod_id":           mod_id,
            "mod_name":         mod_name,
            "reason":           reason,
            "duration_minutes": duration_minutes,
            "expires_at":       expires_at,
            "active":           True,
            "guild_id":         guild_id,
            "created_at":       _now(),
        }
        await self.queue_bans.insert_one(doc)
        return doc

    async def get_active_queue_ban(self, user_id: int, guild_id: int) -> dict | None:
        return await self.queue_bans.find_one({
            "user_id":  user_id,
            "guild_id": guild_id,
            "active":   True,
        })

    async def deactivate_queue_ban(self, user_id: int, guild_id: int) -> bool:
        result = await self.queue_bans.update_many(
            {"user_id": user_id, "guild_id": guild_id, "active": True},
            {"$set": {"active": False, "removed_at": _now()}},
        )
        return result.modified_count > 0

    async def get_all_active_queue_bans(self, guild_id: int) -> list[dict]:
        cursor = self.queue_bans.find({"guild_id": guild_id, "active": True})
        return await cursor.to_list(length=None)

    # ─────────────────────────────────────────────────────────────────────────
    # PUNISHMENTS (general timeouts + queue locks)
    # ─────────────────────────────────────────────────────────────────────────

    async def create_punishment(
        self,
        *,
        user_id: int,
        user_name: str,
        mod_id: int,
        mod_name: str,
        punishment_type: str,
        reason: str,
        duration_minutes: int | None,
        case_id: str,
        guild_id: int,
    ) -> dict:
        from datetime import timedelta
        expires_at = (
            _now() + timedelta(minutes=duration_minutes)
            if duration_minutes is not None
            else None
        )
        doc = {
            "case_id":          case_id,
            "user_id":          user_id,
            "user_name":        user_name,
            "mod_id":           mod_id,
            "mod_name":         mod_name,
            "type":             punishment_type,
            "reason":           reason,
            "duration_minutes": duration_minutes,
            "expires_at":       expires_at,
            "active":           True,
            "guild_id":         guild_id,
            "created_at":       _now(),
        }
        await self.punishments.insert_one(doc)
        return doc

    async def get_active_punishments(self, user_id: int, guild_id: int) -> list[dict]:
        cursor = self.punishments.find({
            "user_id":  user_id,
            "guild_id": guild_id,
            "active":   True,
        }).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def get_all_punishments(self, user_id: int, guild_id: int) -> list[dict]:
        cursor = self.punishments.find({
            "user_id":  user_id,
            "guild_id": guild_id,
        }).sort("created_at", -1)
        return await cursor.to_list(length=None)

    # ─────────────────────────────────────────────────────────────────────────
    # ESCALATION ALERTS
    # ─────────────────────────────────────────────────────────────────────────

    async def count_recent_warnings_by_reason(
        self,
        user_id: int,
        guild_id: int,
        reason: str,
        window_days: int,
    ) -> int:
        from datetime import timedelta
        since = _now() - timedelta(days=window_days)
        return await self.warnings.count_documents({
            "user_id":    user_id,
            "guild_id":   guild_id,
            "reason":     reason,
            "created_at": {"$gte": since},
        })
