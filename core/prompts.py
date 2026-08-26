from pathlib import Path


DEFAULT_PROMPT = (
    "Analizeaza imaginea cu atentie. "
    "Descrie ceea ce vezi si raspunde la intrebarea utilizatorului. "
    "Raspunde in romana. "
    "Nu inventa caracteristici care nu sunt vizibile."
)


def load_prompt(prompt_path: Path) -> str:
    """
    Citește un prompt dintr-un fișier text.
    """
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"Fișierul prompt nu există: {prompt_path}"
        )

    prompt = prompt_path.read_text(encoding="utf-8").strip()

    if not prompt:
        raise ValueError(
            f"Fișierul prompt este gol: {prompt_path}"
        )

    return prompt


def save_prompt(prompt_path: Path, prompt: str) -> None:
    """
    Salvează un prompt într-un fișier text.
    """
    prompt = prompt.strip()

    if not prompt:
        raise ValueError("Promptul nu poate fi gol.")

    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")


def get_default_prompt() -> str:
    """
    Returnează promptul implicit al aplicației.
    """
    return DEFAULT_PROMPT