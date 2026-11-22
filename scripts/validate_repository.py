"""Validate shipped metadata/docs and reject private subscription credentials."""

from pathlib import Path
import json
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "__pycache__", ".pytest_cache"}
files = [
    p
    for p in ROOT.rglob("*")
    if p.is_file() and not SKIP.intersection(p.relative_to(ROOT).parts)
]
errors = []
private = re.compile(
    r"spielerplus[.]de/events/ics[?]t=([A-Za-z0-9_-]+)&u=([A-Za-z0-9_-]+)"
)
allowed = {"EXAMPLE", "PRIVATE", "DEIN_TOKEN"}
for path in files:
    if path.suffix in {".json", ".yaml", ".yml", ".md", ".py", ".example"}:
        text = path.read_text()
        for first, second in private.findall(text):
            if first not in allowed or second not in allowed:
                errors.append(
                    f"{path.relative_to(ROOT)}: possible private ICS credentials"
                )
        if path.suffix == ".json":
            json.loads(text)
        if path.suffix in {".yaml", ".yml"}:
            yaml.load(text, Loader=yaml.BaseLoader)
        if path.suffix == ".md":
            links = re.findall(r'\]\(([^)]+)\)|(?:src|href)="([^"]+)"', text)
            for choices in links:
                target = next(x for x in choices if x).split("#", 1)[0]
                if not target or re.match(r"[a-z]+:", target):
                    continue
                if not (path.parent / target).exists():
                    errors.append(
                        f"{path.relative_to(ROOT)}: broken relative link {target}"
                    )
manifest = json.loads(
    (ROOT / "custom_components/spielerplus/manifest.json").read_text()
)
for language in ["en", "de"]:
    translated = json.loads(
        (
            ROOT / f"custom_components/spielerplus/translations/{language}.json"
        ).read_text()
    )
    for key in [
        "next_training",
        "next_game",
        "countdown",
        "events_week",
        "last_success",
        "last_change",
    ]:
        if key not in translated["entity"]["sensor"]:
            errors.append(f"Missing {language} sensor translation: {key}")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print(
    f"Metadata, DE/EN translations, YAML, relative documentation links and credential scan: OK (v{manifest['version']})"
)
