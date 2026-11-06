# gallery-dl Desktop

An unofficial Windows app powered by [gallery-dl](https://codeberg.org/mikf/gallery-dl) and [yt-dlp](https://github.com/yt-dlp/yt-dlp). Save images and videos from supported sites or extract images from individual web pages.

## Install

Requires Windows 10/11, an internet connection, WinGet, and Google Chrome, Microsoft Edge, or Brave.

1. Download and extract this repository.
2. Run `INSTALL.bat` to prepare the local `.venv` and required tools.
3. Launch `RUN.vbs` or the **gallery-dl Desktop** shortcut.

The app uses your installed browser; it does not download another copy.

## Use

Paste one or more URLs, choose **Save to** and **Folder**, select **Images**, **Videos**, or both, then click **Download**.

Only **Images** is selected by default. Separate `Images` and `Videos` folders are the default; existing localized folders are reused. Choose **All in one folder** to keep everything together.

For Instagram, sign in through the browser window if prompted. Sessions are kept locally in `.browser-profile`; keep this folder private. Site access restrictions still apply.

## Update and troubleshoot

- **Update** refreshes the app, both download engines, and dependencies, then verifies them.
- Run `INSTALL.bat` again to check and update required tools.
- Use `INSTALL.bat --check` for a read-only requirements check.
- Use `RUN_DEBUG.cmd` if the app does not start.

Download only content you are authorized to save.
