"""Paste a link, choose a folder, download."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from engine import folder_name_from_url, normalize_urls

APP_DIR = Path(__file__).resolve().parent
STATE_FILE = APP_DIR / '.gallery-dl-gui.json'
ICON_PNG = APP_DIR / 'assets/gallery-dl-icon.png'
ICON_ICO = APP_DIR / 'assets/gallery-dl-icon.ico'
BG, PANEL, TEXT, MUTED, GREEN = '#110B38', '#1E1E1E', '#FFFFFF', '#99A2DB', '#B2F962'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('gallery-dl Desktop')
        try:
            self.app_icon = tk.PhotoImage(file=str(ICON_PNG))
            self.iconphoto(True, self.app_icon)
            if sys.platform == 'win32':
                self.iconbitmap(default=str(ICON_ICO))
        except tk.TclError:
            self.app_icon = None
        self.configure(bg=BG)
        self.geometry('800x780')
        self.minsize(720, 650)
        self.events = queue.Queue()
        self.process = None
        self.busy = self.cancelled = False
        self.saved = self.existing = 0
        self.update_restart_required = False
        self.update_verified = False
        destination = str(Path('Downloads') / 'gallery-dl')
        prefs = {}
        try:
            prefs = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            destination = prefs.get('destination') or destination
            previous_default = str(Path.home() / 'Downloads' / 'gallery-dl')
            if os.path.normcase(destination) == os.path.normcase(previous_default):
                destination = str(Path('Downloads') / 'gallery-dl')
        except (OSError, ValueError):
            pass
        self.destination = tk.StringVar(value=destination)
        self.download_images = tk.BooleanVar(value=prefs.get('images', True) is not False)
        self.download_videos = tk.BooleanVar(value=bool(prefs.get('videos', False)))
        self.separate_media = tk.BooleanVar(value=prefs.get('separate_media', True) is not False)
        self.collection = tk.StringVar()
        self._automatic_collection = ''
        self._setting_collection = False
        self.status = tk.StringVar(value='Paste a URL and click Download.')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TProgressbar', background=GREEN, troughcolor=PANEL, borderwidth=0)
        body = tk.Frame(self, bg=BG, padx=24, pady=20)
        body.pack(fill='both', expand=True)
        try:
            self.logo = tk.PhotoImage(file=str(APP_DIR / 'assets/gallery-dl-logo.png')).subsample(4)
            tk.Label(body, image=self.logo, bg=BG).pack(anchor='w', pady=(0, 16))
        except tk.TclError:
            self.label(body, 'gallery-dl Desktop', 22).pack(anchor='w')
        self.label(body, 'Paste a URL', 12).pack(anchor='w', pady=(0, 6))
        self.urls = tk.Text(body, height=3, wrap='word', bg=PANEL, fg=TEXT,
                            insertbackground=GREEN, relief='flat', padx=12, pady=10,
                            font=('Segoe UI', 11), undo=True)
        self.urls.pack(fill='x')
        self.urls.bind('<<Modified>>', self.url_changed)
        self.urls.edit_modified(False)
        self.label(body, 'A page, image, post, or gallery. Multiple URLs are supported.', 10, MUTED).pack(anchor='w', pady=(6, 18))
        self.label(body, 'Save to', 11).pack(anchor='w', pady=(0, 6))
        folder = tk.Frame(body, bg=BG)
        folder.pack(fill='x')
        self.folder_entry = tk.Entry(folder, textvariable=self.destination, bg=PANEL, fg=TEXT,
                                     insertbackground=GREEN, relief='flat', font=('Segoe UI', 10))
        self.folder_entry.pack(side='left', fill='x', expand=True, ipady=9)
        self.browse = self.button(folder, 'Browse…', self.choose_folder)
        self.browse.pack(side='left', padx=(8, 0))

        media_options = tk.Frame(body, bg=BG)
        media_options.pack(fill='x', pady=(12, 0))
        self.label(media_options, 'Download', 10, MUTED).pack(side='left', padx=(0, 8))
        self.images_check = self.checkbutton(media_options, 'Images', self.download_images)
        self.images_check.pack(side='left')
        self.videos_check = self.checkbutton(media_options, 'Videos', self.download_videos)
        self.videos_check.pack(side='left', padx=(8, 0))

        storage_options = tk.Frame(body, bg=BG)
        storage_options.pack(fill='x', pady=(4, 0))
        self.label(storage_options, 'Organize', 10, MUTED).pack(side='left', padx=(0, 8))
        self.separate_radio = self.radiobutton(
            storage_options, 'Separate folders', self.separate_media, True)
        self.separate_radio.pack(side='left')
        self.together_radio = self.radiobutton(
            storage_options, 'All in one folder', self.separate_media, False)
        self.together_radio.pack(side='left', padx=(8, 0))

        self.label(body, 'Folder', 11).pack(anchor='w', pady=(14, 6))
        self.collection_entry = tk.Entry(body, textvariable=self.collection, bg=PANEL, fg=TEXT,
                                         insertbackground=GREEN, relief='flat', font=('Segoe UI', 10))
        self.collection_entry.pack(fill='x', ipady=9)
        self.collection.trace_add('write', self.collection_changed)
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill='x', pady=(20, 16))
        self.download = self.button(actions, 'Download', self.start, primary=True)
        self.download.pack(side='left')
        self.stop = self.button(actions, 'Cancel', self.cancel)
        self.stop.pack(side='left', padx=8)
        self.stop.configure(state='disabled')
        self.button(actions, 'Open folder', self.open_folder).pack(side='right')
        self.update_button = self.button(actions, 'Update', self.update_engine)
        self.update_button.pack(side='right', padx=8)
        tk.Label(body, textvariable=self.status, bg=BG, fg=GREEN, font=('Segoe UI', 11),
                 anchor='w', wraplength=730).pack(fill='x', pady=(0, 8))
        self.progress = ttk.Progressbar(body, mode='indeterminate')
        self.progress.pack(fill='x', pady=(0, 12))
        log_frame = tk.Frame(body, bg=PANEL)
        log_frame.pack(fill='both', expand=True)
        self.log = tk.Text(log_frame, height=6, wrap='word', bg=PANEL, fg=MUTED,
                           relief='flat', padx=12, pady=10, font=('Segoe UI', 10), state='disabled')
        self.log.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=scrollbar.set)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Control-Return>', lambda _: self.start())
        self.after(100, self.poll)

    def label(self, parent, text, size, color=TEXT):
        return tk.Label(parent, text=text, bg=BG, fg=color, font=('Segoe UI', size))

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=GREEN if primary else '#21136D',
                         fg=BG if primary else TEXT, activebackground='#6B3BD0', activeforeground=TEXT,
                         relief='flat', bd=0, padx=17, pady=9, cursor='hand2', font=('Segoe UI', 10, 'bold'))

    def checkbutton(self, parent, text, variable):
        return tk.Checkbutton(parent, text=text, variable=variable, bg=BG, fg=TEXT,
                              activebackground=BG, activeforeground=TEXT, selectcolor='#21136D',
                              bd=0, highlightthickness=0, font=('Segoe UI', 10))

    def radiobutton(self, parent, text, variable, value):
        return tk.Radiobutton(parent, text=text, variable=variable, value=value, bg=BG, fg=TEXT,
                              activebackground=BG, activeforeground=TEXT, selectcolor='#21136D',
                              bd=0, highlightthickness=0, font=('Segoe UI', 10))

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.resolve_destination())
        if folder:
            self.destination.set(folder)

    def resolve_destination(self):
        value = os.path.expandvars(self.destination.get().strip())
        path = Path(value).expanduser()
        return (Path.home() / path if not path.is_absolute() else path).resolve()

    def collection_changed(self, *_):
        if not self._setting_collection and self.collection.get() != self._automatic_collection:
            self._automatic_collection = ''

    def url_changed(self, _event=None):
        if not self.urls.edit_modified():
            return
        self.urls.edit_modified(False)
        try:
            suggested = folder_name_from_url(normalize_urls(self.urls.get('1.0', 'end'))[0])
        except ValueError:
            return
        if not self.collection.get() or self.collection.get() == self._automatic_collection:
            self._setting_collection = True
            self.collection.set(suggested)
            self._automatic_collection = suggested
            self._setting_collection = False

    def target_folder(self):
        name = self.collection.get().strip()
        if not name:
            raise ValueError('Enter a folder name.')
        if name in ('.', '..') or any(char in name for char in '<>:"/\\|?*') or name.rstrip(' .') != name:
            raise ValueError('Use a single folder name without /, \\ or special characters.')
        if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
            raise ValueError('This folder name is reserved by Windows.')
        return self.resolve_destination() / name

    def open_folder(self):
        try:
            folder = self.target_folder() if self.collection.get().strip() else self.resolve_destination()
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(folder)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Folder unavailable', str(exc))

    def append(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def set_busy(self, value):
        self.busy = value
        for control in (self.download, self.update_button, self.browse, self.folder_entry,
                        self.collection_entry, self.urls, self.images_check, self.videos_check,
                        self.separate_radio, self.together_radio):
            control.configure(state='disabled' if value else 'normal')
        self.stop.configure(state='normal' if value else 'disabled')
        self.progress.start(12) if value else self.progress.stop()

    def start(self):
        if self.busy:
            return
        try:
            urls = normalize_urls(self.urls.get('1.0', 'end'))
            if not self.destination.get().strip():
                raise ValueError('Choose a destination folder.')
            if not self.download_images.get() and not self.download_videos.get():
                raise ValueError('Select Images, Videos, or both.')
            destination = self.target_folder()
            destination.mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Check the URL or folder', str(exc))
            return
        try:
            STATE_FILE.write_text(json.dumps({
                'destination': self.destination.get().strip(),
                'images': self.download_images.get(),
                'videos': self.download_videos.get(),
                'separate_media': self.separate_media.get(),
            }), encoding='utf-8')
        except OSError:
            pass
        self.saved = self.existing = 0
        self.cancelled = False
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        self.append('Destination: ' + str(destination))
        selected = 'Images and videos' if self.download_images.get() and self.download_videos.get() \
            else 'Images' if self.download_images.get() else 'Videos'
        organization = 'separate folders' if self.separate_media.get() else 'All in one folder'
        self.append(f'Content: {selected} · {organization}')
        self.set_busy(True)
        self.status.set('Looking for media…')
        self.launch([str(APP_DIR / 'engine.py')], {
            'urls': urls,
            'destination': str(destination),
            'images': self.download_images.get(),
            'videos': self.download_videos.get(),
            'separate_media': self.separate_media.get(),
        })

    def launch(self, args, payload=None):
        # Spawn before enabling event processing: Cancel cannot race creation.
        try:
            self.process = subprocess.Popen([str(APP_DIR / '.venv/Scripts/python.exe'), '-u', *args],
                cwd=APP_DIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if payload is not None:
                self.process.stdin.write(json.dumps(payload) + '\n')
                self.process.stdin.flush()
            self.process.stdin.close()
        except OSError as exc:
            self.append(str(exc))
            self.status.set('Could not start. Run INSTALL.bat.')
            self.set_busy(False)
            return
        proc = self.process
        def read():
            for line in proc.stdout:
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError()
                except ValueError:
                    event = {'type': 'log', 'text': line.rstrip()}
                self.events.put(event)
            self.events.put({'type': 'exit', 'code': proc.wait(), 'update': payload is None})
        threading.Thread(target=read, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            event = self.events.get_nowait()
            kind = event.get('type')
            if kind in ('log', 'status', 'error'):
                self.append(event.get('text', ''))
                if kind != 'log':
                    self.status.set(event.get('text', ''))
            elif kind == 'file':
                self.existing += bool(event.get('existing'))
                self.saved += not event.get('existing', False)
                self.status.set(f'{self.saved} files downloaded · {self.existing} already present')
                self.append(('Already present: ' if event.get('existing') else 'Saved: ') + event['name'])
            elif kind == 'done':
                self.status.set(event['text'])
                self.append(event['text'])
            elif kind == 'update_result':
                self.update_verified = True
                self.update_restart_required = bool(event.get('restart_required'))
            elif kind == 'exit':
                self.process = None
                self.set_busy(False)
                if self.cancelled:
                    self.status.set('Canceled. Completed files remain in the destination folder.')
                elif event.get('update'):
                    text = 'Update verified.'
                    if self.update_restart_required:
                        text += ' Reopen the app to load the updated interface.'
                    self.status.set(text if event['code'] == 0 and self.update_verified
                                    else 'Update failed or could not be verified. See the details.')
                elif event['code'] != 0:
                    self.status.set(f'Download incomplete: {self.saved} files saved. See the details.')
        self.after(100, self.poll)

    def cancel(self):
        if self.process and self.process.poll() is None:
            self.cancelled = True
            self.stop.configure(state='disabled')
            self.status.set('Canceling…')
            subprocess.Popen(['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def update_engine(self):
        if not self.busy:
            self.cancelled = False
            self.update_restart_required = False
            self.update_verified = False
            self.set_busy(True)
            self.status.set('Checking app and engine updates…')
            self.append('Checking the application, official releases, and dependencies…')
            self.launch([str(APP_DIR / 'maintenance.py')])

    def close(self):
        if self.busy and not messagebox.askyesno('Close?', 'Cancel the current operation and close?'):
            return
        self.cancel()
        self.destroy()


if __name__ == '__main__':
    if sys.platform == 'win32':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()
