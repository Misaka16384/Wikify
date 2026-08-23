"""What a browser tab calls a page is not what the paper is called.

The extension sends `tab.title` verbatim on purpose — it parses nothing, which
is what keeps it a button rather than a second implementation of the pipeline.
So the rule about what a title looks like lives here, and is pinned here.

Measured on a real click: queueing https://arxiv.org/abs/2410.11942 stored the
title as "[2410.11942] Operator algebra and algorithmic construction…". It is
invisible while rung 1 works, because arXiv's own HTML supplies a proper title
that overwrites it — and it reaches the library unchanged the moment rung 1
misses and a converter with no metadata of its own handles the paper instead.
"""

import pytest

from magi.ingest.enqueue import clean_title


@pytest.mark.parametrize("raw, expected", [
    # the measured case
    ("[2410.11942] Operator algebra and algorithmic construction of boundaries",
     "Operator algebra and algorithmic construction of boundaries"),
    # five-digit identifiers, and versioned ones
    ("[2503.03827v2] Generalized toric codes on twisted tori",
     "Generalized toric codes on twisted tori"),
    ("[arXiv:2401.00506] A paper", "A paper"),
    # the legacy identifier format, which a modern-only rule would miss
    ("[cond-mat/9512169] The Hubbard Model: Introduction",
     "The Hubbard Model: Introduction"),
    ("[hep-th/9711200v3] The Large N Limit", "The Large N Limit"),
    # trailing site names, in the dash forms browsers actually emit
    ("Some Paper - arXiv", "Some Paper"),
    ("Some Paper – arXiv.org", "Some Paper"),
])
def test_browser_noise_is_stripped(raw, expected):
    assert clean_title(raw) == expected


@pytest.mark.parametrize("raw", [
    "Operator algebra and algorithmic construction of boundaries",
    "The Hubbard Model: Introduction and Selected Rigorous Results",
    # A bracketed prefix that is not an identifier is part of the title.
    "[Review] Quantum error correction for beginners",
    # Numbers in the title itself must survive.
    "Bounds on 2410 configurations of the toric code",
])
def test_a_real_title_is_left_alone(raw):
    assert clean_title(raw) == raw


def test_nothing_in_gives_nothing_out():
    assert clean_title(None) is None
    assert clean_title("") is None


def test_a_title_that_is_only_an_identifier_is_kept():
    """Stripping everything would file the paper under no name at all."""
    assert clean_title("[2410.11942]") == "[2410.11942]"


def test_surrounding_whitespace_goes():
    assert clean_title("  [2410.11942]  A paper  ") == "A paper"


def test_the_api_endpoint_cleans_too():
    """The extension is the only caller that sends a browser title, and it
    reaches the ledger through the endpoint rather than the CLI."""
    import inspect

    from magi.ui import api

    src = inspect.getsource(api)
    assert "title=clean_title(req.title)" in src, (
        "the enqueue endpoint must clean the title; the browser path is the "
        "only one that carries browser noise")
