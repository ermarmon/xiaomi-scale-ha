from __future__ import annotations

import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

MISCALE_V2_UUID = "0000181b-0000-1000-8000-00805f9b34fb"
MISCALE_V1_UUID = "0000181d-0000-1000-8000-00805f9b34fb"


@dataclass(frozen=True)
class ScaleMeasurement:
    weight: float
    unit: str
    timestamp: str
    stabilized: bool
    impedance: int | None
    source_address: str
    rssi: int | None


def parse_service_info(service_info: Any) -> ScaleMeasurement | None:
    service_data = {
        str(key).lower(): value for key, value in service_info.service_data.items()
    }
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    address = service_info.address
    rssi = getattr(service_info, "rssi", None)

    if MISCALE_V2_UUID in service_data:
        data = binascii.b2a_hex(service_data[MISCALE_V2_UUID]).decode("ascii")
        data = "1b18" + data
        payload = bytes.fromhex(data[4:])
        ctrl_byte = payload[1]
        stabilized = bool(ctrl_byte & (1 << 5))
        has_impedance = bool(ctrl_byte & (1 << 1))
        measunit = data[4:6]
        measured = int((data[28:30] + data[26:28]), 16) * 0.01
        unit = ""
        if measunit == "03":
            unit = "lbs"
        if measunit == "02":
            unit = "kg"
            measured = measured / 2
        if not unit:
            return None
        impedance = int((data[24:26] + data[22:24]), 16) if has_impedance else None
        return ScaleMeasurement(
            weight=round(measured, 2),
            unit=unit,
            timestamp=timestamp,
            stabilized=stabilized,
            impedance=impedance,
            source_address=address,
            rssi=rssi,
        )

    if MISCALE_V1_UUID in service_data:
        data = binascii.b2a_hex(service_data[MISCALE_V1_UUID]).decode("ascii")
        data = "1d18" + data
        measunit = data[4:6]
        measured = int((data[8:10] + data[6:8]), 16) * 0.01
        unit = ""
        if measunit.startswith(("03", "a3")):
            unit = "lbs"
        if measunit.startswith(("12", "b2")):
            unit = "jin"
        if measunit.startswith(("22", "a2")):
            unit = "kg"
            measured = measured / 2
        if not unit:
            return None
        return ScaleMeasurement(
            weight=round(measured, 2),
            unit=unit,
            timestamp=timestamp,
            stabilized=True,
            impedance=None,
            source_address=address,
            rssi=rssi,
        )

    return None
