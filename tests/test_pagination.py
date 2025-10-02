from __future__ import annotations

import pytest

from core.pagination import parse_page_params, paginate_sequence, PageRequest


def test_pagination_defaults():
    req = parse_page_params({})
    assert req["page"] == 1
    assert req["size"] == 20


def test_pagination_custom_params():
    req = parse_page_params({"page": "2", "size": "5"})
    assert req["page"] == 2
    assert req["size"] == 5


def test_pagination_caps():
    req = parse_page_params({"page": "1", "size": "500"})
    assert req["size"] == 100  # capped


def test_pagination_invalid_size():
    with pytest.raises(ValueError):
        parse_page_params({"size": "0"})


def test_pagination_invalid_page():
    with pytest.raises(ValueError):
        parse_page_params({"page": "0"})


def test_paginate_sequence_meta():
    data = list(range(1, 51))  # 50 items
    req = PageRequest(page=2, size=10, sort=None, order="asc")  # type: ignore[arg-type]
    page = paginate_sequence(data, req)
    assert page["meta"]["page"] == 2
    assert page["meta"]["pages"] == 5
    assert page["items"] == list(range(11, 21))
