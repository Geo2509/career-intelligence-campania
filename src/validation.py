from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .strategy_performance import print_table


VALIDATION_REPORT_PATH = Path("output/validation_report.json")

DEFAULT_LOCATIONS = [
    "Napoli",
    "Pozzuoli",
    "Bacoli",
    "Monte di Procida",
    "Salerno",
    "Bari",
    "Gioia Tauro",
    "Remote",
    "Unknown",
]

DEFAULT_TARGET_ROLES = [
    "Data Entry",
    "Document Processing",
    "Back Office",
    "Import Export",
    "Shipping Documentation",
    "Excel Back Office",
    "Operations Assistant",
]

ROLE_ALIASES = {
    "Data Entry": ("data entry", "inserimento dati"),
    "Document Processing": ("document processing", "gestione documentale", "documenti", "documentazione"),
    "Back Office": ("back office",),
    "Import Export": ("import export", "import", "export"),
    "Shipping Documentation": ("shipping documentation", "spedizioni", "shipping", "documentazione"),
    "Excel Back Office": ("excel back office", "excel", "back office"),
    "Operations Assistant": ("operations assistant", "operativo", "operations"),
}


def build_validation_report(
    *,
    records: list[dict],
    run_stats: object,
    engine_performance: dict,
    strategy_ranking: dict,
    query_performance: dict,
    discovery_recommendations: dict,
    roles_path: str | Path = "configs/roles.yaml",
    locations_path: str | Path = "configs/locations.yaml",
) -> dict:
    unique_companies = len({record.get("domain", "") for record in records if record.get("domain")})
    profiled_companies = int(getattr(run_stats, "profiled_companies", 0) or 0)
    ignored = _count_action(records, "Ignore")
    possible = _count_qualification(records, "Possible Match")
    good = _count_qualification(records, "Good Match")
    excellent = _count_qualification(records, "Excellent Match")
    send_cv = _count_action(records, "Send CV")
    manual_review = _count_action(records, "Manual Review")

    locations = _target_locations(locations_path)
    roles = _target_roles(roles_path)
    industries = _count_values(records, "industry", default="Unknown")
    location_counts = _regional_counts(records, locations)
    role_coverage = _role_coverage(records, roles)

    quality = {
        "precision": _safe_rate(send_cv, profiled_companies),
        "send_cv_rate": _safe_rate(send_cv, unique_companies),
        "good_match_rate": _safe_rate(good + excellent, unique_companies),
        "ignored_rate": _safe_rate(ignored, unique_companies),
    }

    recommendations = {
        "queries_to_keep": discovery_recommendations.get("queries_to_keep", []),
        "queries_to_remove": discovery_recommendations.get("queries_to_remove", []),
        "strategies_to_disable": _strategies_to_disable(strategy_ranking, discovery_recommendations),
        "roles_needing_more_coverage": [
            role for role, metrics in role_coverage.items() if metrics["companies"] == 0
        ],
        "cities_needing_more_coverage": [
            location for location, count in location_counts.items() if location != "Unknown" and count == 0
        ],
    }

    return {
        "generated_at": _utc_now(),
        "validation_dataset": {
            "total_companies_discovered": int(getattr(run_stats, "after_aggregator_filter", unique_companies) or 0),
            "unique_companies": unique_companies,
            "profiled_companies": profiled_companies,
            "ignored_companies": ignored,
            "possible_match": possible,
            "good_match": good,
            "excellent_match": excellent,
            "send_cv": send_cv,
            "manual_review": manual_review,
        },
        "regional_analysis": location_counts,
        "industry_analysis": industries,
        "role_coverage": role_coverage,
        "engine_comparison": engine_performance.get("engines", {}),
        "quality": quality,
        "top_industries": _top_items(industries),
        "top_locations": _top_items(location_counts),
        "top_strategies": [
            item.get("strategy", "") for item in strategy_ranking.get("ranking", [])[:5] if item.get("strategy")
        ],
        "top_queries": [
            item.get("query", "") for item in query_performance.get("ranking", [])[:10] if item.get("query")
        ],
        "recommendations": recommendations,
    }


