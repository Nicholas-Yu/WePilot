import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger("skills")


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    body: str
    file_types: list[str] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)
    priority: int = 50
    enabled: bool = True


class SkillRuntime:
    def __init__(self, skill_dirs: Optional[List[str]] = None, max_loaded_skills: int = 2):
        self.skill_dirs = [Path(item) for item in (skill_dirs or ["skills", "user_skills"])]
        self.max_loaded_skills = max_loaded_skills
        self.skills = self.discover()

    def discover(self) -> list[Skill]:
        skills = []
        for base_dir in self.skill_dirs:
            if not base_dir.exists():
                continue
            for skill_md in sorted(base_dir.glob("*/SKILL.md")):
                try:
                    skill = self._load_skill(skill_md)
                    if skill.enabled:
                        skills.append(skill)
                except Exception as exc:
                    logger.warning("failed to load skill %s: %s", skill_md, exc)
        skills.sort(key=lambda skill: skill.priority, reverse=True)
        logger.info("loaded %s skills", len(skills))
        return skills

    def select(self, user_message: str, files: Optional[List[Any]] = None) -> list[Skill]:
        files = files or []
        explicit = self._explicit_skill_names(user_message)
        scored = []
        for skill in self.skills:
            score = 0
            if explicit and skill.name in explicit:
                score += 1000
            score += self._file_score(skill, files)
            score += self._intent_score(skill, user_message)
            if score > 0:
                scored.append((score + skill.priority / 100, skill))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [skill for _, skill in scored[: self.max_loaded_skills]]
        if selected:
            logger.info("selected skills: %s", ", ".join(skill.name for skill in selected))
        return selected

    def build_context(self, skills: list[Skill]) -> str:
        if not skills:
            return ""
        sections = [
            "本轮请应用以下 Skill 指令。Skill 是按需加载的专业工作流，请优先遵循这些指令完成任务。"
        ]
        for skill in skills:
            sections.append(f"\n--- Skill: {skill.name} ---\n{skill.body.strip()}")
        return "\n".join(sections)

    def _load_skill(self, skill_md: Path) -> Skill:
        raw = skill_md.read_text(encoding="utf-8")
        meta, body = self._parse_frontmatter(raw)
        name = str(meta.get("name", skill_md.parent.name)).strip()
        description = str(meta.get("description", "")).strip()
        if not name or not description:
            raise ValueError("SKILL.md must include name and description")
        return Skill(
            name=name,
            description=description,
            path=skill_md.parent,
            body=body,
            file_types=self._list_meta(meta.get("file_types", [])),
            intents=self._list_meta(meta.get("intents", [])),
            priority=int(meta.get("priority", 50)),
            enabled=str(meta.get("enabled", "true")).lower() != "false",
        )

    def _parse_frontmatter(self, raw: str) -> tuple[dict[str, Any], str]:
        if not raw.startswith("---"):
            return {}, raw
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return {}, raw
        meta = {}
        for line in parts[1].splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                items = [item.strip().strip('"').strip("'") for item in value[1:-1].split(",") if item.strip()]
                meta[key] = items
            else:
                meta[key] = value.strip('"').strip("'")
        return meta, parts[2]

    def _file_score(self, skill: Skill, files: list[Any]) -> int:
        if not skill.file_types or not files:
            return 0
        score = 0
        for file_ctx in files:
            filename = getattr(file_ctx, "filename", "").lower()
            suffix = Path(filename).suffix.lower()
            if suffix in skill.file_types:
                score += 20
        return score

    def _intent_score(self, skill: Skill, user_message: str) -> int:
        text = user_message.lower()
        score = 0
        searchable = " ".join([skill.name, skill.description] + skill.intents).lower()
        for token in self._tokens(text):
            if token and token in searchable:
                score += 3
        for intent in skill.intents:
            if intent.lower() in text:
                score += 15
        return score

    def _explicit_skill_names(self, user_message: str) -> set[str]:
        text = user_message.lower()
        names = set()
        for skill in self.skills:
            if skill.name in text or skill.name.replace("-", " ") in text:
                names.add(skill.name)
        return names

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text.lower())

    def _list_meta(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return []
