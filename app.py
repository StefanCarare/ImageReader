from pathlib import Path
import sys

from core.images import (
    get_image_path,
    image_to_base64,
    get_image_metadata,
)

from core.prompts import load_prompt

from core.ollama import (
    check_ollama,
    generate,
    get_response,
    get_thinking,
    get_statistics,
    OllamaError,
)

from core.output import (
    save_result,
    create_output_path,
)


# ============================================================
# PATHS
# ============================================================

APP_ROOT = Path(__file__).resolve().parent

CONFIG_DIR = APP_ROOT / "config"
INPUT_DIR = APP_ROOT / "input"
OUTPUT_DIR = APP_ROOT / "output"
PROMPTS_DIR = APP_ROOT / "prompts"
LOG_DIR = APP_ROOT / "logs"


# ============================================================
# SETTINGS
# ============================================================

def load_settings(settings_path: Path) -> dict:
    """
    Citește un fișier de forma:

        KEY=value

    și returnează un dicționar.
    """

    if not settings_path.is_file():
        raise FileNotFoundError(
            f"Fișierul settings nu există: {settings_path}"
        )

    settings = {}

    for line in settings_path.read_text(
        encoding="utf-8"
    ).splitlines():

        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        settings[key.strip()] = value.strip()

    return settings


# ============================================================
# INPUT IMAGE
# ============================================================

def find_first_image(input_dir: Path) -> Path:
    """
    Găsește prima imagine din directorul input.
    """

    extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
    }

    images = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in extensions
    )

    if not images:
        raise FileNotFoundError(
            f"Nu am găsit nicio imagine în: {input_dir}"
        )

    return images[0]


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    print()
    print("========================================")
    print("MUSE VISION")
    print("========================================")
    print()

    # --------------------------------------------------------
    # Directoare
    # --------------------------------------------------------

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # Settings
    # --------------------------------------------------------

    try:
        settings = load_settings(
            CONFIG_DIR / "settings.txt"
        )

    except Exception as exc:
        print(f"EROARE settings: {exc}")
        return 1

    ollama_url = settings.get(
        "OLLAMA_URL",
        "http://localhost:11434"
    )

    model = settings.get(
        "MODEL",
        "muse-glimmer"
    )

    try:
        num_ctx = int(
            settings.get("NUM_CTX", "8192")
        )

        num_predict = int(
            settings.get("NUM_PREDICT", "1500")
        )

    except ValueError:
        print("EROARE: NUM_CTX sau NUM_PREDICT nu este numeric.")
        return 1

    print(f"Model: {model}")
    print(f"Ollama: {ollama_url}")
    print(f"Context: {num_ctx}")
    print(f"Max output tokens: {num_predict}")
    print()

    # --------------------------------------------------------
    # Verificăm Ollama
    # --------------------------------------------------------

    print("Verific Ollama...")

    if not check_ollama(ollama_url):
        print()
        print("EROARE: Ollama nu este accesibil.")
        print("Verifică dacă Ollama rulează.")
        return 1

    print("Ollama: OK")
    print()

    # --------------------------------------------------------
    # Găsim imaginea
    # --------------------------------------------------------

    try:
        image_path = find_first_image(INPUT_DIR)

    except Exception as exc:
        print(f"EROARE imagine: {exc}")
        return 1

    print(f"Imagine: {image_path.name}")

    # --------------------------------------------------------
    # Metadata imagine
    # --------------------------------------------------------

    try:
        image_metadata = get_image_metadata(
            image_path
        )

    except Exception as exc:
        print(f"AVERTISMENT metadata: {exc}")
        image_metadata = {}

    if image_metadata.get("photo_date"):
        print(
            f"Data fotografierii: "
            f"{image_metadata['photo_date']}"
        )

    print()

    # --------------------------------------------------------
    # Prompt
    # --------------------------------------------------------

    prompt_path = PROMPTS_DIR / "default.txt"

    if not prompt_path.is_file():

        print(
            f"EROARE: Nu există promptul:\n"
            f"{prompt_path}"
        )

        print()
        print(
            "Creează fișierul:"
        )
        print(
            f"  {prompt_path}"
        )

        return 1

    try:
        prompt = load_prompt(prompt_path)

    except Exception as exc:
        print(f"EROARE prompt: {exc}")
        return 1

    print("Prompt încărcat.")
    print()

    # --------------------------------------------------------
    # Imagine -> Base64
    # --------------------------------------------------------

    print("Pregătesc imaginea...")

    try:
        image_base64 = image_to_base64(
            image_path
        )

    except Exception as exc:
        print(f"EROARE imagine: {exc}")
        return 1

    print("Imagine pregătită.")
    print()

    # --------------------------------------------------------
    # Ollama
    # --------------------------------------------------------

    print("Trimit imaginea către Muse Glimmer...")
    print("Acest pas poate dura.")
    print()

    try:
        data = generate(
            ollama_url=ollama_url,
            model=model,
            prompt=prompt,
            image_base64=image_base64,
            num_ctx=num_ctx,
            num_predict=num_predict,
        )

    except OllamaError as exc:
        print()
        print(f"EROARE Ollama: {exc}")
        return 1

    # --------------------------------------------------------
    # Extragem rezultatele
    # --------------------------------------------------------

    response = get_response(data)
    thinking = get_thinking(data)
    statistics = get_statistics(data)

    # --------------------------------------------------------
    # Afișăm răspunsul
    # --------------------------------------------------------

    print("========================================")
    print("RĂSPUNS MUSE GLIMMER")
    print("========================================")
    print()

    print(response)

    print()

    # --------------------------------------------------------
    # Salvăm rezultatul
    # --------------------------------------------------------

    output_path = create_output_path(
        OUTPUT_DIR,
        image_path,
        suffix="_description",
    )

    try:
        save_result(
            output_path=output_path,
            response=response,
            thinking=thinking,
            image_name=image_path.name,
            prompt=prompt,
            model=model,
            statistics=statistics,
            image_metadata=image_metadata,
            preset_name="",
        )

    except Exception as exc:
        print()
        print(f"EROARE salvare: {exc}")
        return 1

    print()
    print("========================================")
    print(f"Rezultatul a fost salvat în:")
    print(output_path)
    print("========================================")
    print()

    return 0


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    sys.exit(main())