def write_validation_report(report: dict, path: str | Path = VALIDATION_REPORT_PATH) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def print_validation_report(report: dict) -> None:
    dataset = report.get("validation_dataset", {})
    quality = report.get("quality", {})
    print_table(
        ["Metric", "Value"],
        [
            ["Unique Companies", str(dataset.get("unique_companies", 0))],
            ["Profiled Companies", str(dataset.get("profiled_companies", 0))],
            ["Send CV", str(dataset.get("send_cv", 0))],
            ["Manual Review", str(dataset.get("manual_review", 0))],
            ["Precision", f"{float(quality.get('precision', 0)):.2f}"],
            ["Good Match Rate", f"{float(quality.get('good_match_rate', 0)):.2f}"],
            ["Ignored Rate", f"{float(quality.get('ignored_rate', 0)):.2f}"],
        ],
    )


def _count_action(records: list[dict], action: str) -> int:
    return sum(1 for record in records if record.get("next_action") == action)


def _count_qualification(records: list[dict], qualification: str) -> int:
    return sum(1 for record in records if record.get("qualification") == qualification)


def _count_values(records: list[dict], field: str, default: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(field, "") or default)
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        counts[default] = 0
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _regional_counts(records: list[dict], target_locations: list[str]) -> dict[str, int]:
    counts = {location: 0 for location in target_locations}
    counts.setdefault("Unknown", 0)
    for record in records:
        location = _record_location(record, target_locations)
        counts[location] = counts.get(location, 0) + 1
    return counts


def _record_location(record: dict, target_locations: list[str]) -> str:
    text = " ".join(
        str(record.get(key, ""))
        for key in ("city", "region", "title", "snippet", "page_text", "query", "original_query")
    ).lower()
    if any(term in text for term in ("remoto", "remote", "smart working")):
        return "Remote"
    for location in target_locations:
        if location == "Unknown":
            continue
        if location.lower() in text:
            return location
    return record.get("city") or record.get("region") or "Unknown"


def _role_coverage(records: list[dict], target_roles: list[str]) -> dict[str, dict[str, int]]:
    coverage = {role: {"companies": 0, "send_cv": 0, "good_or_excellent": 0} for role in target_roles}
    for record in records:
        text = " ".join(
            str(record.get(key, ""))
            for key in ("title", "snippet", "page_text", "query", "original_query", "queries")
        ).lower()
        for role in target_roles:
            aliases = ROLE_ALIASES.get(role, (role.lower(),))
            if any(alias.lower() in text for alias in aliases):
                coverage[role]["companies"] += 1
                if record.get("next_action") == "Send CV":
                    coverage[role]["send_cv"] += 1
                if record.get("qualification") in {"Good Match", "Excellent Match"}:
                    coverage[role]["good_or_excellent"] += 1
    return coverage


def _target_locations(locations_path: str | Path) -> list[str]:
    configured = _load_yaml_list(locations_path, "locations")
    normalized = ["Remote" if "remoto" in location.lower() or "remote" in location.lower() else location for location in configured]
    return _stable_unique([*DEFAULT_LOCATIONS, *normalized, "Unknown"])


def _target_roles(roles_path: str | Path) -> list[str]:
    configured = [role.title() for role in _load_yaml_list(roles_path, "roles")]
    return _stable_unique([*DEFAULT_TARGET_ROLES, *configured])


def _load_yaml_list(path: str | Path, key: str) -> list[str]:
    config_path = Path(path)
    if not config_path.exists():
        return []
    data = yaml.safe_load(config_path.read_text()) or {}
    return [str(value) for value in data.get(key, [])]


def _stable_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _top_items(counts: dict[str, int], limit: int = 5) -> list[dict[str, object]]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _strategies_to_disable(strategy_ranking: dict, discovery_recommendations: dict) -> list[str]:
    only_ignored = set(discovery_recommendations.get("strategies_producing_only_ignored_companies", []))
    disable = {
        item.get("strategy", "")
        for item in strategy_ranking.get("ranking", [])
        if item.get("strategy")
        and float(item.get("strategy_score", 0) or 0) == 0
        and int(item.get("samples", 1) or 1) >= 1
    }
    disable.update(only_ignored)
    return sorted(disable)


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0
    return round(numerator / denominator, 4)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
