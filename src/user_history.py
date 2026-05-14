from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any


class UserHistoryManager:
    def __init__(self, path: str = "data/user_history.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, list[dict[str, Any]]] = {"users": {}}
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict) and isinstance(loaded.get("users"), dict):
                    self.data = loaded
            except (json.JSONDecodeError, OSError):
                self.data = {"users": {}}

    def _save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    def add_measurement(self, user_name: str, weight: float, timestamp: str) -> None:
        users = self.data.setdefault("users", {})
        measurements = users.setdefault(user_name, [])
        measurements.append({"weight": float(weight), "timestamp": timestamp})
        users[user_name] = measurements[-10:]
        self._save()

    def get_candidates(
        self,
        weight: float,
        users_config: list[dict[str, Any]],
        tolerance_kg: float = 2.0,
    ) -> list[str]:
        candidates: list[str] = []
        users = self.data.get("users", {})

        for user in users_config:
            name = user.get("NAME")
            if not isinstance(name, str):
                continue
            history = users.get(name, [])
            if len(history) >= 3:
                last_weights = [float(m["weight"]) for m in history[-10:] if "weight" in m]
                if last_weights and abs(mean(last_weights) - weight) <= tolerance_kg:
                    candidates.append(name)
            else:
                # Bootstrap: fall back to GT/LT range for users with insufficient history
                gt = user.get("GT")
                lt = user.get("LT")
                if isinstance(gt, (int, float)) and isinstance(lt, (int, float)):
                    if gt < weight < lt:
                        candidates.append(name)

        return candidates
