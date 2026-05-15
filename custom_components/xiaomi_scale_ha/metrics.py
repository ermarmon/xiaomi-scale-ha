from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

_LOGGER = logging.getLogger(__name__)


def build_metrics(payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    weight = float(payload["weight"])
    if payload["unit"] == "lbs":
        calc_weight = round(weight * 0.4536, 2)
    elif payload["unit"] == "jin":
        calc_weight = round(weight * 0.5, 2)
    else:
        calc_weight = weight

    height_m = float(user["HEIGHT"]) / 100
    result = {"bmi": round(calc_weight / (height_m * height_m), 2)}

    impedance = payload.get("impedance")
    if impedance:
        try:
            from .body_metrics import bodyMetrics

            age = age_years(user["DOB"])
            metrics = bodyMetrics(calc_weight, int(user["HEIGHT"]), age, user["SEX"], int(impedance))
            result.update(
                {
                    "basal_metabolism": round(metrics.getBMR(), 2),
                    "visceral_fat": round(metrics.getVisceralFat(), 2),
                    "lean_body_mass": round(metrics.getLBMCoefficient(), 2),
                    "body_fat": round(metrics.getFatPercentage(), 2),
                    "water": round(metrics.getWaterPercentage(), 2),
                    "bone_mass": round(metrics.getBoneMass(), 2),
                    "muscle_mass": round(metrics.getMuscleMass(), 2),
                    "protein": round(metrics.getProteinPercentage(), 2),
                    "metabolic_age": round(metrics.getMetabolicAge()),
                }
            )
        except Exception as err:
            result["metrics_error"] = str(err)
            _LOGGER.debug("Unable to calculate impedance metrics: %s", err)
    return result


def age_years(dob: str) -> float:
    born = datetime.strptime(dob, "%Y-%m-%d")
    return abs((datetime.today() - born).days) / 365


def slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def same_weight_session(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    prev_w = previous.get("weight")
    curr_w = current.get("weight")
    if not isinstance(prev_w, (int, float)) or not isinstance(curr_w, (int, float)):
        return False
    if previous.get("unit") != current.get("unit"):
        return False
    return abs(float(prev_w) - float(curr_w)) <= 0.2
