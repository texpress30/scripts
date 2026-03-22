from __future__ import annotations

from dataclasses import dataclass, field
import copy
import logging
from threading import Lock
from typing import Literal

from app.core.config import load_settings
from app.services.creative_assets_repository import creative_assets_repository
from app.services.creative_counters_repository import creative_counters_repository


Channel = Literal["google", "meta", "tiktok"]
logger = logging.getLogger(__name__)


@dataclass
class CreativeAsset:
    id: int
    client_id: int
    name: str
    format: str
    dimensions: str
    objective_fit: str
    platform_fit: list[str]
    language: str
    brand_tags: list[str]
    legal_status: str
    approval_status: str


@dataclass
class CreativeVariant:
    id: int
    asset_id: int
    headline: str
    body: str
    cta: str
    media: str


@dataclass
class CampaignAdSetLink:
    id: int
    asset_id: int
    campaign_id: int
    ad_set_id: int


@dataclass
class PublishedCreative:
    id: int
    asset_id: int
    channel: Channel
    native_id: str
    status: str


class PublishAdapter:
    platform: Channel

    def publish(self, asset: CreativeAsset, variant: CreativeVariant | None) -> str:
        raise NotImplementedError


class GooglePublishAdapter(PublishAdapter):
    platform: Channel = "google"

    def publish(self, asset: CreativeAsset, variant: CreativeVariant | None) -> str:
        suffix = variant.id if variant else "base"
        return f"google_ad_creative_{asset.id}_{suffix}"


class MetaPublishAdapter(PublishAdapter):
    platform: Channel = "meta"

    def publish(self, asset: CreativeAsset, variant: CreativeVariant | None) -> str:
        suffix = variant.id if variant else "base"
        return f"meta_ad_creative_{asset.id}_{suffix}"


class TikTokPublishAdapter(PublishAdapter):
    platform: Channel = "tiktok"

    def publish(self, asset: CreativeAsset, variant: CreativeVariant | None) -> str:
        suffix = variant.id if variant else "base"
        return f"tiktok_ad_creative_{asset.id}_{suffix}"


