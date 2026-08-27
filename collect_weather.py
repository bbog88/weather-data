#!/usr/bin/env python3
"""Collect current weather for Jinju and Busan from Open-Meteo."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Asia/Seoul"
DATA_DIR = Path(__file__).resolve().parent / "data"

LOCATIONS = (
    {"name": "진주", "slug": "jinju", "latitude": 35.1800, "longitude": 128.1076},
    {"name": "부산", "slug": "busan", "latitude": 35.1796, "longitude": 129.0756},
)

CURRENT_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
)

CSV_FIELDS = (
    "collected_at",
    "observed_at",
    "location",
    "latitude",
    "longitude",
    "temperature_c",
    "apparent_temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "weather_code",
)


def fetch_current_weather(location: dict[str, object]) -> dict[str, object]:
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "current": ",".join(CURRENT_FIELDS),
        "timezone": TIMEZONE,
    }
    request = Request(
        f"{API_URL}?{urlencode(params)}",
        headers={"User-Agent": "github-weather-collector/1.0"},
    )

    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    current = payload.get("current")
    if not isinstance(current, dict):
        raise ValueError(f"{location['name']}: API 응답에 current 데이터가 없습니다.")

    required = ("time", *CURRENT_FIELDS)
    missing = [field for field in required if current.get(field) is None]
    if missing:
        raise ValueError(
            f"{location['name']}: API 응답에서 필수 항목이 누락되었습니다: {', '.join(missing)}"
        )

    return current


def has_observation(csv_path: Path, observed_at: str) -> bool:
    if not csv_path.exists():
        return False

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return any(
            row.get("observed_at") == observed_at
            for row in csv.DictReader(csv_file)
        )


def append_observation(
    csv_path: Path,
    location: dict[str, object],
    current: dict[str, object],
    collected_at: str,
) -> bool:
    observed_at = str(current["time"])
    if has_observation(csv_path, observed_at):
        print(f"{location['name']}: {observed_at} 데이터가 이미 있어 건너뜁니다.")
        return False

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not csv_path.exists()
    row = {
        "collected_at": collected_at,
        "observed_at": observed_at,
        "location": location["name"],
        "latitude": f"{float(location['latitude']):.4f}",
        "longitude": f"{float(location['longitude']):.4f}",
        "temperature_c": current["temperature_2m"],
        "apparent_temperature_c": current["apparent_temperature"],
        "relative_humidity_pct": current["relative_humidity_2m"],
        "precipitation_mm": current["precipitation"],
        "weather_code": current["weather_code"],
    }

    with csv_path.open("a", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        if is_new_file:
            writer.writeheader()
        writer.writerow(row)

    print(f"{location['name']}: {observed_at} 데이터를 {csv_path}에 저장했습니다.")
    return True


def main() -> int:
    # 먼저 두 지역을 모두 받아 API 오류로 한 지역만 저장되는 상황을 피합니다.
    weather_by_slug = {
        str(location["slug"]): fetch_current_weather(location)
        for location in LOCATIONS
    }
    collected_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")

    added_count = 0
    for location in LOCATIONS:
        csv_path = DATA_DIR / f"{location['slug']}_weather.csv"
        added_count += append_observation(
            csv_path,
            location,
            weather_by_slug[str(location["slug"])],
            collected_at,
        )

    print(f"완료: 새 행 {added_count}개를 저장했습니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"날씨 수집 실패: {error}", file=sys.stderr)
        raise SystemExit(1)
