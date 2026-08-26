from pathlib import Path
import re
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk


from PIL import Image, ImageTk

from core.images import (
    image_to_base64,
    get_image_metadata,
)

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

from core.prompts import (
    load_prompt,
    save_prompt
)


# ============================================================
# PATHS
# ============================================================

APP_ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = APP_ROOT / "config"
OUTPUT_DIR = APP_ROOT / "output"
PROMPTS_DIR = APP_ROOT / "prompts"

ROMANIAN_COUNTIES = [
    "Alba",
    "Arad",
    "Argeș",
    "Bacău",
    "Bihor",
    "Bistrița-Năsăud",
    "Botoșani",
    "Brașov",
    "Brăila",
    "București",
    "Buzău",
    "Caraș-Severin",
    "Călărași",
    "Cluj",
    "Constanța",
    "Covasna",
    "Dâmbovița",
    "Dolj",
    "Galați",
    "Giurgiu",
    "Gorj",
    "Harghita",
    "Hunedoara",
    "Ialomița",
    "Iași",
    "Ilfov",
    "Maramureș",
    "Mehedinți",
    "Mureș",
    "Neamț",
    "Olt",
    "Prahova",
    "Sălaj",
    "Satu Mare",
    "Sibiu",
    "Suceava",
    "Teleorman",
    "Timiș",
    "Tulcea",
    "Vaslui",
    "Vâlcea",
    "Vrancea",
]

# ============================================================
# SETTINGS
# ============================================================

def load_settings(settings_path: Path) -> dict:
    """
    Citește setările dintr-un fișier KEY=value.
    """

    if not settings_path.is_file():
        return {}

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


