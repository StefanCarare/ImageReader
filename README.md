# ImageReader - Image Analysis with AI

A Python application for analyzing images using local AI models (Ollama). Features both a GUI and CLI interface for batch and single image analysis with metadata extraction and customizable prompts.

## Features

- **GUI Interface**: User-friendly Tkinter-based interface for image analysis
- **Batch Processing**: Analyze multiple images in sequence
- **CLI Support**: Command-line interface for automation and scripting
- **Metadata Extraction**: Extract EXIF, XMP, and GPS metadata from images
- **Custom Prompts**: Create and manage custom analysis prompts
- **Preset Management**: Save and load prompt presets for different use cases
- **Real-time Status**: Live progress tracking with elapsed time display
- **Multiple Models**: Support for various Ollama models (muse-glimmer, qwen3-vl, etc.)
- **Rich Text Formatting**: Markdown-style formatting in prompt and output fields

## Requirements

- Python 3.8+
- Ollama (local AI model server)
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install and configure Ollama:
   - Download from [ollama.com](https://ollama.com)
   - Pull a vision model: `ollama pull muse-glimmer` or `ollama pull qwen3-vl:8b`
   - Start Ollama server: `ollama serve`

## Configuration

Edit `config/settings.txt` to configure:

- `OLLAMA_URL`: Ollama server URL (default: http://localhost:11434)
- `MODEL`: AI model to use (default: muse-glimmer)
- `NUM_CTX`: Context window size (default: 8192)
- `NUM_PREDICT`: Maximum tokens to generate (default: 3000)
- `THINKING`: Enable/disable thinking output (default: true)

## Usage

### GUI Mode

Run the application:
```bash
python -m gui.main_window
```

Or use the provided batch file (Windows):
```bash
run.bat
```

**Creating a Desktop Shortcut (Windows):**

To create a shortcut on your Desktop for easy access:

1. Right-click on your Desktop and select **New** → **Shortcut**
2. In the "Type the location of the item" field, enter:
   ```
   C:\path\to\ImageReader\run.bat
   ```
   (Replace `C:\path\to\ImageReader\` with the actual path to your ImageReader folder)
3. Click **Next**
4. Name the shortcut "ImageReader" and click **Finish**
5. (Optional) Right-click the shortcut → **Properties** → **Change Icon** to select a custom icon

**GUI Features:**
- Add single images or entire folders
- Select custom prompts and presets
- Enter manual location information
- View real-time analysis progress
- Save and edit analysis results
- Batch analyze multiple images

### CLI Mode

Analyze a single image:
```bash
python app.py input/image.jpg
```

Specify a custom prompt:
```bash
python app.py input/image.jpg prompts/custom.txt
```

## Project Structure

```
appAI/
├── app.py              # CLI interface
├── config/             # Configuration files
│   └── settings.txt    # Application settings
├── core/               # Core functionality
│   ├── images.py       # Image processing and metadata
│   ├── ollama.py       # Ollama API integration
│   ├── output.py       # Result saving
│   └── prompts.py      # Prompt management
├── gui/                # GUI interface
│   └── main_window.py  # Main window implementation
├── input/              # Input images directory
├── output/             # Analysis results directory
├── prompts/            # Custom prompts directory
└── logs/               # Application logs
```

## Prompts

Create custom prompts in the `prompts/` directory. Each prompt file should contain the analysis instructions in plain text or Markdown.

Example prompt:
```
Analyze this image and provide:
1. Main subject identification
2. Technical details (camera, settings)
3. Artistic composition analysis
4. Contextual information
```

## Output Format

Analysis results are saved as `_description.txt` files in the `output/` directory, containing:

- Image metadata (date, camera, GPS if available)
- Manual location information (if provided)
- Prompt used for analysis
- Model response
- Statistics (tokens, duration)
- Thinking output (if enabled)

## Keyboard Shortcuts (GUI)

- `Enter` in custom location field: Save location
- Click outside text fields: Render Markdown formatting

## Troubleshooting

**Ollama connection error:**
- Ensure Ollama server is running: `ollama serve`
- Check `OLLAMA_URL` in settings.txt

**No metadata extracted:**
- Some images may not have EXIF data
- Try different image formats (JPEG recommended)

**Slow analysis:**
- Reduce `NUM_PREDICT` in settings.txt
- Use a faster model (e.g., qwen3-vl:8b instead of muse-glimmer)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
