import pytest


@pytest.fixture(scope="module")
def vcr_config():
    # ORS sends its key as an Authorization header (app/services/route_generator.py's
    # _get_client()); strip it from recorded cassettes so they're safe to commit.
    #
    # match_on adds "body" to VCR's default matcher (method/scheme/host/port/path/query).
    # route_generator.py fires several concurrent POSTs to the *same* ORS endpoint
    # (different route variants -- recommended/shortest/avoid-tollways/alternative_routes,
    # plus separate land legs for each port-pair candidate) that only differ by JSON body.
    # Without body-matching, VCR can't tell these apart and misattributes responses
    # between threads depending on whatever order they happen to replay in.
    return {
        "filter_headers": ["authorization"],
        "match_on": ["method", "scheme", "host", "port", "path", "query", "body"],
    }
