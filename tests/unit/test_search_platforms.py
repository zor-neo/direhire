from direhire.sources.platforms import (
    SEARCH_PLATFORMS,
    available_platforms,
    platform_as_dict,
    platforms_for_regions,
    resolve_location_regions,
)


def test_search_platform_registry_keys() -> None:
    assert "jobstreet" in SEARCH_PLATFORMS
    assert "jobsdb" in SEARCH_PLATFORMS
    assert "jobthai" in SEARCH_PLATFORMS
    assert SEARCH_PLATFORMS["jobstreet"].adapter_key == "seek_search"
    assert SEARCH_PLATFORMS["jobstreet"].availability == "PAUSED"
    assert SEARCH_PLATFORMS["jobstreet"].search_capable is True


def test_resolve_location_regions() -> None:
    assert resolve_location_regions("Malaysia") == ["MY"]
    assert resolve_location_regions("Kuala Lumpur") == ["MY"]
    assert resolve_location_regions("Bangkok") == ["TH"]
    assert resolve_location_regions("Unknown Location") == []


def test_platforms_for_regions() -> None:
    my_platforms = platforms_for_regions(["MY"])
    keys = [p.key for p in my_platforms]
    assert "jobstreet" in keys
    assert "glassdoor" in keys
    assert "jobthai" not in keys


def test_platform_as_dict() -> None:
    data = platform_as_dict(SEARCH_PLATFORMS["jobstreet"])
    assert data["key"] == "jobstreet"
    assert isinstance(data["regions"], list)
    assert "MY" in data["regions"]


def test_only_operational_platforms_are_available() -> None:
    assert [platform.key for platform in available_platforms()] == ["jobthai"]
