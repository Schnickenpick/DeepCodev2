# DeepCode

Free AI in your terminal. 34 models, no account, no API key, no limits.

```
  ██████╗ ███████╗███████╗██████╗      ██████╗ ██████╗ ██████╗ ███████╗
  ██╔══██╗██╔════╝██╔════╝██╔══██╗    ██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║  ██║█████╗  █████╗  ██████╔╝    ██║     ██║   ██║██║  ██║█████╗
  ██║  ██║██╔══╝  ██╔══╝  ██╔═══╝     ██║     ██║   ██║██║  ██║██╔══╝
  ██████╔╝███████╗███████╗██║         ╚██████╗╚██████╔╝██████╔╝███████╗
  ╚═════╝ ╚══════╝╚══════╝╚═╝          ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
```

## Install (Windows)

1. Download `deepcode.exe` and `install.bat` from [Releases](https://github.com/Schnickenpick/DeepCodev2/releases)
2. Put both files in the same folder
3. Right-click `install.bat` → Run as Administrator
4. Open a new terminal and type `deepcode`

## Features

**34 models** — GPT-4o, Claude Opus, Gemini 2.5 Pro, Llama, Mistral, and more. Switch anytime with `/model`.

**Agent mode** — AI that can read and write files, run shell commands, and search your codebase to complete tasks autonomously. Toggle with `/agent`.

**Web search** — answers pulled live from the internet with sources. Toggle with `/search`.

**Merge AI** — sends your prompt to GPT, Claude, and Gemini simultaneously and combines the best answer. Toggle with `/merge`.

**Memory** — remembers facts about you and your projects across sessions.

**Session history** — resume past conversations with `/session`.

## Commands

| Command | Description |
|---|---|
| `/model <name>` | Switch model — e.g. `/model opus` |
| `/models` | List all 34 models |
| `/agent` | Toggle agent mode |
| `/merge` | Toggle Merge AI |
| `/search` | Toggle web search |
| `/session` | Browse and resume past conversations |
| `/new` | Start a new conversation |
| `/compact` | Summarize conversation to save context |
| `/memory` | Show remembered facts |
| `/clear` | Clear the screen |
| `/help` | Show all commands |
| `/exit` | Quit |

## Keybinds

| Key | Action |
|---|---|
| `Enter` | Send message |
| `Ctrl+J` | New line (multiline input) |
| `Tab` | Autocomplete command |
| `↑ / ↓` | Navigate history / autocomplete |
| `Ctrl+C` | Cancel / exit |

## Build from source

Requires Python 3.9+.

```
pip install httpx rich prompt_toolkit
pip install -e .
deepcode
```

To build the exe:

```
pip install pyinstaller appdirs
python -m PyInstaller deepcode.spec --clean
```

## Antivirus False Positives

Some antivirus tools flag `deepcode.exe`. These are false positives caused by PyInstaller, not malicious code.

**Why it happens:** PyInstaller bundles Python, all dependencies, and your code into a single `.exe`. The bootloader that unpacks everything at runtime looks similar to self-extracting malware to heuristic scanners — even when the code inside is completely clean.

**Specific flags explained:**

- **Software Packing** — PyInstaller compresses everything into one file. Every PyInstaller exe gets this flag.
- **QueryPerformanceCounter** — PyInstaller's bootloader uses this for timing during startup. Not VM detection, standard bootloader behavior.
- **Persistence / Privilege Escalation** — `install.bat` writes to the registry to add the install folder to PATH. That's all. Any installer does this.
- **vcruntime140.dll** — PyInstaller ships its own copy of the C++ runtime. Normal, not sideloading.
- **Bkav Pro / SecureAge flagging** — both are known for false positives on any PyInstaller binary. 67/69 vendors on VirusTotal say clean, including Windows Defender, Bitdefender, CrowdStrike, and Kaspersky.

**Verify it yourself:** The full source code is in this repo. Build it from source using the instructions above and you'll get the same exe with the same flags — because they come from PyInstaller, not the code.

## License

MIT