def load_prompt_file(prompt_path: Path) -> str:
    """
    Citește un prompt dintr-un fișier text UTF-8.
    """

    if not prompt_path.is_file():
        return ""

    return prompt_path.read_text(
        encoding="utf-8"
    ).strip()


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow:

    def __init__(self, root: tk.Tk):

        self.root = root

        self.root.title("Muse Vision")
        self.root.geometry("1100x800")
        self.root.minsize(900, 650)

        # ----------------------------------------------------
        # Settings
        # ----------------------------------------------------

        settings = load_settings(
            CONFIG_DIR / "settings.txt"
        )

        self.ollama_url = settings.get(
            "OLLAMA_URL",
            "http://localhost:11434"
        )

        self.model = settings.get(
            "MODEL",
            "muse-glimmer"
        )

        try:
            self.num_ctx = int(
                settings.get("NUM_CTX", "8192")
            )
        except ValueError:
            self.num_ctx = 8192

        try:
            self.num_predict = int(
                settings.get("NUM_PREDICT", "4000")
            )      
        except ValueError:
            self.num_predict = 4000

        try:
            self.thinking = (
                settings.get("THINKING", "true").lower()
                in ("1", "true", "yes", "on")
            )            
        except ValueError:
            self.thinking = 4000

        # ----------------------------------------------------
        # State
        # ----------------------------------------------------

        self.image_paths = []
        self.image_status = {}
        self.image_locations = {}
        self.image_path: Path | None = None
        self.image_metadata = {}
        self.image_base64 = None

        self.response_text = ""
        self.thinking_text = ""
        self.statistics = {}
        self.prompt_raw_text = ""
        self.prompt_is_rendered = False
        self.output_is_rendered = False
        self.text_zoom_size = 10

        self.preview_image = None
        self.analysis_start_time = None
        self.status_update_timer = None
        self.batch_current = 0
        self.batch_total = 0
        self.batch_filename = ""

        # ----------------------------------------------------
        # GUI
        # ----------------------------------------------------
        
        self.build_ui()

        self.load_default_prompt()

        self.set_status("Ready")        

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        # ----------------------------------------------------
        # Main container
        # ----------------------------------------------------

        main = ttk.Frame(
            self.root,
            padding=12
        )

        main.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        title = ttk.Label(
            main,
            text="MUSE VISION",
            font=("Segoe UI", 20, "bold")
        )

        title.pack(
            anchor="w",
            pady=(0, 10)
        )


        # ----------------------------------------------------
        # Top section: Image + Prompt
        # ----------------------------------------------------

        top_frame = ttk.Frame(
            main
        )

        top_frame.pack(
            fill="x",
            expand=False,
            pady=(0, 10)
        )

        top_frame.columnconfigure(
            0,
            weight=45
        )

        top_frame.columnconfigure(
            1,
            weight=55
        )


        # ----------------------------------------------------
        # Image section
        # ----------------------------------------------------

        image_frame = ttk.LabelFrame(
            top_frame,
            text="Images",
            padding=10
        )

        image_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 6)
        )

        # ----------------------------------------------------
        # Image list
        # ----------------------------------------------------

        list_frame = ttk.Frame(
            image_frame
        )

        list_frame.pack(
            fill="x"
        )

        self.image_listbox = tk.Listbox(
            list_frame,
            height=5,
            selectmode=tk.SINGLE,
            font=("Segoe UI", 10)
        )

        self.image_listbox.pack(
            side="left",
            fill="both",
            expand=True
        )

        image_scroll = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.image_listbox.yview
        )

        image_scroll.pack(
            side="right",
            fill="y"
        )

        self.image_listbox.configure(
            yscrollcommand=image_scroll.set
        )

        self.image_listbox.bind(
            "<<ListboxSelect>>",
            self.on_image_selected
        )

        # ----------------------------------------------------
        # Image buttons
        # ----------------------------------------------------

        image_buttons = ttk.Frame(
            image_frame
        )

        image_buttons.pack(
            fill="x",
            pady=(8, 0)
        )

        self.add_images_button = ttk.Button(
            image_buttons,
            text="Add Images...",
            command=self.add_images
        )

        self.add_images_button.pack(
            side="left"
        )

        self.add_folder_button = ttk.Button(
            image_buttons,
            text="Add Folder...",
            command=self.add_folder
        )

        self.add_folder_button.pack(
            side="left",
            padx=(8, 0)
        )

        self.remove_image_button = ttk.Button(
            image_buttons,
            text="Remove",
            command=self.remove_selected_image
        )

        self.remove_image_button.pack(
            side="left",
            padx=(8, 0)
        )

        self.clear_images_button = ttk.Button(
            image_buttons,
            text="Clear",
            command=self.clear_images
        )

        self.clear_images_button.pack(
            side="left",
            padx=(8, 0)
        )

        # ----------------------------------------------------
        # Preview + Photo Info
        # ----------------------------------------------------

        preview_info_frame = ttk.Frame(
            image_frame
        )

        preview_info_frame.pack(
            fill="x",
            pady=(10, 0)
        )

        # ----------------------------------------------------
        # Preview
        # ----------------------------------------------------

        preview_frame = ttk.Frame(
            preview_info_frame
        )

        preview_frame.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.preview_label = ttk.Label(
            preview_frame,
            text="No image selected",
            anchor="center"
        )

        self.preview_label.pack(
            fill="both",
            expand=True
        )

        # ----------------------------------------------------
        # Photo Info
        # ----------------------------------------------------

        photo_info_frame = ttk.LabelFrame(
            preview_info_frame,
            text="Photo Info",
            padding=10
        )

        photo_info_frame.pack(
            side="left",
            fill="both",
            padx=(15, 0)
        )

        self.photo_file_label = ttk.Label(
            photo_info_frame,
            text="File: —",
            anchor="w"
        )

        self.photo_file_label.pack(
            anchor="w",
            pady=(0, 6)
        )

        self.photo_date_label = ttk.Label(
            photo_info_frame,
            text="Date: —",
            anchor="w"
        )

        self.photo_date_label.pack(
            anchor="w",
            pady=(0, 6)
        )

        self.photo_camera_label = ttk.Label(
            photo_info_frame,
            text="Camera: —",
            anchor="w"
        )

        self.photo_camera_label.pack(
            anchor="w",
            pady=(0, 6)
        )

        self.photo_model_label = ttk.Label(
            photo_info_frame,
            text="Model: —",
            anchor="w"
        )

        self.photo_model_label.pack(
            anchor="w",
            pady=(0, 6)
        )

        self.photo_location_label = ttk.Label(
            photo_info_frame,
            text="GPS: —",
            anchor="w"
        )

        self.photo_location_label.pack(
            anchor="w",
            pady=(0, 8)
        )

        ttk.Label(
            photo_info_frame,
            text="Location:"
        ).pack(
            anchor="w"
        )

        self.location_var = tk.StringVar(
            value="București"
        )

        self.location_combo = ttk.Combobox(
            photo_info_frame,
            textvariable=self.location_var,
            values=ROMANIAN_COUNTIES + ["__ALTCEVA__"],
            state="readonly",
            width=24
        )

        self.location_combo.pack(
            anchor="w"
        )

        self.location_combo.bind(
            "<<ComboboxSelected>>",
            self.on_location_selected
        )

        self.custom_location_var = tk.StringVar()

        self.custom_location_frame = ttk.Frame(
            photo_info_frame
        )

        ttk.Label(
            self.custom_location_frame,
            text="Localitate / locație:"
        ).pack(
            anchor="w",
            pady=(6, 2)
        )

        self.custom_location_entry = ttk.Entry(
            self.custom_location_frame,
            textvariable=self.custom_location_var,
            width=27
        )

        self.custom_location_entry.pack(
            anchor="w"
        )

        self.custom_location_entry.bind(
            "<FocusOut>",
            self.on_custom_location_changed
        )

        self.custom_location_entry.bind(
            "<Return>",
            self.on_custom_location_changed
        )

        # ----------------------------------------------------
        # Prompt section
        # ----------------------------------------------------

        prompt_frame = ttk.LabelFrame(
            top_frame,
            text="Prompt",
            padding=10
        )

        prompt_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(6, 0)
        )

        # Prompt selector
        prompt_controls = ttk.Frame(
            prompt_frame
        )

        prompt_controls.pack(
            fill="x",
            pady=(0, 8)
        )

        ttk.Label(
            prompt_controls,
            text="Preset:"
        ).pack(
            side="left"
        )

        self.prompt_var = tk.StringVar()

        self.prompt_combo = ttk.Combobox(
            prompt_controls,
            textvariable=self.prompt_var,
            state="readonly",
            width=30
        )

        self.prompt_combo.pack(
            side="left",
            padx=(8, 8)
        )

        self.new_prompt_button = ttk.Button(
            prompt_controls,
            text="New Prompt",
            command=self.new_prompt
        )

        self.new_prompt_button.pack(
            side="left",
            padx=(0, 6)
        )

        self.update_prompt_button = ttk.Button(
            prompt_controls,
            text="Update",
            command=self.update_prompt
        )

        self.update_prompt_button.pack(
            side="left"
        )

        self.prompt_combo.bind(
            "<<ComboboxSelected>>",
            self.on_prompt_selected
        )

        # Prompt editor        
        self.prompt_text = tk.Text(
            prompt_frame,
            height=7,
            wrap="word",
            font=("Segoe UI", 10)
        )
        self.configure_rich_text(
            self.prompt_text
        )
        self.prompt_text.bind(
            "<FocusIn>",
            self.edit_prompt_text
        )
        self.prompt_text.bind(
            "<FocusOut>",
            self.render_prompt_text
        )

        self.prompt_text.pack(
            fill="both",
            expand=True
        )

        self.populate_prompt_list()


        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        button_frame = ttk.Frame(main)

        button_frame.pack(
            fill="x",
            pady=(0, 10)
        )

        self.analyze_button = ttk.Button(
            button_frame,
            text="ANALYZE",
            command=self.start_analysis
        )

        self.analyze_button.pack(
            side="left"
        )

        self.analyze_all_button = ttk.Button(
            button_frame,
            text="ANALYZE ALL",
            command=self.start_batch_analysis
        )

        self.analyze_all_button.pack(
            side="left",
            padx=(8, 0)
        )

        self.save_button = ttk.Button(
            button_frame,
            text="SAVE",
            command=self.save_current_result,
            state="disabled"
        )

        self.save_button.pack(
            side="left",
            padx=(8, 0)
        )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        self.progress = ttk.Progressbar(
            button_frame,
            mode="indeterminate",
            length=150
        )

        self.progress.pack(
            side="right"
        )

        # ----------------------------------------------------
        # Batch progress group
        # ----------------------------------------------------

        self.batch_progress_frame = ttk.Frame(
            button_frame
        )

        self.batch_progress_label = ttk.Label(
            self.batch_progress_frame,
            text="Batch: 0 / 0"
        )

        self.batch_progress_label.pack(
            side="left",
            padx=(0, 8)
        )

        self.batch_progress = ttk.Progressbar(
            self.batch_progress_frame,
            mode="determinate",
            length=150
        )

        self.batch_progress.pack(
            side="left"
        )

        # Hidden until ANALYZE ALL
        self.batch_progress_frame.pack_forget()

        # ----------------------------------------------------
        # Status bar
        # ----------------------------------------------------

        status_frame = ttk.Frame(main)

        status_frame.pack(
            side="bottom",
            fill="x",
            pady=(8, 0)
        )

        self.status_label = ttk.Label(
            status_frame,
            text="Ready"
        )

        self.status_label.pack(
            side="left"
        )

        self.model_label = ttk.Label(
            status_frame,
            text=f"Model: {self.model}"
        )

        self.model_label.pack(
            side="right"
        )

        # ----------------------------------------------------
        # Output section
        # ----------------------------------------------------

        output_frame = ttk.LabelFrame(
            main,
            text="Output",
            padding=10
        )

        output_frame.pack(
            fill="both",
            expand=True,
            side="top"
        )

        self.output_text = tk.Text(
            output_frame,
            wrap="word",
            font=("Segoe UI", 10)
        )
        self.configure_rich_text(
            self.output_text
        )
        self.output_text.bind(
            "<FocusIn>",
            self.edit_output_text
        )
        self.output_text.bind(
            "<FocusOut>",
            self.render_output_text
        )

        self.output_text.pack(
            side="left",
            fill="both",
            expand=True
        )

        output_scroll = ttk.Scrollbar(
            output_frame,
            orient="vertical",
            command=self.output_text.yview
        )

        output_scroll.pack(
            side="right",
            fill="y"
        )

        self.output_text.configure(
            yscrollcommand=output_scroll.set
        )

    def configure_rich_text(
        self,
        widget: tk.Text
    ):
        """
        Configurează taguri vizuale pentru Markdown simplu.
        """

        self.apply_text_zoom(widget)

        widget.bind(
            "<Control-MouseWheel>",
            self.zoom_text_areas
        )

        widget.bind(
            "<Control-Button-4>",
            self.zoom_text_areas
        )

        widget.bind(
            "<Control-Button-5>",
            self.zoom_text_areas
        )

    def apply_text_zoom(
        self,
        widget: tk.Text
    ):
        """
        Aplică dimensiunea curentă a fontului pe zona text și taguri.
        """

        size = self.text_zoom_size

        body_font = tkfont.Font(
            family="Segoe UI",
            size=size
        )
        bold_font = tkfont.Font(
            family="Segoe UI",
            size=size,
            weight="bold"
        )
        italic_font = tkfont.Font(
            family="Segoe UI",
            size=size,
            slant="italic"
        )
        h1_font = tkfont.Font(
            family="Segoe UI",
            size=size + 5,
            weight="bold"
        )
        h2_font = tkfont.Font(
            family="Segoe UI",
            size=size + 3,
            weight="bold"
        )
        h3_font = tkfont.Font(
            family="Segoe UI",
            size=size + 1,
            weight="bold"
        )

        widget._rich_text_fonts = (
            body_font,
            bold_font,
            italic_font,
            h1_font,
            h2_font,
            h3_font
        )

        widget.configure(
            font=body_font
        )

        widget.tag_configure(
            "h1",
            font=h1_font,
            spacing1=10,
            spacing3=6
        )

        widget.tag_configure(
            "h2",
            font=h2_font,
            spacing1=8,
            spacing3=5
        )

        widget.tag_configure(
            "h3",
            font=h3_font,
            spacing1=6,
            spacing3=4
        )

        widget.tag_configure(
            "bold",
            font=bold_font
        )

        widget.tag_configure(
            "italic",
            font=italic_font
        )

        widget.tag_configure(
            "body",
            spacing1=2,
            spacing3=2
        )

        widget.tag_configure(
            "list",
            lmargin1=0,
            lmargin2=0,
            spacing1=2,
            spacing3=2
        )

        widget.tag_configure(
            "rule",
            foreground="#777777",
            spacing1=4,
            spacing3=4
        )

    def zoom_text_areas(self, event):
        """
        Ctrl + rotița mouse-ului mărește sau micșorează Prompt și Output.
        """

        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            delta = 1
        else:
            delta = -1

        new_size = max(
            8,
            min(
                24,
                self.text_zoom_size + delta
            )
        )

        if new_size == self.text_zoom_size:
            return "break"

        self.text_zoom_size = new_size

        self.apply_text_zoom(
            self.prompt_text
        )
        self.apply_text_zoom(
            self.output_text
        )

        return "break"

    def set_rich_text(
        self,
        widget: tk.Text,
        text: str
    ):
        """
        Înlocuiește conținutul și aplică formatarea vizuală.
        """

        widget.delete(
            "1.0",
            tk.END
        )

        self.insert_rich_text(
            widget,
            text
        )

    def set_plain_text(
        self,
        widget: tk.Text,
        text: str
    ):
        """
        Înlocuiește conținutul fără să modifice textul original.
        """

        widget.delete(
            "1.0",
            tk.END
        )

        widget.insert(
            "1.0",
            text
        )

    def set_prompt_text(
        self,
        text: str,
        render: bool = True
    ):
        """
        Păstrează sursa promptului și afișează opțional varianta formatată.
        """

        self.prompt_raw_text = text

        if render and text:
            self.set_rich_text(
                self.prompt_text,
                text
            )
            self.prompt_is_rendered = True
            return

        self.set_plain_text(
            self.prompt_text,
            text
        )
        self.prompt_is_rendered = False

    def get_prompt_text(self) -> str:
        """
        Returnează promptul sursă, nu textul curățat pentru afișare.
        """

        if self.prompt_is_rendered:
            return self.prompt_raw_text.strip()

        return self.prompt_text.get(
            "1.0",
            tk.END
        ).strip()

    def edit_prompt_text(self, _event=None):
        """
        La editare, arată Markdown-ul original.
        """

        if not self.prompt_is_rendered:
            return

        self.set_plain_text(
            self.prompt_text,
            self.prompt_raw_text
        )
        self.prompt_is_rendered = False

    def render_prompt_text(self, _event=None):
        """
        La ieșirea din câmp, păstrează sursa și afișează formatat.
        """

        if self.prompt_is_rendered:
            return

        text = self.prompt_text.get(
            "1.0",
            tk.END
        ).strip()

        self.set_prompt_text(
            text,
            render=True
        )

    def set_output_text(
        self,
        text: str,
        render: bool = True,
        saveable: bool = True
    ):
        """
        Păstrează sursa outputului și afișează opțional varianta formatată.
        """

        self.response_text = text if saveable else ""

        if render and text:
            self.set_rich_text(
                self.output_text,
                text
            )
            self.output_is_rendered = saveable
        else:
            self.set_plain_text(
                self.output_text,
                text
            )
            self.output_is_rendered = False

        self.update_save_button_state()

    def get_output_text(self) -> str:
        """
        Returnează outputul sursă, inclusiv modificările utilizatorului.
        """

        if self.output_is_rendered:
            return self.response_text.strip()

        return self.output_text.get(
            "1.0",
            tk.END
        ).strip()

    def edit_output_text(self, _event=None):
        """
        La editare, arată textul original al rezultatului.
        """

        if not self.output_is_rendered:
            return

        self.set_plain_text(
            self.output_text,
            self.response_text
        )
        self.output_is_rendered = False

    def render_output_text(self, _event=None):
        """
        La ieșirea din câmp, păstrează modificările și afișează formatat.
        """

        if self.output_is_rendered:
            return

        text = self.output_text.get(
            "1.0",
            tk.END
        ).strip()

        if not text:
            self.set_output_text(
                "",
                render=False,
                saveable=False
            )
            return

        self.set_output_text(
            text,
            render=True,
            saveable=True
        )

    def insert_rich_text(
        self,
        widget: tk.Text,
        text: str
    ):
        """
        Redă un subset mic de Markdown în tk.Text.
        """

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()

            if not stripped:
                widget.insert(
                    tk.END,
                    "\n"
                )
                continue

            # Preserve leading spaces for indentation
            leading_spaces = len(line) - len(line.lstrip())

            if re.fullmatch(r"[-*_]{3,}", stripped):
                if leading_spaces > 0:
                    widget.insert(
                        tk.END,
                        " " * leading_spaces
                    )
                widget.insert(
                    tk.END,
                    "------------------------------\n",
                    ("rule",)
                )
                continue

            heading = re.match(
                r"^(#{1,3})\s+(.*)$",
                stripped
            )

            if heading:
                if leading_spaces > 0:
                    widget.insert(
                        tk.END,
                        " " * leading_spaces
                    )
                level = len(heading.group(1))
                tag = f"h{level}"
                self.insert_inline_rich_text(
                    widget,
                    heading.group(2).strip(),
                    (tag,)
                )
                widget.insert(
                    tk.END,
                    "\n"
                )
                continue

            list_item = re.match(
                r"^([-*+]|\d+[.)])\s+(.*)$",
                stripped
            )

            if list_item:
                if leading_spaces > 0:
                    widget.insert(
                        tk.END,
                        " " * leading_spaces
                    )
                marker = list_item.group(1)
                if marker in {"*", "+"}:
                    marker = "-"

                widget.insert(
                    tk.END,
                    f"{marker} ",
                    ("list",)
                )
                self.insert_inline_rich_text(
                    widget,
                    list_item.group(2).strip(),
                    ("list",)
                )
                widget.insert(
                    tk.END,
                    "\n"
                )
                continue

            if leading_spaces > 0:
                widget.insert(
                    tk.END,
                    " " * leading_spaces
                )
            self.insert_inline_rich_text(
                widget,
                stripped,
                ("body",)
            )
            widget.insert(
                tk.END,
                "\n"
            )

    def insert_inline_rich_text(
        self,
        widget: tk.Text,
        text: str,
        base_tags: tuple[str, ...]
    ):
        """
        Aplică bold și italic pentru Markdown inline simplu.
        """

        pattern = re.compile(
            r"(\*\*|__)(.+?)\1|(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)"
        )
        cursor = 0

        for match in pattern.finditer(text):
            if match.start() > cursor:
                widget.insert(
                    tk.END,
                    text[cursor:match.start()],
                    base_tags
                )

            if match.group(1):
                formatted_text = match.group(2)
                formatted_tags = base_tags + ("bold",)
            elif match.group(3) is not None:
                formatted_text = match.group(3)
                formatted_tags = base_tags + ("italic",)
            else:
                formatted_text = match.group(4)
                formatted_tags = base_tags + ("italic",)

            widget.insert(
                tk.END,
                formatted_text,
                formatted_tags
            )

            cursor = match.end()

        if cursor < len(text):
            widget.insert(
                tk.END,
                text[cursor:],
                base_tags
            )

    # ========================================================
    # PROMPTS
    # ========================================================

    def load_default_prompt(self):
        """
        Încarcă automat prompts/default.txt la pornirea aplicației.
        """

        prompt_path = PROMPTS_DIR / "default.txt"

        prompt = load_prompt_file(
            prompt_path
        )

        if prompt:
            self.set_prompt_text(
                prompt
            )


    def extract_location_from_description(self, image_path: Path) -> str | None:
        """
        Extrage locația manuală din fișierul _description dacă există.
        Returnează None dacă nu există sau dacă nu este locație manuală.
        """
        description_path = OUTPUT_DIR / f"{image_path.stem}_description.txt"
        
        if not description_path.is_file():
            return None
        
        try:
            content = description_path.read_text(encoding="utf-8")
            
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("Location:") and "(manual)" in line:
                    # Extrage locația fără "(manual)"
                    location = line.replace("Location:", "").strip().replace("(manual)", "").strip()
                    return location
                    
        except Exception:
            pass
            
        return None


    def extract_prompt_from_description(self, image_path: Path) -> str | None:
        """
        Extrage promptul din fișierul _description dacă există.
        Returnează None dacă nu există.
        """
        description_path = OUTPUT_DIR / f"{image_path.stem}_description.txt"
        
        if not description_path.is_file():
            return None
        
        try:
            content = description_path.read_text(encoding="utf-8")
            
            lines = content.splitlines()
            prompt_lines = []
            in_prompt_section = False
            
            for line in lines:
                if line.strip() == "=== PROMPT ===":
                    in_prompt_section = True
                    continue
                elif line.strip() == "=== RESPONSE ===":
                    break
                elif in_prompt_section:
                    prompt_lines.append(line)
                    
            if prompt_lines:
                return "\n".join(prompt_lines).strip()
                    
        except Exception:
            pass
            
        return None


    def extract_preset_name_from_description(self, image_path: Path) -> str | None:
        """
        Extrage numele preset-ului din fișierul _description dacă există.
        Returnează None dacă nu există.
        """
        description_path = OUTPUT_DIR / f"{image_path.stem}_description.txt"
        
        if not description_path.is_file():
            return None
        
        try:
            content = description_path.read_text(encoding="utf-8")
            
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("Preset:"):
                    preset_name = line.replace("Preset:", "").strip()
                    return preset_name
                    
        except Exception:
            pass
            
        return None


    # ========================================================
    # IMAGES
    # ========================================================

    def add_images(self):

        paths = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[
                (
                    "Image files",
                    "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"
                ),
                (
                    "All files",
                    "*.*"
                ),
            ]
        )

        if not paths:
            return

        for path in paths:

            path = Path(path)

            if path not in self.image_paths:
                self.image_paths.append(path)

        self.refresh_image_list()

        if self.image_paths:
            self.select_image(0)


    def add_folder(self):

        folder = filedialog.askdirectory(
            title="Select image folder"
        )

        if not folder:
            return

        folder = Path(folder)

        extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".bmp",
            ".tif",
            ".tiff",
        }

        paths = sorted(
            path
            for path in folder.iterdir()
            if path.is_file()
            and path.suffix.lower() in extensions
        )

        added = 0

        for path in paths:

            if path not in self.image_paths:

                self.image_paths.append(path)
                added += 1

        self.refresh_image_list()

        if self.image_paths:

            self.select_image(0)

        self.set_status(
            f"Added {added} image(s)"
        )


    def refresh_image_list(self):

        self.image_listbox.delete(
            0,
            tk.END
        )

        for path in self.image_paths:

            status = self.image_status.get(
                path
            )

            if status is None:

                output_path = create_output_path(
                    OUTPUT_DIR,
                    path,
                    suffix="_description"
                )

                if output_path.exists():
                    status = "done"
                else:
                    status = ""

            if status == "done":
                prefix = "✓ "

            elif status == "processing":
                prefix = "... "

            elif status == "error":
                prefix = "✗ "

            else:
                prefix = "   "

            self.image_listbox.insert(
                tk.END,
                prefix + path.name
            )


    def select_image(self, index: int):

        if not self.image_paths:
            return

        if index < 0 or index >= len(self.image_paths):
            return

        self.image_listbox.selection_clear(
            0,
            tk.END
        )

        self.image_listbox.selection_set(
            index
        )

        self.image_listbox.see(
            index
        )

        self.load_selected_image(
            self.image_paths[index]
        )


    def on_image_selected(self, event=None):

        selection = self.image_listbox.curselection()

        if not selection:
            return

        index = selection[0]

        self.load_selected_image(
            self.image_paths[index]
        )


    def load_selected_image(self, path: Path):

        try:

            self.image_path = path
            
            # ------------------------------------------------
            # Manual location for this image
            # ------------------------------------------------

            # Încearcă să încarci din fișierul _description
            saved_location = self.extract_location_from_description(path)
            
            if saved_location:
                # Salvează în dicționar pentru utilizare ulterioară
                self.image_locations[path] = saved_location
            else:
                # Fallback la dicționar sau la București
                saved_location = self.image_locations.get(
                    path,
                    "București"
                )

            if saved_location in ROMANIAN_COUNTIES:
                self.location_var.set(
                    saved_location
                )
                self.custom_location_var.set("")
                self.custom_location_frame.pack_forget()
            else:
                self.location_var.set("__ALTCEVA__")
                self.custom_location_var.set(
                    saved_location
                )
                self.custom_location_frame.pack(
                    anchor="w"
                )
            
            # ------------------------------------------------
            # Metadata
            # ------------------------------------------------

            self.image_metadata = get_image_metadata(
                path
            )

            # ------------------------------------------------
            # Photo Info
            # ------------------------------------------------

            photo_date = self.image_metadata.get(
                "photo_date"
            )

            camera_make = self.image_metadata.get(
                "camera_make"
            )

            camera_model = self.image_metadata.get(
                "camera_model"
            )

            latitude = self.image_metadata.get(
                "latitude"
            )

            longitude = self.image_metadata.get(
                "longitude"
            )

            self.photo_file_label.configure(
                text=f"File: {path.name}"
            )

            self.photo_date_label.configure(
                text=f"Date: {photo_date or '—'}"
            )

            self.photo_camera_label.configure(
                text=f"Camera: {camera_make or '—'}"
            )

            self.photo_model_label.configure(
                text=f"Model: {camera_model or '—'}"
            )

            if (
                latitude is not None
                and longitude is not None
            ):
                location_text = (
                    f"{latitude:.6f}, {longitude:.6f}"
                )
            else:
                location_text = "—"

            self.photo_location_label.configure(
                text=f"Location: {location_text}"
            )

            # ------------------------------------------------
            # Base64
            # ------------------------------------------------

            self.image_base64 = image_to_base64(
                path
            )

            # ------------------------------------------------
            # Preview
            # ------------------------------------------------

            with Image.open(path) as image:

                image.thumbnail(
                    (500, 250)
                )

                preview = image.copy()

            self.preview_image = ImageTk.PhotoImage(
                preview
            )

            self.preview_label.configure(
                image=self.preview_image,
                text=""
            )

            self.set_status(
                f"Selected: {path.name}"
            )
            
            self.load_saved_result(path)
            
            # ------------------------------------------------
            # Load prompt from description file if exists
            # ------------------------------------------------
            
            saved_prompt = self.extract_prompt_from_description(path)
            if saved_prompt:
                self.set_prompt_text(saved_prompt)
            else:
                self.load_default_prompt()
            
            # ------------------------------------------------
            # Load preset name from description file if exists
            # ------------------------------------------------
            
            saved_preset_name = self.extract_preset_name_from_description(path)
            if saved_preset_name and saved_preset_name in self.prompt_combo['values']:
                self.prompt_var.set(saved_preset_name)
            elif "default" in self.prompt_combo['values']:
                self.prompt_var.set("default")

        except Exception as exc:

            self.image_path = None
            self.image_base64 = None

            messagebox.showerror(
                "Image error",
                str(exc)
            )


    def remove_selected_image(self):

        selection = self.image_listbox.curselection()

        if not selection:
            return

        index = selection[0]
        
        path = self.image_paths[index]

        self.image_locations.pop(
            path,
            None
        )

        del self.image_paths[index]        

        self.refresh_image_list()

        if self.image_paths:

            new_index = min(
                index,
                len(self.image_paths) - 1
            )

            self.select_image(
                new_index
            )

        else:

            self.image_path = None
            self.image_base64 = None
            self.thinking_text = ""

            self.preview_label.configure(
                image="",
                text="No image selected"
            )

            self.set_output_text(
                "",
                render=False,
                saveable=False
            )

            self.set_status(
                "No images"
            )


    def clear_images(self):

        self.image_paths.clear()
        self.image_locations.clear()

        self.image_path = None
        self.image_base64 = None
        self.thinking_text = ""

        self.image_listbox.delete(
            0,
            tk.END
        )

        self.preview_label.configure(
            image="",
            text="No image selected"
        )

        self.set_status(
            "Images cleared"
        )

        self.set_output_text(
            "",
            render=False,
            saveable=False
        )


    def batch_status(
        self,
        current,
        total,
        filename
    ):

        self.progress.stop()

        self.progress.configure(
            mode="indeterminate"
        )

        self.progress.start(
            200
        )

        self.batch_progress.configure(
            mode="determinate",
            maximum=total,
            value=current + 1
        )

        self.batch_progress_label.configure(
            text=f"Batch: {current} / {total}"
        )

        self.batch_current = current
        self.batch_filename = filename
        self.update_status_with_time()


    def batch_item_error(
        self,
        current,
        total,
        filename,
        error
    ):

        self.progress.stop()

        self.progress.configure(
            mode="indeterminate"
        )

        self.progress.start(
            200
        )

        self.batch_progress.configure(
            mode="determinate",
            maximum=total,
            value=current + 1
        )

        self.batch_progress_label.configure(
            text=f"Batch: {current} / {total}"
        )

        self.set_output_text(
            f"ERROR\n\n{filename}\n\n{error}",
            saveable=False
        )

        self.set_status(
            f"Error {current} / {total}: {filename}"
        )


    def batch_item_finished(
        self,
        current,
        total,
        filename,
        response
    ):

        self.progress.stop()

        self.progress.configure(
            mode="indeterminate"
        )

        self.progress.start(
            200
        )

        self.batch_progress.configure(
            mode="determinate",
            maximum=total,
            value=current + 1
        )

        self.batch_progress_label.configure(
            text=f"Batch: {current} / {total}"
        )

        self.set_output_text(
            response
        )

        self.set_status(
            f"Completed {current} / {total}: {filename}"
        )


    def batch_finished(
        self,
        total,
        completed,
        errors,
        elapsed
    ):

        self.stop_status_timer()
        self.analysis_start_time = None
        self.batch_current = 0
        self.batch_total = 0

        self.progress.stop()

        self.batch_progress.configure(
            mode="determinate",
            maximum=total,
            value=total
        )

        self.batch_progress_label.configure(
            text=f"Batch: {total} / {total}"
        )

        self.batch_progress_frame.pack_forget()

        self.progress.pack(
            side="right"
        )

        # ----------------------------------------------------
        # Re-enable controls
        # ----------------------------------------------------

        self.analyze_button.configure(
            state="normal"
        )

        self.analyze_all_button.configure(
            state="normal"
        )

        self.add_images_button.configure(
            state="normal"
        )

        self.add_folder_button.configure(
            state="normal"
        )

        self.remove_image_button.configure(
            state="normal"
        )

        self.clear_images_button.configure(
            state="normal"
        )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        duration = self.format_seconds(
            elapsed
        )

        if errors:

            self.set_status(
                f"Batch finished: {completed}/{total}, "
                f"errors: {len(errors)} — "
                f"{duration}"
            )

            error_text = "\n".join(
                errors
            )

            messagebox.showwarning(
                "Batch finished with errors",
                f"Completed: {completed}/{total}\n\n"
                f"Errors: {len(errors)}\n\n"
                f"Total duration: {duration}\n\n"
                f"{error_text}"
            )

        else:

            self.set_status(
                f"Batch completed: {completed}/{total} — "
                f"{duration}"
            )

            messagebox.showinfo(
                "Batch complete",
                f"All {total} images were analyzed successfully.\n\n"
                f"Total duration: {duration}"
            )


    def load_image(self, path: Path):

        try:

            self.image_path = path

            self.image_entry.delete(
                0,
                tk.END
            )

            self.image_entry.insert(
                0,
                str(path)
            )

            # -----------------------------------------------
            # Metadata
            # -----------------------------------------------

            self.image_metadata = get_image_metadata(
                path
            )

            # -----------------------------------------------
            # Base64
            # -----------------------------------------------

            self.image_base64 = image_to_base64(
                path
            )

            # -----------------------------------------------
            # Preview
            # -----------------------------------------------

            with Image.open(path) as image:

                image.thumbnail(
                    (500, 250)
                )

                preview = image.copy()

            self.preview_image = ImageTk.PhotoImage(
                preview
            )

            self.preview_label.configure(
                image=self.preview_image,
                text=""
            )

            self.set_status(
                f"Loaded: {path.name}"
            )

        except Exception as exc:

            self.image_path = None
            self.image_base64 = None

            messagebox.showerror(
                "Image error",
                str(exc)
            )


    def load_saved_result(self, image_path: Path):

        output_path = create_output_path(
            OUTPUT_DIR,
            image_path,
            suffix="_description"
        )

        if not output_path.exists():
            self.thinking_text = ""

            self.set_output_text(
                "No saved result for this image.",
                saveable=False
            )
            return

        try:
            text = output_path.read_text(
                encoding="utf-8"
            )

            # ------------------------------------------------
            # Extract RESPONSE section
            # ------------------------------------------------

            response = text

            marker_start = "=== RESPONSE ==="

            if marker_start in text:

                response = text.split(
                    marker_start,
                    1
                )[1]

                next_section = re.search(
                    r"\n=== [A-Z ]+ ===",
                    response
                )

                if next_section:
                    response = response[
                        :next_section.start()
                    ]

                response = response.strip()

            # ------------------------------------------------
            # Display only response
            # ------------------------------------------------

            self.thinking_text = ""

            self.set_output_text(
                response
            )

        except Exception as exc:

            self.thinking_text = ""

            self.set_output_text(
                f"Could not load saved result:\n\n{exc}",
                saveable=False
            )


    def build_analysis_prompt(
        self,
        prompt: str,
        metadata: dict,
        manual_location: str = ""
    ) -> str:
        """
        Construiește promptul final trimis modelului,
        adăugând contextul disponibil al fotografiei.

        Contextul poate conține:
        - data fotografierii
        - producătorul camerei
        - modelul camerei
        - coordonate GPS
        - locație introdusă manual

        Metadata este folosită ca informație contextuală pentru
        evaluarea plauzibilității identificării, nu ca dovadă vizuală.

        Imaginea rămâne sursa principală pentru identificare.
        """

        metadata = metadata or {}

        photo_date = metadata.get(
            "photo_date"
        )

        camera_make = metadata.get(
            "camera_make"
        )

        camera_model = metadata.get(
            "camera_model"
        )

        latitude = metadata.get(
            "latitude"
        )

        longitude = metadata.get(
            "longitude"
        )

        manual_location = (
            manual_location or ""
        ).strip()

        context_lines = [
            "=== CONTEXT FOTOGRAFIE ==="
        ]

        # ------------------------------------------------
        # Data fotografierii
        # ------------------------------------------------

        if photo_date:
            context_lines.append(
                f"Data fotografierii: {photo_date}"
            )

        # ------------------------------------------------
        # Camera
        # ------------------------------------------------

        if camera_make:
            context_lines.append(
                f"Producător cameră: {camera_make}"
            )

        if camera_model:
            context_lines.append(
                f"Model cameră: {camera_model}"
            )

        # ------------------------------------------------
        # Locație
        # ------------------------------------------------

        if (
            latitude is not None
            and longitude is not None
        ):
            context_lines.append(
                f"Locație GPS: {latitude:.6f}, {longitude:.6f}"
            )

        elif manual_location:
            context_lines.append(
                f"Locație: {manual_location} (introdusă manual)"
            )

        # ------------------------------------------------
        # Dacă nu există context
        # ------------------------------------------------

        if len(context_lines) == 1:
            return prompt

        # ------------------------------------------------
        # Reguli pentru folosirea contextului
        # ------------------------------------------------

        context_lines.extend([
            "",
            "Folosește aceste informații ca date contextuale "
            "pentru evaluarea plauzibilității identificării.",
            "",
            "Data fotografierii poate fi folosită pentru a ține "
            "cont de sezon și de perioada în care anumite specii "
            "pot fi întâlnite.",
            "",
            "Locația poate fi folosită pentru a ține cont de "
            "distribuția geografică și de speciile plauzibile "
            "în zona respectivă.",
            "",
            "NU considera aceste informații drept dovezi vizuale.",
            "NU afirma că data, locația sau datele camerei sunt "
            "vizibile în fotografie.",
            "",
            "Identificarea trebuie să se bazeze în primul rând "
            "pe caracteristicile observabile în imagine.",
            "",
            "Dacă informațiile contextuale sugerează o identificare "
            "diferită de ceea ce este vizibil în imagine, acordă "
            "prioritate caracteristicilor vizibile și menționează "
            "incertitudinea atunci când este relevant.",
            "",
            "=== INSTRUCȚIUNEA UTILIZATORULUI ==="
        ])

        return (
            "\n".join(context_lines)
            + "\n"
            + prompt
        )


    def on_location_selected(self, event=None):

        if self.image_path is None:
            return

        location = self.location_var.get().strip()

        if location == "__ALTCEVA__":
            self.custom_location_frame.pack(
                anchor="w"
            )
            self.custom_location_entry.focus_set()

            custom_location = self.custom_location_var.get().strip()

            if custom_location:
                self.image_locations[
                    self.image_path
                ] = custom_location

            return

        self.custom_location_frame.pack_forget()
        self.custom_location_var.set("")

        self.image_locations[
            self.image_path
        ] = location


    def on_custom_location_changed(self, event=None):

        if self.image_path is None:
            return

        custom_location = self.custom_location_var.get().strip()

        if self.location_var.get().strip() != "__ALTCEVA__":
            return

        if custom_location:
            self.image_locations[
                self.image_path
            ] = custom_location


    # ========================================================
    # ANALYSIS
    # ========================================================

    def start_analysis(self):

        self.image_status[self.image_path] = "processing"

        self.refresh_image_list()

        if self.image_path is None:
            messagebox.showwarning(
                "No image",
                "Select an image first."
            )
            return

        prompt = self.get_prompt_text()

        if not prompt:
            messagebox.showwarning(
                "No prompt",
                "Enter a prompt first."
            )
            return

        self.batch_progress_frame.pack_forget()
        self.batch_progress_label.pack_forget()

        # ----------------------------------------------------
        # Disable controls
        # ----------------------------------------------------

        self.analyze_button.configure(
            state="disabled"
        )

        self.add_images_button.configure(
            state="disabled"
        )

        self.add_folder_button.configure(
            state="disabled"
        )

        self.remove_image_button.configure(
            state="disabled"
        )

        self.clear_images_button.configure(
            state="disabled"
        )

        self.save_button.configure(
            state="disabled"
        )
        
        self.progress.pack(
            side="right"
        )        

        self.progress.start(
            200
        )

        self.analysis_start_time = time.perf_counter()
        self.set_status(
            "Muse Glimmer is working..."
        )
        self.update_status_with_time()

        # ----------------------------------------------------
        # Capture preset name
        # ----------------------------------------------------

        preset_name = self.prompt_var.get()

        # ----------------------------------------------------
        # Thread
        # ----------------------------------------------------

        thread = threading.Thread(
            target=self.run_analysis,
            args=(prompt, preset_name),
            daemon=True
        )

        thread.start()

    # --------------------------------------------------------

    def start_batch_analysis(self):

        if not self.image_paths:
            messagebox.showwarning(
                "No images",
                "Add at least one image first."
            )
            return

        prompt = self.get_prompt_text()

        if not prompt:
            messagebox.showwarning(
                "No prompt",
                "Enter a prompt first."
            )
            return

        # ----------------------------------------------------
        # Disable controls
        # ----------------------------------------------------

        self.analyze_button.configure(
            state="disabled"
        )

        self.analyze_all_button.configure(
            state="disabled"
        )

        self.add_images_button.configure(
            state="disabled"
        )

        self.add_folder_button.configure(
            state="disabled"
        )

        self.remove_image_button.configure(
            state="disabled"
        )

        self.clear_images_button.configure(
            state="disabled"
        )

        self.save_button.configure(
            state="disabled"
        )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        total = len(self.image_paths)

        # Current image progress
        self.progress.pack(
            side="right"
        )

        self.progress.configure(
            mode="indeterminate"
        )

        self.progress.start(
            200
        )

        # Batch progress
        self.batch_progress.configure(
            mode="determinate",
            maximum=total,
            value=0
        )

        self.batch_progress_label.configure(
            text=f"Batch: 0 / {total}"
        )

        self.batch_progress_frame.pack(
            side="right",
            padx=(0, 8)
        )

        self.batch_total = total
        self.batch_current = 0
        self.analysis_start_time = time.perf_counter()
        self.set_status(
            f"Processing batch: 0 / {total}"
        )
        self.update_status_with_time()

        # ----------------------------------------------------
        # Snapshot of the list and preset
        # ----------------------------------------------------

        paths = list(
            self.image_paths
        )

        preset_name = self.prompt_var.get()

        # ----------------------------------------------------
        # Start worker
        # ----------------------------------------------------

        thread = threading.Thread(
            target=self.run_batch_analysis,
            args=(paths, prompt, preset_name),
            daemon=True
        )

        thread.start()


    def run_batch_analysis(
        self,
        paths,
        prompt,
        preset_name
    ):

        batch_start_time = time.perf_counter()
        
        total = len(paths)        

        completed = 0
        errors = []

        for index, path in enumerate(paths, start=0):

            self.image_status[path] = "processing"

            self.root.after(
                0,
                self.refresh_image_list
            )

            # Update status immediately before processing
            self.batch_current = index
            self.batch_filename = path.name
            self.root.after(
                0,
                self.batch_status,
                index,
                total,
                path.name
            )

            try:

                # ------------------------------------------------
                # Read image
                # ------------------------------------------------

                image_base64 = image_to_base64(
                    path
                )

                metadata = get_image_metadata(
                    path
                )
                
                manual_location = self.image_locations.get(
                    path,
                    "București"
                )                

                analysis_prompt = self.build_analysis_prompt(
                    prompt,
                    metadata,
                    manual_location
                )

                # ------------------------------------------------
                # Ollama
                # ------------------------------------------------

                if not check_ollama(
                    self.ollama_url
                ):
                    raise OllamaError(
                        "Ollama is not accessible."
                    )

                data = generate(
                    ollama_url=self.ollama_url,
                    model=self.model,
                    prompt=analysis_prompt,
                    image_base64=image_base64,
                    num_ctx=self.num_ctx,
                    num_predict=self.num_predict,
                    thinking=self.thinking,
                )

                response = get_response(
                    data
                )

                thinking = get_thinking(
                    data
                )

                statistics = get_statistics(
                    data
                )

                # ------------------------------------------------
                # Output path
                # ------------------------------------------------

                output_path = create_output_path(
                    OUTPUT_DIR,
                    path,
                    suffix="_description"
                )

                # ------------------------------------------------
                # Save immediately
                # ------------------------------------------------

                save_result(
                    output_path=output_path,
                    response=response,
                    thinking=thinking if self.thinking else "",
                    image_name=path.name,
                    prompt=prompt,
                    model=self.model,
                    statistics=statistics,
                    image_metadata=metadata,
                    manual_location=manual_location,
                    preset_name=preset_name,
                )

                completed += 1
                
                self.image_status[path] = "done"

                self.root.after(
                    0,
                    self.refresh_image_list
                )                

                self.root.after(
                    0,
                    self.batch_item_finished,
                    index,
                    total,
                    path.name,
                    response
                )

            except Exception as exc:

                errors.append(
                    f"{path.name}: {exc}"
                )

                self.root.after(
                    0,
                    self.batch_item_error,
                    index,
                    total,
                    path.name,
                    str(exc)
                )
                
                self.image_status[path] = "error"

                self.root.after(
                    0,
                    self.refresh_image_list
                )                

        # --------------------------------------------------------
        # Batch finished
        # --------------------------------------------------------

        batch_elapsed = time.perf_counter() - batch_start_time

        self.root.after(
            0,
            self.batch_finished,
            total,
            completed,
            errors,
            batch_elapsed
        )

    def run_analysis(self, prompt: str, preset_name: str):

        start_time = time.perf_counter()

        try:

            # ------------------------------------------------
            # Ollama
            # ------------------------------------------------

            if not check_ollama(
                self.ollama_url
            ):
                raise OllamaError(
                    "Ollama is not accessible."
                )

            # ------------------------------------------------
            # Generate
            # ------------------------------------------------
           
            manual_location = self.image_locations.get(
                self.image_path,
                self.location_var.get().strip()
            )            

            analysis_prompt = self.build_analysis_prompt(
                prompt,
                self.image_metadata,
                manual_location
            )            

            data = generate(
                ollama_url=self.ollama_url,
                model=self.model,
                prompt=prompt,
                image_base64=self.image_base64,
                num_ctx=self.num_ctx,
                num_predict=self.num_predict,
                thinking=self.thinking,
            )

            # ------------------------------------------------
            # Results
            # ------------------------------------------------

            response = get_response(
                data
            )

            thinking = get_thinking(
                data
            )

            statistics = get_statistics(
                data
            )

            output_path = create_output_path(
                OUTPUT_DIR,
                self.image_path,
                suffix="_description"
            )

            save_result(
                output_path=output_path,
                response=response,
                thinking=thinking if self.thinking else "",
                image_name=self.image_path.name,
                prompt=prompt,
                model=self.model,
                statistics=statistics,
                image_metadata=self.image_metadata,
                manual_location=manual_location,
                preset_name=preset_name,
            )


            elapsed = time.perf_counter() - start_time

            self.response_text = response
            self.thinking_text = thinking
            self.statistics = statistics

            self.root.after(
                0,
                self.analysis_finished,
                response,
                elapsed,
                prompt,
                preset_name
            )

        except Exception as exc:

            self.root.after(
                0,
                self.analysis_failed,
                str(exc)
            )

    # ========================================================
    # ANALYSIS FINISHED
    # ========================================================

    def analysis_finished(
        self,
        response: str,
        elapsed: float,
        prompt: str,
        preset_name: str
    ):

        if self.image_path is not None:
            self.image_status[self.image_path] = "done"

        self.refresh_image_list()

        self.stop_status_timer()
        self.analysis_start_time = None

        self.progress.stop()
        self.progress["value"] = 0
        self.progress.pack_forget()

        self.analyze_button.configure(
            state="normal"
        )

        self.add_images_button.configure(
            state="normal"
        )

        self.add_folder_button.configure(
            state="normal"
        )

        self.remove_image_button.configure(
            state="normal"
        )

        self.clear_images_button.configure(
            state="normal"
        )

        self.save_button.configure(
            state="normal"
        )

        # ----------------------------------------------------
        # Output
        # ----------------------------------------------------

        self.set_output_text(
            response
        )

        try:
            self.save_analysis_result(response, prompt, preset_name)

        except Exception as exc:
            self.set_status(
                f"Result displayed, but could not be saved: {exc}"
            )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        self.set_status(
            f"Done — {self.format_seconds(elapsed)}"
        )

        # ----------------------------------------------------
        # Completion popup
        # ----------------------------------------------------

        messagebox.showinfo(
            "Analiză finalizată",
            f"Analiza a fost finalizată pentru:\n\n"
            f"{self.image_path.name}\n\n"
            f"Durată: {self.format_seconds(elapsed)}"
        )

    def analysis_failed(
        self,
        error
    ):

        if self.image_path is not None:
            self.image_status[self.image_path] = "error"

        self.refresh_image_list()

        self.stop_status_timer()
        self.analysis_start_time = None

        self.progress.stop()
        self.progress["value"] = 0
        self.progress.pack_forget()

        self.analyze_button.configure(
            state="normal"
        )

        self.add_images_button.configure(
            state="normal"
        )

        self.add_folder_button.configure(
            state="normal"
        )

        self.remove_image_button.configure(
            state="normal"
        )

        self.clear_images_button.configure(
            state="normal"
        )

        self.set_status(
            "Error"
        )

        messagebox.showerror(
            "Analysis failed",
            str(error)
        )

    # ========================================================
    # SAVE
    # ========================================================

    def save_analysis_result(self, response: str, prompt: str, preset_name: str):

        if self.image_path is None:
            return

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        output_path = create_output_path(
            OUTPUT_DIR,
            self.image_path,
            suffix="_description"
        )

        save_result(
            output_path=output_path,
            response=response,
            thinking=self.thinking_text if self.thinking else "",
            image_name=self.image_path.name,
            prompt=prompt,
            model=self.model,
            statistics=self.statistics,
            image_metadata=self.image_metadata,
            manual_location=self.image_locations.get(
                self.image_path,
                self.location_var.get().strip()
            ),
            preset_name=preset_name,
        )

    def save_current_result(self):

        if self.image_path is None:
            return

        response = self.get_output_text()

        if not response:
            messagebox.showwarning(
                "Nothing to save",
                "There is no result to save."
            )
            return

        prompt = self.get_prompt_text()

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        output_path = create_output_path(
            OUTPUT_DIR,
            self.image_path,
            suffix="_description"
        )

        try:

            save_result(
                output_path=output_path,
                response=response,
                thinking=self.thinking_text if self.thinking else "",
                image_name=self.image_path.name,
                prompt=prompt,
                model=self.model,
                statistics=self.statistics,
                image_metadata=self.image_metadata,
                manual_location=self.image_locations.get(
                    self.image_path,
                    self.location_var.get().strip()
                ),
                preset_name=self.prompt_var.get(),
            )

            self.set_output_text(
                response
            )

            self.set_status(
                f"Saved: {output_path.name}"
            )

        except Exception as exc:

            messagebox.showerror(
                "Save error",
                str(exc)
            )

    # ========================================================
    # STATUS
    # ========================================================

    def update_save_button_state(self):

        if not hasattr(self, "save_button"):
            return

        has_result = (
            self.image_path is not None
            and bool(self.response_text.strip())
        )

        self.save_button.configure(
            state="normal" if has_result else "disabled"
        )

    def set_status(self, text: str):

        self.status_label.configure(
            text=text
        )

    def update_status_with_time(self):
        """
        Update status with elapsed time every 1 second.
        Constructs message dynamically based on current state.
        """
        if self.analysis_start_time is None:
            return

        # Stop any existing timer before starting a new one
        if self.status_update_timer:
            self.root.after_cancel(self.status_update_timer)
            self.status_update_timer = None

        elapsed = time.perf_counter() - self.analysis_start_time
        elapsed_str = self.format_seconds(elapsed)

        # Construct message dynamically for batch mode
        if self.batch_total > 0:
            if self.batch_filename:
                base_message = f"Processing {self.batch_current} / {self.batch_total}: {self.batch_filename}"
            else:
                base_message = f"Processing batch: {self.batch_current} / {self.batch_total}"
        else:
            base_message = "Muse Glimmer is working"

        self.set_status(f"{base_message} — {elapsed_str}")

        # Schedule next update in 1 second
        self.status_update_timer = self.root.after(
            1000,
            self.update_status_with_time
        )

    def stop_status_timer(self):
        """
        Stop the status update timer.
        """
        if self.status_update_timer:
            self.root.after_cancel(self.status_update_timer)
            self.status_update_timer = None

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def format_seconds(seconds: float) -> str:

        if seconds < 60:
            return f"{seconds:.1f}s"

        minutes = int(seconds // 60)
        remaining = seconds % 60

        if minutes < 60:
            return f"{minutes}m {remaining:.1f}s"

        hours = int(minutes // 60)
        minutes = minutes % 60

        return (
            f"{hours}h "
            f"{minutes}m "
            f"{remaining:.1f}s"
        )

    def populate_prompt_list(self):
        """
        Găsește toate fișierele .txt din prompts/
        și le pune în selector.
        """

        PROMPTS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        prompt_files = sorted(
            PROMPTS_DIR.glob("*.txt")
        )

        names = [
            path.stem
            for path in prompt_files
        ]

        self.prompt_files = {
            path.stem: path
            for path in prompt_files
        }

        self.prompt_combo["values"] = names

        if "default" in names:
            self.prompt_var.set("default")

        elif names:
            self.prompt_var.set(names[0])

    def load_selected_prompt(self):
        """
        Încarcă promptul selectat în editor.
        """

        name = self.prompt_var.get()

        if not name:
            return

        prompt_path = self.prompt_files.get(name)

        if not prompt_path:
            return

        prompt = load_prompt_file(
            prompt_path
        )

        self.set_prompt_text(
            prompt
        )

        self.set_status(
            f"Prompt loaded: {name}"
        )

    def on_prompt_selected(self, event=None):
        """
        Când utilizatorul selectează un prompt,
        îl încărcăm automat.
        """

        self.load_selected_prompt()

    def update_prompt(self):

        name = self.prompt_var.get().strip()

        if not name:
            messagebox.showwarning(
                "No prompt selected",
                "Select a prompt first."
            )
            return

        prompt_path = self.prompt_files.get(name)

        if not prompt_path:
            messagebox.showerror(
                "Prompt error",
                f"Could not find the file for prompt: {name}"
            )
            return

        prompt = self.get_prompt_text()

        if not prompt:
            messagebox.showwarning(
                "Empty prompt",
                "The prompt cannot be empty."
            )
            return

        try:

            save_prompt(
                prompt_path,
                prompt
            )

            self.set_status(
                f"Prompt updated: {name}"
            )

        except Exception as exc:

            messagebox.showerror(
                "Update prompt error",
                str(exc)
            )

    def new_prompt(self):

        name = simpledialog.askstring(
            "New Prompt",
            "Enter prompt name:"
        )

        if name is None:
            return

        name = name.strip()

        if not name:
            messagebox.showwarning(
                "Invalid name",
                "The prompt name cannot be empty."
            )
            return

        if not name.endswith(".txt"):
            filename = f"{name}.txt"
        else:
            filename = name

        prompt_path = PROMPTS_DIR / filename

        if prompt_path.exists():
            messagebox.showwarning(
                "Prompt already exists",
                f"The prompt '{name}' already exists."
            )
            return

        try:

            prompt_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            prompt_path.write_text(
                "",
                encoding="utf-8"
            )

        except Exception as exc:

            messagebox.showerror(
                "Create prompt error",
                str(exc)
            )

            return

        self.populate_prompt_list()

        prompt_name = prompt_path.stem

        self.prompt_var.set(
            prompt_name
        )

        self.set_prompt_text(
            ""
        )

        self.set_status(
            f"New prompt created: {prompt_name}"
        )
        

# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():

    root = tk.Tk()

    MainWindow(root)

    root.mainloop()


if __name__ == "__main__":
    main()
