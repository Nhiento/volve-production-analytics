"""Tag registry: the single source of truth for which tags exist and what "good" looks like.

It works like a tiny PI Asset Framework:
  - assets.csv         one row per well (the "elements")
  - tag_templates.csv  one row per measurement type (the "element template")
  - every asset gets every template, so 6 wells x 12 templates = 72 tags

The publisher, the quality monitor and the docs all read from here, so a unit or
limit is defined once and used everywhere.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

TAGS_DIR = Path(__file__).resolve().parent / "tags"


@dataclass(frozen=True)
class Template:
    name: str
    source_column: str
    unit: str
    description: str
    min: float
    max: float
    frozen_check: bool
    zero_is_bad_when_flowing: bool


@dataclass(frozen=True)
class Asset:
    asset_id: str
    source_wellbore: str
    field: str
    facility: str
    role: str


@dataclass(frozen=True)
class Tag:
    asset: Asset
    template: Template

    @property
    def tag_id(self) -> str:
        """Human-readable tag name, e.g. volve.F-12.downhole_pressure"""
        return f"volve.{self.asset.asset_id}.{self.template.name}"

    @property
    def topic(self) -> str:
        """MQTT topic the value is published on, e.g. volve/F-12/downhole_pressure"""
        return f"volve/{self.asset.asset_id}/{self.template.name}"


def _yes(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1"}


def load_templates() -> list[Template]:
    with open(TAGS_DIR / "tag_templates.csv", newline="") as f:
        return [
            Template(
                name=r["template"],
                source_column=r["source_column"],
                unit=r["unit"],
                description=r["description"],
                min=float(r["min"]),
                max=float(r["max"]),
                frozen_check=_yes(r["frozen_check"]),
                zero_is_bad_when_flowing=_yes(r["zero_is_bad_when_flowing"]),
            )
            for r in csv.DictReader(f)
        ]


def load_assets() -> list[Asset]:
    with open(TAGS_DIR / "assets.csv", newline="") as f:
        return [Asset(**r) for r in csv.DictReader(f)]


def load_tags() -> list[Tag]:
    templates = load_templates()
    return [Tag(a, t) for a in load_assets() for t in templates]


if __name__ == "__main__":
    tags = load_tags()
    print(f"{len(tags)} tags")
    for tag in tags[:12]:
        t = tag.template
        print(f"  {tag.tag_id:<38} {t.unit:<6} [{t.min:g}, {t.max:g}]")
