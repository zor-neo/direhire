from types import SimpleNamespace

from direhire.watches.external_search import external_searches_for


def test_external_search_uses_only_target_and_location_in_encoded_links() -> None:
    watch = SimpleNamespace(
        target_terms=["Backend Engineer", "Platform"],
        required_terms=["private-required-term"],
        excluded_terms=["private-excluded-term"],
        locations=["Bangkok"],
    )

    searches = external_searches_for(watch)

    assert [search.key for search in searches] == ["jobsdb-th", "linkedin", "indeed"]
    assert "Backend+Engineer+Platform" in searches[0].url
    assert "Bangkok" in searches[0].url
    assert all("private-required-term" not in search.url for search in searches)
    assert all("private-excluded-term" not in search.url for search in searches)


def test_cambodia_external_searches_include_local_boards() -> None:
    watch = SimpleNamespace(target_terms=["IT Support"], locations=["Phnom Penh"])

    searches = external_searches_for(watch)

    assert [search.key for search in searches[:3]] == [
        "bongthom",
        "jobnet-cambodia",
        "khmer24",
    ]
    assert all(search.url.startswith("https://") for search in searches)


def test_vietnam_external_searches_include_two_active_local_boards() -> None:
    watch = SimpleNamespace(target_terms=["Python Engineer"], locations=["Vietnam"])

    searches = external_searches_for(watch)

    assert [search.key for search in searches[:2]] == ["vietnamworks", "topcv-vietnam"]
    assert "q=Python+Engineer" in searches[0].url
    assert "keyword=Python+Engineer" in searches[1].url


def test_requested_country_markets_get_one_primary_local_search() -> None:
    cases = {
        "Japan": "daijob",
        "Malaysia": "jobstreet-my",
        "Philippines": "jobstreet-ph",
        "Australia": "seek-au",
        "New Zealand": "seek-nz",
        "South Korea": "jobkorea",
        "Taiwan": "104-taiwan",
    }

    for location, expected in cases.items():
        watch = SimpleNamespace(target_terms=["Data Engineer"], locations=[location])
        keys = [search.key for search in external_searches_for(watch)]
        assert expected in keys
