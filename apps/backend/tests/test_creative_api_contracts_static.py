from pathlib import Path


def test_creative_router_paths_remain_unchanged_static():
    content = Path("apps/backend/app/api/creative.py").read_text(encoding="utf-8")
    expected_paths = [
        '@router.get("/library/assets")',
        '@router.post("/library/assets")',
        '@router.post("/library/assets/{asset_id}/variants")',
        '@router.post("/ai-generation/assets/{asset_id}/variants")',
        '@router.post("/approvals/assets/{asset_id}")',
        '@router.post("/library/assets/{asset_id}/links")',
        '@router.post("/library/assets/{asset_id}/performance")',
        '@router.post("/publish/assets/{asset_id}/to-channel")',
    ]
    for expected in expected_paths:
        assert expected in content
