from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Literal


Channel = Literal["google", "meta", "tiktok"]


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
        with self._lock:
            asset = CreativeAsset(
                id=self._next_asset_id,
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
            self._next_asset_id += 1

        return self.get_asset(asset.id)

    def list_assets(self, client_id: int | None = None) -> list[dict[str, object]]:
        items = [asset for asset in self._assets.values() if client_id is None or asset.client_id == client_id]
        return [self.get_asset(asset.id) for asset in items]

    def get_asset(self, asset_id: int) -> dict[str, object]:
        asset = self._assets.get(asset_id)
        if asset is None:
            raise ValueError("Asset not found")

        variants = self._variants.get(asset_id, [])
        links = self._links.get(asset_id, [])
        performance_scores = self._performance_scores.get(asset_id, {})

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

    def add_variant(self, asset_id: int, headline: str, body: str, cta: str, media: str) -> dict[str, object]:
        if asset_id not in self._assets:
            raise ValueError("Asset not found")

        with self._lock:
            variant = CreativeVariant(
                id=self._next_variant_id,
                asset_id=asset_id,
                headline=headline,
                body=body,
                cta=cta,
                media=media,
            )
            self._variants.setdefault(asset_id, []).append(variant)
            self._next_variant_id += 1

        return {
            "id": variant.id,
            "asset_id": variant.asset_id,
            "headline": variant.headline,
            "body": variant.body,
            "cta": variant.cta,
            "media": variant.media,
        }

    def generate_variants(self, asset_id: int, count: int = 3) -> list[dict[str, object]]:
        asset = self._assets.get(asset_id)
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
                )
            )
        return generated

    def update_approval(self, asset_id: int, legal_status: str, approval_status: str) -> dict[str, object]:
        asset = self._assets.get(asset_id)
        if asset is None:
            raise ValueError("Asset not found")

        asset.legal_status = legal_status
        asset.approval_status = approval_status
        return self.get_asset(asset_id)

    def link_to_campaign(self, asset_id: int, campaign_id: int, ad_set_id: int) -> dict[str, int]:
        if asset_id not in self._assets:
            raise ValueError("Asset not found")

        with self._lock:
            link = CampaignAdSetLink(
                id=self._next_link_id,
                asset_id=asset_id,
                campaign_id=campaign_id,
                ad_set_id=ad_set_id,
            )
            self._links.setdefault(asset_id, []).append(link)
            self._next_link_id += 1

        return {
            "id": link.id,
            "asset_id": link.asset_id,
            "campaign_id": link.campaign_id,
            "ad_set_id": link.ad_set_id,
        }

    def set_performance_scores(self, asset_id: int, scores: dict[str, float]) -> dict[str, object]:
        if asset_id not in self._assets:
            raise ValueError("Asset not found")

        self._performance_scores[asset_id] = scores
        return self.get_asset(asset_id)

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
