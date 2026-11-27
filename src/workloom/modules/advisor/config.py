"""WorkloomAdvisor module configuration."""

from pathlib import Path

from workloom.modules.base import RAGModuleConfig


def _load_prompt() -> str:
    """Load system prompt from file."""
    prompt_path = (
        Path(__file__).parent.parent.parent.parent.parent / "prompts" / "advisor.txt"
    )
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""


advisor_config = RAGModuleConfig(
    department_id="advisor",
    display_name="WorkloomAdvisor Telegram",
    description="Консультант по здоровью WORKLOOM",
    system_prompt=_load_prompt(),
    rag_limit=10,
    score_threshold=0.30,
    department_filter="advisor",
)
