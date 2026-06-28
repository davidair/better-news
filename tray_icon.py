"""
System tray icon for the pipeline. Only visible while the pipeline is running.
States: RUNNING (green), GPU_SKIPPED (yellow), ERROR (red).

Usage:
    icon = TrayIcon()
    icon.start()          # show green icon in tray
    icon.set_gpu_skipped() # turn yellow
    icon.set_error()       # turn red
    icon.stop()           # remove from tray
"""

import platform
import threading

try:
    from PIL import Image, ImageDraw
    import pystray
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False

_COLOR_RUNNING = (76, 175, 80)      # green
_COLOR_GPU_SKIPPED = (255, 193, 7)  # amber
_COLOR_ERROR = (244, 67, 54)        # red
_ICON_SIZE = 64


def _make_icon_image(color):
    img = Image.new('RGBA', (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 6
    draw.ellipse(
        [margin, margin, _ICON_SIZE - margin, _ICON_SIZE - margin],
        fill=color
    )
    return img


class TrayIcon:
    def __init__(self):
        self._icon = None
        self._thread = None
        self._available = _TRAY_AVAILABLE and platform.system() in ('Windows', 'Darwin', 'Linux')

    def _make_pystray_icon(self, color, title):
        return pystray.Icon(
            'better-news',
            _make_icon_image(color),
            title
        )

    def start(self):
        if not self._available:
            return
        self._icon = self._make_pystray_icon(_COLOR_RUNNING, 'Better News: running')
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def _update(self, color, title):
        if not self._available or self._icon is None:
            return
        self._icon.icon = _make_icon_image(color)
        self._icon.title = title

    def set_gpu_skipped(self):
        self._update(_COLOR_GPU_SKIPPED, 'Better News: GPU busy, analysis skipped')

    def set_error(self):
        self._update(_COLOR_ERROR, 'Better News: error (check pipeline.log)')

    def stop(self):
        if not self._available or self._icon is None:
            return
        self._icon.stop()
        self._icon = None
