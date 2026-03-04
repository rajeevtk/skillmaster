from dataclasses import dataclass, field


@dataclass
class GeneratedSkill:
    skill_id: str
    name: str
    description: str
    skill_md: str
    additional_files: dict[str, str] = field(default_factory=dict)  # filename -> content
