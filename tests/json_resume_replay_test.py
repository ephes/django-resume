import tracemalloc

import pytest

from django_resume.formats.json_resume.export import _same_json


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ({"a": [None, {"x": 7}], "b": True}, {"b": True, "a": [None, {"x": 7}]}, True),
        ({"a": [None, {"x": 7}]}, {"a": [None, {"x": 8}]}, False),
        ([True], [1], False),
        ([1], [1.0], False),
        ([-0.0], [0.0], False),
        ([float("nan")], [float("nan")], False),
        ([float("inf")], [float("inf")], False),
        ([(1,)], [[1]], False),
        ({1: "value"}, {"1": "value"}, False),
        ([object()], [object()], False),
    ],
)
def test_replay_compares_canonical_json(left, right, expected):
    assert _same_json(left, right) is expected


def test_overdeep_legacy_snapshot_is_ineligible_for_replay():
    snapshot = {}
    for _ in range(1500):
        snapshot = {"nested": snapshot}
    assert not _same_json(snapshot, snapshot)


def test_equal_replay_snapshots_avoid_full_serialized_copies():
    left = {"data": ["synthetic" * 128] * 1024}
    right = {"data": left["data"].copy()}

    tracemalloc.start()
    try:
        assert _same_json(left, right)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < 256 * 1024