class CreativeWorkflowService:
    def __init__(self) -> None:
        self._assets: dict[int, CreativeAsset] = {}
        self._variants: dict[int, list[CreativeVariant]] = {}
        self._performance_scores: dict[int, dict[str, float]] = {}
        self._links: dict[int, list[CampaignAdSetLink]] = {}
        self._published: dict[int, PublishedCreative] = {}

        self._next_asset_id = 1
        self._next_variant_id = 1
        self._next_link_id = 1
        self._next_publish_id = 1

        self._lock = Lock()
        self._adapters: dict[Channel, PublishAdapter] = {
            "google": GooglePublishAdapter(),
            "meta": MetaPublishAdapter(),
            "tiktok": TikTokPublishAdapter(),
        }

    def _mongo_shadow_write_enabled(self) -> bool:
        try:
            settings = load_settings()
        except Exception:  # noqa: BLE001
            return False
        return bool(getattr(settings, "creative_workflow_mongo_shadow_write_enabled", False))

    def _mongo_read_through_enabled(self) -> bool:
        try:
            settings = load_settings()
        except Exception:  # noqa: BLE001
            return False
        return bool(getattr(settings, "creative_workflow_mongo_read_through_enabled", False))

    def _mongo_reads_source_enabled(self) -> bool:
        try:
            settings = load_settings()
        except Exception:  # noqa: BLE001
            return False
        return bool(getattr(settings, "creative_workflow_mongo_reads_source_enabled", False))

    def _mongo_core_writes_source_enabled(self) -> bool:
        try:
            settings = load_settings()
        except Exception:  # noqa: BLE001
            return False
        return bool(getattr(settings, "creative_workflow_mongo_core_writes_source_enabled", False))

    def _mongo_derived_writes_requested_enabled(self) -> bool:
        try:
            settings = load_settings()
        except Exception:  # noqa: BLE001
            return False
        return bool(getattr(settings, "creative_workflow_mongo_derived_writes_source_enabled", False))

    def _mongo_derived_writes_source_enabled(self) -> bool:
        if not self._mongo_derived_writes_requested_enabled():
            return False
        if not self._mongo_core_writes_source_enabled():
            logger.info("creative_workflow.derived_write_ignored_missing_core_writes")
            return False
        return True

    def _sync_local_counter(self, *, counter_name: str, allocated_id: int) -> None:
        next_value = max(1, int(allocated_id) + 1)
        if counter_name == "asset":
            self._next_asset_id = max(int(self._next_asset_id), next_value)
        elif counter_name == "variant":
            self._next_variant_id = max(int(self._next_variant_id), next_value)
        elif counter_name == "link":
            self._next_link_id = max(int(self._next_link_id), next_value)

    def _next_id_for_counter(self, *, counter_name: str) -> int:
        if not self._mongo_shadow_write_enabled():
            logger.info("creative_workflow.shadow_write_disabled operation=next_id counter=%s", counter_name)
            if counter_name == "asset":
                value = int(self._next_asset_id)
                self._next_asset_id += 1
                return value
            if counter_name == "variant":
                value = int(self._next_variant_id)
                self._next_variant_id += 1
                return value
            if counter_name == "link":
                value = int(self._next_link_id)
                self._next_link_id += 1
                return value
            raise ValueError(f"Unsupported counter_name: {counter_name}")

        try:
            if counter_name == "asset":
                value = int(creative_counters_repository.next_asset_id())
            elif counter_name == "variant":
                value = int(creative_counters_repository.next_variant_id())
            elif counter_name == "link":
                value = int(creative_counters_repository.next_link_id())
            else:
                raise ValueError(f"Unsupported counter_name: {counter_name}")
            self._sync_local_counter(counter_name=counter_name, allocated_id=value)
            return value
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "creative_workflow.shadow_counter_failed counter=%s error=%s",
                counter_name,
                exc.__class__.__name__,
            )
            if counter_name == "asset":
                value = int(self._next_asset_id)
                self._next_asset_id += 1
                return value
            if counter_name == "variant":
                value = int(self._next_variant_id)
                self._next_variant_id += 1
                return value
            value = int(self._next_link_id)
            self._next_link_id += 1
            return value

    def _asset_payload_from_local(self, *, asset_id: int) -> dict[str, object]:
        asset = self._assets.get(int(asset_id))
        if asset is None:
            raise ValueError("Asset not found")
        variants = self._variants.get(int(asset_id), [])
        links = self._links.get(int(asset_id), [])
        performance_scores = self._performance_scores.get(int(asset_id), {})
        return {
            "id": asset.id,
            "client_id": asset.client_id,
            "name": asset.name,
            "metadata": {
                "format": asset.format,
                "dimensions": asset.dimensions,
                "objective_fit": asset.objective_fit,
                "platform_fit": asset.platform_fit,
                "language": asset.language,
                "brand_tags": asset.brand_tags,
                "legal_status": asset.legal_status,
                "approval_status": asset.approval_status,
            },
            "creative_variants": [
                {
                    "id": variant.id,
                    "headline": variant.headline,
                    "body": variant.body,
                    "cta": variant.cta,
                    "media": variant.media,
                }
                for variant in variants
            ],
            "performance_scores": performance_scores,
            "campaign_links": [
                {
                    "id": link.id,
                    "campaign_id": link.campaign_id,
                    "ad_set_id": link.ad_set_id,
                }
                for link in links
            ],
        }

    def _build_asset_snapshot(
        self,
        *,
        asset_id: int,
        client_id: int,
        name: str,
        format: str,
        dimensions: str,
        objective_fit: str,
        platform_fit: list[str],
        language: str,
        brand_tags: list[str],
        legal_status: str,
        approval_status: str,
        creative_variants: list[dict[str, object]] | None = None,
        performance_scores: dict[str, float] | None = None,
        campaign_links: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        return {
            "id": int(asset_id),
            "creative_id": int(asset_id),
            "asset_id": int(asset_id),
            "client_id": int(client_id),
            "name": name,
            "metadata": {
                "format": format,
                "dimensions": dimensions,
                "objective_fit": objective_fit,
                "platform_fit": list(platform_fit),
                "language": language,
                "brand_tags": list(brand_tags),
                "legal_status": legal_status,
                "approval_status": approval_status,
            },
            "creative_variants": list(creative_variants or []),
            "performance_scores": dict(performance_scores or {}),
            "campaign_links": list(campaign_links or []),
        }

    def _resolve_asset_snapshot_for_write(self, *, asset_id: int, operation: str) -> dict[str, object] | None:
        try:
            payload = creative_assets_repository.get_by_creative_id(int(asset_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "creative_workflow.core_write_mongo_read_failed operation=%s asset_id=%s error=%s",
                operation,
                asset_id,
                exc.__class__.__name__,
            )
            payload = None

        if isinstance(payload, dict):
            return copy.deepcopy(payload)

        logger.info("creative_workflow.core_write_mongo_miss_fallback_local operation=%s asset_id=%s", operation, asset_id)
        local_asset = self._assets.get(int(asset_id))
        if local_asset is None:
            return None
        return copy.deepcopy(self._asset_payload_from_local(asset_id=int(asset_id)))

    def _resolve_asset_snapshot_for_derived_write(self, *, asset_id: int, operation: str) -> dict[str, object] | None:
        try:
            payload = creative_assets_repository.get_by_creative_id(int(asset_id))
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "creative_workflow.derived_write_mongo_read_failed operation=%s asset_id=%s error=%s",
                operation,
                asset_id,
                exc.__class__.__name__,
            )
            raise

        if isinstance(payload, dict):
            return copy.deepcopy(payload)

        local_asset = self._assets.get(int(asset_id))
        if local_asset is None:
            return None
        logger.info("creative_workflow.derived_write_mongo_miss_fallback_local operation=%s asset_id=%s", operation, asset_id)
        return copy.deepcopy(self._asset_payload_from_local(asset_id=int(asset_id)))

    def _hydrate_local_cache_after_persist(self, *, persisted_snapshot: dict[str, object], operation: str) -> CreativeAsset:
        hydrated = self._hydrate_asset_from_document(persisted_snapshot, overwrite_existing=True)
        if hydrated is None:
            raise RuntimeError(f"Failed to hydrate local cache after {operation}")
        return hydrated

    def _next_id_for_core_write(self, *, counter_name: str) -> int:
        if counter_name == "asset":
            value = int(creative_counters_repository.next_asset_id())
        elif counter_name == "variant":
            value = int(creative_counters_repository.next_variant_id())
        elif counter_name == "link":
            value = int(creative_counters_repository.next_link_id())
        else:
            raise ValueError(f"Unsupported counter_name: {counter_name}")
        self._sync_local_counter(counter_name=counter_name, allocated_id=value)
        return value

    def _shadow_upsert_asset(self, *, asset_id: int, operation: str) -> None:
        if not self._mongo_shadow_write_enabled():
            logger.info("creative_workflow.shadow_write_disabled operation=%s asset_id=%s", operation, asset_id)
            return
        try:
            snapshot = self._asset_payload_from_local(asset_id=int(asset_id))
            creative_assets_repository.upsert_asset(snapshot)
            logger.info("creative_workflow.shadow_write_success operation=%s asset_id=%s", operation, asset_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "creative_workflow.shadow_write_failed operation=%s asset_id=%s error=%s",
                operation,
                asset_id,
                exc.__class__.__name__,
            )

    def _hydrate_asset_from_document(self, payload: dict[str, object], *, overwrite_existing: bool = False) -> CreativeAsset | None:
        try:
            asset_id = int(payload.get("id") or payload.get("creative_id") or payload.get("asset_id") or 0)
        except Exception:  # noqa: BLE001
            asset_id = 0
        if asset_id <= 0:
            return None
        if asset_id in self._assets and not overwrite_existing:
            return self._assets.get(asset_id)

        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        creative_variants = payload.get("creative_variants") if isinstance(payload.get("creative_variants"), list) else []
        performance_scores = payload.get("performance_scores") if isinstance(payload.get("performance_scores"), dict) else {}
        campaign_links = payload.get("campaign_links") if isinstance(payload.get("campaign_links"), list) else []

        try:
            asset = CreativeAsset(
                id=asset_id,
                client_id=int(payload.get("client_id") or 0),
                name=str(payload.get("name") or ""),
                format=str(metadata.get("format") or ""),
                dimensions=str(metadata.get("dimensions") or ""),
                objective_fit=str(metadata.get("objective_fit") or ""),
                platform_fit=[str(item) for item in list(metadata.get("platform_fit") or [])],
                language=str(metadata.get("language") or ""),
                brand_tags=[str(item) for item in list(metadata.get("brand_tags") or [])],
                legal_status=str(metadata.get("legal_status") or ""),
                approval_status=str(metadata.get("approval_status") or ""),
            )
        except Exception:  # noqa: BLE001
            return None

        variants: list[CreativeVariant] = []
        for item in creative_variants:
            if not isinstance(item, dict):
                continue
            variant_id = int(item.get("id") or 0)
            if variant_id <= 0:
                continue
            variants.append(
                CreativeVariant(
                    id=variant_id,
                    asset_id=asset_id,
                    headline=str(item.get("headline") or ""),
                    body=str(item.get("body") or ""),
                    cta=str(item.get("cta") or ""),
                    media=str(item.get("media") or ""),
                )
            )

        links: list[CampaignAdSetLink] = []
        for item in campaign_links:
            if not isinstance(item, dict):
                continue
            link_id = int(item.get("id") or 0)
            if link_id <= 0:
                continue
            links.append(
                CampaignAdSetLink(
                    id=link_id,
                    asset_id=asset_id,
                    campaign_id=int(item.get("campaign_id") or 0),
                    ad_set_id=int(item.get("ad_set_id") or 0),
                )
            )

        self._assets[asset_id] = asset
        self._variants[asset_id] = variants
        self._performance_scores[asset_id] = {str(key): float(value) for key, value in performance_scores.items()}
        self._links[asset_id] = links

        self._sync_local_counter(counter_name="asset", allocated_id=asset_id)
        if len(variants) > 0:
            self._sync_local_counter(counter_name="variant", allocated_id=max(item.id for item in variants))
        if len(links) > 0:
            self._sync_local_counter(counter_name="link", allocated_id=max(item.id for item in links))
        return asset

    def _resolve_asset_local_or_mongo(self, *, asset_id: int, operation: str) -> CreativeAsset | None:
        local_asset = self._assets.get(int(asset_id))
        if local_asset is not None:
            return local_asset
        if not self._mongo_read_through_enabled():
            logger.info("creative_workflow.read_through_disabled operation=%s asset_id=%s", operation, asset_id)
            return None
        try:
            payload = creative_assets_repository.get_by_creative_id(int(asset_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "creative_workflow.read_through_failed operation=%s asset_id=%s error=%s",
                operation,
                asset_id,
                exc.__class__.__name__,
            )
            return None
        if not isinstance(payload, dict):
            return None
        hydrated = self._hydrate_asset_from_document(payload)
        if hydrated is not None:
            logger.info("creative_workflow.read_through_hydrated operation=%s asset_id=%s", operation, asset_id)
        return hydrated

    def _resolve_asset_mongo_first(self, *, asset_id: int, operation: str) -> CreativeAsset | None:
        try:
            payload = creative_assets_repository.get_by_creative_id(int(asset_id))
            if isinstance(payload, dict):
                hydrated = self._hydrate_asset_from_document(payload, overwrite_existing=True)
                if hydrated is not None:
                    logger.info("creative_workflow.mongo_first_hit operation=%s asset_id=%s", operation, asset_id)
                    return hydrated
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "creative_workflow.mongo_first_failed operation=%s asset_id=%s error=%s",
                operation,
                asset_id,
                exc.__class__.__name__,
            )
        return self._assets.get(int(asset_id))

    def create_asset(
        self,
        client_id: int,
        name: str,
        format: str,
        dimensions: str,
        objective_fit: str,
        platform_fit: list[str],
        language: str,
        brand_tags: list[str],
        legal_status: str,
        approval_status: str,
    ) -> dict[str, object]:
        if self._mongo_core_writes_source_enabled():
            with self._lock:
                asset_id = self._next_id_for_core_write(counter_name="asset")
                snapshot = self._build_asset_snapshot(
                    asset_id=asset_id,
                    client_id=client_id,
                    name=name,
                    format=format,
                    dimensions=dimensions,
                    objective_fit=objective_fit,
                    platform_fit=platform_fit,
                    language=language,
                    brand_tags=brand_tags,
                    legal_status=legal_status,
                    approval_status=approval_status,
                )
                try:
                    persisted = creative_assets_repository.upsert_asset(snapshot)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "creative_workflow.core_write_failed operation=create_asset asset_id=%s error=%s",
                        asset_id,
                        exc.__class__.__name__,
                    )
                    raise
                persisted_snapshot = dict(persisted) if isinstance(persisted, dict) and len(persisted) > 0 else snapshot
                hydrated = self._hydrate_local_cache_after_persist(
                    persisted_snapshot=persisted_snapshot,
                    operation="create_asset",
                )
                return self._asset_payload_from_local(asset_id=hydrated.id)

        with self._lock:
            asset_id = self._next_id_for_counter(counter_name="asset")
            asset = CreativeAsset(
                id=asset_id,
                client_id=client_id,
                name=name,
                format=format,
                dimensions=dimensions,
                objective_fit=objective_fit,
                platform_fit=platform_fit,
                language=language,
                brand_tags=brand_tags,
                legal_status=legal_status,
                approval_status=approval_status,
            )
            self._assets[asset.id] = asset
            self._variants.setdefault(asset.id, [])
            self._performance_scores.setdefault(asset.id, {})
            self._links.setdefault(asset.id, [])

        payload = self._asset_payload_from_local(asset_id=asset.id)
        self._shadow_upsert_asset(asset_id=asset.id, operation="create_asset")
        return payload

    def list_assets(self, client_id: int | None = None) -> list[dict[str, object]]:
        if self._mongo_reads_source_enabled():
            mongo_ids_seen: set[int] = set()
            mongo_ids_ordered: list[int] = []
            try:
                mongo_items = creative_assets_repository.list_assets(limit=1000, client_id=client_id)
                for payload in mongo_items:
                    if not isinstance(payload, dict):
                        continue
                    hydrated = self._hydrate_asset_from_document(payload, overwrite_existing=True)
                    if hydrated is not None:
                        hydrated_id = int(hydrated.id)
                        if hydrated_id not in mongo_ids_seen:
                            mongo_ids_seen.add(hydrated_id)
                            mongo_ids_ordered.append(hydrated_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("creative_workflow.mongo_first_list_failed error=%s", exc.__class__.__name__)
                items = [asset for asset in self._assets.values() if client_id is None or asset.client_id == client_id]
                return [self._asset_payload_from_local(asset_id=asset.id) for asset in items]

            local_items = [asset for asset in self._assets.values() if client_id is None or asset.client_id == client_id]
            ordered_ids: list[int] = list(mongo_ids_ordered)
            ordered_ids.extend(int(asset.id) for asset in local_items if int(asset.id) not in mongo_ids_seen)
            return [self._asset_payload_from_local(asset_id=asset_id) for asset_id in ordered_ids]

        if self._mongo_read_through_enabled():
            try:
                mongo_items = creative_assets_repository.list_assets(limit=1000, client_id=client_id)
                for payload in mongo_items:
                    if not isinstance(payload, dict):
                        continue
                    asset_id = int(payload.get("id") or payload.get("creative_id") or payload.get("asset_id") or 0)
                    if asset_id <= 0 or asset_id in self._assets:
                        continue
                    self._hydrate_asset_from_document(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("creative_workflow.list_read_through_failed error=%s", exc.__class__.__name__)
        items = [asset for asset in self._assets.values() if client_id is None or asset.client_id == client_id]
        return [self.get_asset(asset.id) for asset in items]

    def get_asset(self, asset_id: int) -> dict[str, object]:
        asset = (
            self._resolve_asset_mongo_first(asset_id=asset_id, operation="get_asset")
            if self._mongo_reads_source_enabled()
            else self._resolve_asset_local_or_mongo(asset_id=asset_id, operation="get_asset")
        )
        if asset is None:
            raise ValueError("Asset not found")
        return self._asset_payload_from_local(asset_id=asset.id)

    def add_variant(
        self,
        asset_id: int,
        headline: str,
        body: str,
        cta: str,
        media: str,
        *,
        _shadow_persist: bool = True,
        _force_local_write_path: bool = False,
    ) -> dict[str, object]:
        if self._mongo_core_writes_source_enabled() and not _force_local_write_path:
            with self._lock:
                snapshot = self._resolve_asset_snapshot_for_write(asset_id=asset_id, operation="add_variant")
                if snapshot is None:
                    raise ValueError("Asset not found")
                variant_id = self._next_id_for_core_write(counter_name="variant")
                resolved_asset_id = int(snapshot.get("id") or snapshot.get("creative_id") or snapshot.get("asset_id") or asset_id)
                variants = [
                    dict(item)
                    for item in list(snapshot.get("creative_variants") or [])
                    if isinstance(item, dict)
                ]
                variant_payload = {
                    "id": variant_id,
                    "headline": headline,
                    "body": body,
                    "cta": cta,
                    "media": media,
                }
                variants.append(variant_payload)
                snapshot["creative_variants"] = variants
                snapshot["id"] = resolved_asset_id
                snapshot["creative_id"] = resolved_asset_id
                snapshot["asset_id"] = resolved_asset_id
                try:
                    persisted = creative_assets_repository.upsert_asset(snapshot)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "creative_workflow.core_write_failed operation=add_variant asset_id=%s error=%s",
                        resolved_asset_id,
                        exc.__class__.__name__,
                    )
                    raise
                persisted_snapshot = dict(persisted) if isinstance(persisted, dict) and len(persisted) > 0 else snapshot
                hydrated = self._hydrate_local_cache_after_persist(
                    persisted_snapshot=persisted_snapshot,
                    operation="add_variant",
                )
                return {
                    "id": variant_id,
                    "asset_id": hydrated.id,
                    "headline": headline,
                    "body": body,
                    "cta": cta,
                    "media": media,
                }

        asset = self._resolve_asset_local_or_mongo(asset_id=asset_id, operation="add_variant")
        if asset is None:
            raise ValueError("Asset not found")

        with self._lock:
            variant = CreativeVariant(
                id=self._next_id_for_counter(counter_name="variant"),
                asset_id=asset.id,
                headline=headline,
                body=body,
                cta=cta,
                media=media,
            )
            self._variants.setdefault(asset.id, []).append(variant)

        payload = {
            "id": variant.id,
            "asset_id": variant.asset_id,
            "headline": variant.headline,
            "body": variant.body,
            "cta": variant.cta,
            "media": variant.media,
        }
        if _shadow_persist:
            self._shadow_upsert_asset(asset_id=asset.id, operation="add_variant")
        return payload

    def generate_variants(self, asset_id: int, count: int = 3) -> list[dict[str, object]]:
        if self._mongo_derived_writes_source_enabled():
            with self._lock:
                snapshot = self._resolve_asset_snapshot_for_derived_write(asset_id=asset_id, operation="generate_variants")
                if snapshot is None:
                    raise ValueError("Asset not found")
                resolved_asset_id = int(snapshot.get("id") or snapshot.get("creative_id") or snapshot.get("asset_id") or asset_id)
                metadata = snapshot.get("metadata") if isinstance(snapshot.get("metadata"), dict) else {}
                name = str(snapshot.get("name") or "")
                objective_fit = str(metadata.get("objective_fit") or "")
                platform_fit = [str(item) for item in list(metadata.get("platform_fit") or [])]
                format_value = str(metadata.get("format") or "")
                variants = [dict(item) for item in list(snapshot.get("creative_variants") or []) if isinstance(item, dict)]
                generated: list[dict[str, object]] = []
                for index in range(1, count + 1):
                    variant_id = self._next_id_for_core_write(counter_name="variant")
                    variant_payload = {
                        "id": variant_id,
                        "headline": f"{name} — Hook {index}",
                        "body": f"Variante AI pentru {objective_fit} pe {', '.join(platform_fit)}.",
                        "cta": "Afla mai mult",
                        "media": f"{format_value}_variant_{index}",
                    }
                    variants.append(variant_payload)
                    generated.append(
                        {
                            "id": variant_id,
                            "asset_id": resolved_asset_id,
                            "headline": str(variant_payload["headline"]),
                            "body": str(variant_payload["body"]),
                            "cta": str(variant_payload["cta"]),
                            "media": str(variant_payload["media"]),
                        }
                    )
                snapshot["creative_variants"] = variants
                snapshot["id"] = resolved_asset_id
                snapshot["creative_id"] = resolved_asset_id
                snapshot["asset_id"] = resolved_asset_id
                try:
                    persisted = creative_assets_repository.upsert_asset(snapshot)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "creative_workflow.derived_write_failed operation=generate_variants asset_id=%s error=%s",
                        resolved_asset_id,
                        exc.__class__.__name__,
                    )
                    raise
                persisted_snapshot = dict(persisted) if isinstance(persisted, dict) and len(persisted) > 0 else snapshot
                self._hydrate_local_cache_after_persist(
                    persisted_snapshot=persisted_snapshot,
                    operation="generate_variants",
                )
                return generated

        asset = self._resolve_asset_local_or_mongo(asset_id=asset_id, operation="generate_variants")
        if asset is None:
            raise ValueError("Asset not found")

        generated: list[dict[str, object]] = []
        for index in range(1, count + 1):
            generated.append(
                self.add_variant(
                    asset_id=asset_id,
                    headline=f"{asset.name} — Hook {index}",
                    body=f"Variante AI pentru {asset.objective_fit} pe {', '.join(asset.platform_fit)}.",
                    cta="Afla mai mult",
                    media=f"{asset.format}_variant_{index}",
                    _shadow_persist=False,
                    _force_local_write_path=True,
                )
            )
        self._shadow_upsert_asset(asset_id=asset_id, operation="generate_variants")
        return generated

    def update_approval(self, asset_id: int, legal_status: str, approval_status: str) -> dict[str, object]:
        if self._mongo_derived_writes_source_enabled():
            with self._lock:
                snapshot = self._resolve_asset_snapshot_for_derived_write(asset_id=asset_id, operation="update_approval")
                if snapshot is None:
                    raise ValueError("Asset not found")
                resolved_asset_id = int(snapshot.get("id") or snapshot.get("creative_id") or snapshot.get("asset_id") or asset_id)
                metadata = dict(snapshot.get("metadata") or {})
                metadata["legal_status"] = legal_status
                metadata["approval_status"] = approval_status
                snapshot["metadata"] = metadata
                snapshot["id"] = resolved_asset_id
                snapshot["creative_id"] = resolved_asset_id
                snapshot["asset_id"] = resolved_asset_id
                try:
                    persisted = creative_assets_repository.upsert_asset(snapshot)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "creative_workflow.derived_write_failed operation=update_approval asset_id=%s error=%s",
                        resolved_asset_id,
                        exc.__class__.__name__,
                    )
                    raise
                persisted_snapshot = dict(persisted) if isinstance(persisted, dict) and len(persisted) > 0 else snapshot
                hydrated = self._hydrate_local_cache_after_persist(
                    persisted_snapshot=persisted_snapshot,
                    operation="update_approval",
                )
                return self._asset_payload_from_local(asset_id=hydrated.id)

        asset = self._resolve_asset_local_or_mongo(asset_id=asset_id, operation="update_approval")
        if asset is None:
            raise ValueError("Asset not found")

        asset.legal_status = legal_status
        asset.approval_status = approval_status
        payload = self._asset_payload_from_local(asset_id=asset_id)
        self._shadow_upsert_asset(asset_id=asset_id, operation="update_approval")
        return payload

    def link_to_campaign(self, asset_id: int, campaign_id: int, ad_set_id: int) -> dict[str, int]:
        if self._mongo_core_writes_source_enabled():
            with self._lock:
                snapshot = self._resolve_asset_snapshot_for_write(asset_id=asset_id, operation="link_to_campaign")
                if snapshot is None:
                    raise ValueError("Asset not found")
                link_id = self._next_id_for_core_write(counter_name="link")
                resolved_asset_id = int(snapshot.get("id") or snapshot.get("creative_id") or snapshot.get("asset_id") or asset_id)
                links = [
                    dict(item)
                    for item in list(snapshot.get("campaign_links") or [])
                    if isinstance(item, dict)
                ]
                links.append(
                    {
                        "id": link_id,
                        "campaign_id": int(campaign_id),
                        "ad_set_id": int(ad_set_id),
                    }
                )
                snapshot["campaign_links"] = links
                snapshot["id"] = resolved_asset_id
                snapshot["creative_id"] = resolved_asset_id
                snapshot["asset_id"] = resolved_asset_id
                try:
                    persisted = creative_assets_repository.upsert_asset(snapshot)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "creative_workflow.core_write_failed operation=link_to_campaign asset_id=%s error=%s",
                        resolved_asset_id,
                        exc.__class__.__name__,
                    )
                    raise
                persisted_snapshot = dict(persisted) if isinstance(persisted, dict) and len(persisted) > 0 else snapshot
                hydrated = self._hydrate_local_cache_after_persist(
                    persisted_snapshot=persisted_snapshot,
                    operation="link_to_campaign",
                )
                return {
                    "id": link_id,
                    "asset_id": hydrated.id,
                    "campaign_id": int(campaign_id),
                    "ad_set_id": int(ad_set_id),
                }

        asset = self._resolve_asset_local_or_mongo(asset_id=asset_id, operation="link_to_campaign")
        if asset is None:
            raise ValueError("Asset not found")

        with self._lock:
            link = CampaignAdSetLink(
                id=self._next_id_for_counter(counter_name="link"),
                asset_id=asset.id,
                campaign_id=campaign_id,
                ad_set_id=ad_set_id,
            )
            self._links.setdefault(asset.id, []).append(link)

        payload = {
            "id": link.id,
            "asset_id": link.asset_id,
            "campaign_id": link.campaign_id,
            "ad_set_id": link.ad_set_id,
        }
        self._shadow_upsert_asset(asset_id=asset.id, operation="link_to_campaign")
        return payload

    def set_performance_scores(self, asset_id: int, scores: dict[str, float]) -> dict[str, object]:
        if self._mongo_derived_writes_source_enabled():
            with self._lock:
                snapshot = self._resolve_asset_snapshot_for_derived_write(asset_id=asset_id, operation="set_performance_scores")
                if snapshot is None:
                    raise ValueError("Asset not found")
                resolved_asset_id = int(snapshot.get("id") or snapshot.get("creative_id") or snapshot.get("asset_id") or asset_id)
                snapshot["performance_scores"] = dict(scores)
                snapshot["id"] = resolved_asset_id
                snapshot["creative_id"] = resolved_asset_id
                snapshot["asset_id"] = resolved_asset_id
                try:
                    persisted = creative_assets_repository.upsert_asset(snapshot)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "creative_workflow.derived_write_failed operation=set_performance_scores asset_id=%s error=%s",
                        resolved_asset_id,
                        exc.__class__.__name__,
                    )
                    raise
                persisted_snapshot = dict(persisted) if isinstance(persisted, dict) and len(persisted) > 0 else snapshot
                hydrated = self._hydrate_local_cache_after_persist(
                    persisted_snapshot=persisted_snapshot,
                    operation="set_performance_scores",
                )
                return self._asset_payload_from_local(asset_id=hydrated.id)

        asset = self._resolve_asset_local_or_mongo(asset_id=asset_id, operation="set_performance_scores")
        if asset is None:
            raise ValueError("Asset not found")

        self._performance_scores[asset.id] = scores
        payload = self._asset_payload_from_local(asset_id=asset.id)
        self._shadow_upsert_asset(asset_id=asset.id, operation="set_performance_scores")
        return payload

    def publish_to_channel(self, asset_id: int, channel: Channel, variant_id: int | None = None) -> dict[str, object]:
        asset = self._assets.get(asset_id)
        if asset is None:
            raise ValueError("Asset not found")
        if channel not in self._adapters:
            raise ValueError("Unsupported channel")

        variant = None
        if variant_id is not None:
            variant = next((item for item in self._variants.get(asset_id, []) if item.id == variant_id), None)
            if variant is None:
                raise ValueError("Variant not found")

        native_id = self._adapters[channel].publish(asset, variant)
        with self._lock:
            published = PublishedCreative(
                id=self._next_publish_id,
                asset_id=asset_id,
                channel=channel,
                native_id=native_id,
                status="published",
            )
            self._published[published.id] = published
            self._next_publish_id += 1

        return {
            "id": published.id,
            "asset_id": published.asset_id,
            "channel": published.channel,
            "native_object_type": "ad_creative",
            "native_id": published.native_id,
            "status": published.status,
        }

    def reset(self) -> None:
        self._assets.clear()
        self._variants.clear()
        self._performance_scores.clear()
        self._links.clear()
        self._published.clear()
        self._next_asset_id = 1
        self._next_variant_id = 1
        self._next_link_id = 1
        self._next_publish_id = 1


creative_workflow_service = CreativeWorkflowService()
