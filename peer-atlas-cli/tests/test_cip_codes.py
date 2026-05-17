"""Verify every CIP code in the curated set maps to an approved 4-digit group code."""

from __future__ import annotations

import json

from peer_atlas_cli.repo_root import find_repo_root

# Approved 4-digit group codes (XX.XX without decimal, as integer).
# Each 6-digit code XX.XXXX is valid when int(XX + XX[:2]) is in this set.
_APPROVED_GROUPS: frozenset[int] = frozenset(
    {
        5109, 5107, 5122, 5123, 5102, 1306, 5100, 5104, 5112, 5203, 4228, 1304,
        5115, 3099, 4407, 5133, 402, 901, 1108, 5004, 1513, 5005, 5006, 5007,
        1003, 904, 5009, 909, 5001, 5202, 1312, 1313, 1301, 3105, 5127, 4201,
        5138, 1310, 1314, 4405, 2601, 403, 1101, 1901, 110, 4499, 5120, 2201,
        4301, 4404, 4400, 3201, 1311, 5210, 4227, 2401, 1303, 1305, 3906, 1110,
        5401, 4303, 4509, 3020, 1508, 301, 2200, 4510, 5132, 501, 5010, 999,
        4506, 5208, 1905, 1307, 2202, 5213, 3005, 3801, 2313, 2705, 5216, 4502,
        3017, 1399, 5136, 3999, 5131, 4507, 1506, 2501, 4008, 5299, 2301, 2608,
        5211, 4304, 1402, 101, 2699, 2611, 1405, 5201, 1407, 1408, 1107, 1433,
        5220, 1410, 1413, 1599, 1401, 1904, 5209, 1907, 1435, 2299, 1419, 3000,
        410, 4511, 2703, 3903, 103, 109, 1404, 5212, 2609, 111, 180, 5110, 1302,
        4299, 3904, 4599, 5214, 499, 3012, 1104, 907, 5199, 5134, 3019, 2604,
        3014, 3802, 4501, 2399, 3031, 5099, 3907, 3006, 3902, 3899, 404, 405,
        5204, 4005, 1409, 1205, 2613, 5217, 4504, 1999, 3011, 1609, 4402, 4006,
        2612, 100, 4302, 1507, 2701, 1414, 4399, 1309, 302, 1515, 1500, 2607,
        5207, 1442, 5108, 107, 3033, 1499, 3103, 5215, 5101, 1439, 2605, 2610,
        181, 1427, 5105, 409, 3028, 1437, 5205, 5218, 406, 4512, 1199, 1102,
        1109, 1418, 4901, 910, 5114, 5219, 5117, 1105, 1510, 1909, 5003, 4505,
        1616, 2203, 2602, 1601, 3015, 2599, 5206, 4001, 502, 5111, 2615, 1403,
        3030, 3101, 108, 1505, 4099, 3001, 3023, 2902, 3905, 1002, 1423, 5106,
        305, 2314, 3106, 3018, 2806, 1315, 199, 1517, 1699, 1428, 4199, 5002,
        3026, 1001, 1436, 306, 5139, 303, 1425, 3025, 2603, 1516, 1611, 1612,
        112, 1902, 1422, 408,
    }
)

_SENTINEL_IDS: frozenset[str] = frozenset({"INVALID", "unknown"})


def test_curated_cip_codes_in_approved_list() -> None:
    """Every non-sentinel id in cip_codes.json must map to a 4-digit group covered by the 2022 FREEOP Graduate ROI Dataset."""
    root = find_repo_root()
    path = root / "categories_and_rules" / "cip_codes.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])

    failures: list[str] = []
    for item in items:
        cid = str(item.get("id", ""))
        if cid in _SENTINEL_IDS:
            continue
        parts = cid.split(".")
        if len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 4:
            failures.append(f"{cid!r}: unexpected format (expected XX.XXXX)")
            continue
        group_int = int(parts[0] + parts[1][:2])
        if group_int not in _APPROVED_GROUPS:
            failures.append(f"{cid!r}: group {group_int} not in approved list")

    assert failures == [], "CIP codes not in approved list:\n" + "\n".join(failures)
