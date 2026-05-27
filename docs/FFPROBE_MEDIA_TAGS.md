# ffprobe Media Tag Scanning

`ffprobe` is optional. Jellyfin Episode Renamer works without it, but the GUI feature **Scan Media Tags** uses `ffprobe` to inspect video files and detect tags such as:

```text
2160p HDR HEVC EAC3
```

The project does not bundle FFmpeg or ffprobe. Install it separately and make sure `ffprobe` is available in your terminal.

## Quick Check

Check whether `ffprobe` is already installed:

```bash
ffprobe -version
```

If the command prints a version number, the scan feature can use it.

## macOS

The simplest option is Homebrew. Install Homebrew first from:

```text
https://brew.sh
```

Then install FFmpeg:

```bash
brew install ffmpeg
ffprobe -version
```

## Windows

Recommended beginner-friendly option:

1. Download a Windows FFmpeg build from:

```text
https://www.gyan.dev/ffmpeg/builds/
```

2. Choose a release build, for example `ffmpeg-release-essentials.zip`.
3. Extract it to a stable folder, for example:

```text
C:\Tools\ffmpeg
```

4. Add the `bin` folder to your Windows `Path`.

Example final path:

```text
C:\Tools\ffmpeg\bin
```

5. Open a new PowerShell window and test:

```powershell
ffprobe -version
```

If Windows says the command is unknown, the `bin` folder is not in `Path` yet or the terminal was opened before the `Path` change.

Alternative for users with package managers:

```powershell
winget install Gyan.FFmpeg
ffprobe -version
```

## Linux

Install FFmpeg through your distribution package manager.

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install ffmpeg
ffprobe -version
```

Fedora:

```bash
sudo dnf install ffmpeg
ffprobe -version
```

Arch Linux:

```bash
sudo pacman -S ffmpeg
ffprobe -version
```

## Scan Workflow

After `ffprobe` is installed:

1. Start the GUI.
2. Choose a movie or show folder.
3. Click **Preview**.
4. Click **Scan Media Tags**.
5. Keep **Use scanned tags** enabled.

Example output name:

```text
John Wick (2014) - 2160p HDR HEVC EAC3 Remote.mkv
```

Detected tags are cached in:

```text
media-tag-cache.json
```

Delete that file if you want the renamer to forget old scan results.
