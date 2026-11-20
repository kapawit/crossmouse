from __future__ import annotations

import threading
import time
from collections import deque

import importlib
import inspect
import pkgutil

from Xlib import X, XK, display
from Xlib import ext as xlib_ext
from Xlib.ext import record, xtest
from Xlib.protocol import rq

from .platform_base import EventSink, InputEvent, Platform


def _patch_xlib_error_classes() -> None:
    for module_info in pkgutil.iter_modules(xlib_ext.__path__):
        try:
            module = importlib.import_module(f"Xlib.ext.{module_info.name}")
        except Exception:
            continue
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and name.endswith("Error")
                and not hasattr(obj, "sequence_number")
            ):
                obj.sequence_number = 0


_patch_xlib_error_classes()

_BUTTONS = {1: "left", 2: "middle", 3: "right"}
_BUTTON_CODES = {v: k for k, v in _BUTTONS.items()}
_WHEEL_UP, _WHEEL_DOWN = 4, 5


def button_event(detail: int, pressed: int) -> InputEvent | None:
    if detail in (_WHEEL_UP, _WHEEL_DOWN):
        return InputEvent("scroll", 0, 1 if detail == _WHEEL_UP else -1) if pressed else None
    return InputEvent("button", _BUTTONS.get(detail, "left"), pressed)

_KEY_ALIASES = {
    "ctrl": "Control_L",
    "shift": "Shift_L",
    "alt": "Alt_L",
    "super": "Super_L",
    "enter": "Return",
    "esc": "Escape",
    "escape": "Escape",
    "space": "space",
    "backspace": "BackSpace",
    "delete": "Delete",
    "tab": "Tab",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "home": "Home",
    "end": "End",
    "pageup": "Prior",
    "pagedown": "Next",
    "plus": "plus",
    "minus": "minus",
}
for _number in range(1, 13):
    _KEY_ALIASES[f"f{_number}"] = f"F{_number}"


def _canonical_key(keysym_name: str) -> str:
    name = keysym_name.lower()
    reverse = {v.lower(): k for k, v in _KEY_ALIASES.items()}
    if name in reverse:
        return reverse[name]
    return name


def _build_keysym_map() -> dict[int, str]:
    mapping: dict[int, str] = {}
    for canonical, keysym_name in _KEY_ALIASES.items():
        keysym = XK.string_to_keysym(keysym_name)
        if keysym and keysym != XK.NoSymbol:
            mapping[keysym] = canonical
    for char in "abcdefghijklmnopqrstuvwxyz0123456789":
        keysym = XK.string_to_keysym(char)
        if keysym:
            mapping[keysym] = char
    for number in range(1, 13):
        keysym = XK.string_to_keysym(f"F{number}")
        if keysym:
            mapping[keysym] = f"f{number}"
    return mapping


_KEYSYM_TO_KEY = _build_keysym_map()


def keysym_to_key(keysym: int) -> str | None:
    key = _KEYSYM_TO_KEY.get(keysym)
    if key is not None:
        return key
    name = XK.keysym_to_string(keysym)
    if not name:
        return None
    text = name.decode() if isinstance(name, bytes) else name
    return _canonical_key(text)


def _keysym_for(key: str) -> int:
    name = _KEY_ALIASES.get(key.lower(), key)
    return XK.string_to_keysym(name)


class LinuxPlatform(Platform):
    def __init__(self, display_name: str | None = None) -> None:
        self._display_name = display_name
        self._display = display.Display(display_name)
        self._display.display.set_error_handler(lambda error, request: True)
        self._root = self._display.screen().root
        self._record_display: display.Display | None = None
        self._sink: EventSink | None = None
        self._record_context = None
        self._thread: threading.Thread | None = None
        self._grabbed = False
        self._keyboard_grabbed = False
        self._pressed_keys: set[int] = set()
        self._warp_targets: deque[tuple[int, int, float]] = deque()
        self._pointer_hidden = False

    def _flush(self) -> None:
        try:
            self._display.flush()
        except Exception:
            pass

    def screen_size(self) -> tuple[int, int]:
        screen = self._display.screen()
        return screen.width_in_pixels, screen.height_in_pixels

    def pointer_position(self) -> tuple[int, int]:
        p = self._root.query_pointer()
        return p.root_x, p.root_y

    def set_pointer_visible(self, visible: bool) -> None:
        import Xlib.ext.xfixes  # noqa: F401

        if visible:
            self._root.xfixes_show_cursor()
        else:
            self._root.xfixes_hide_cursor()
        self._flush()
        self._pointer_hidden = not visible

    def set_pointer(self, x: int, y: int) -> None:
        self._warp_targets.append((int(x), int(y), time.monotonic()))
        xtest.fake_input(self._display, X.MotionNotify, x=int(x), y=int(y))
        self._flush()

    def _is_own_warp(self, x: int, y: int) -> bool:
        now = time.monotonic()
        targets = self._warp_targets
        while targets and now - targets[0][2] > 0.5:
            targets.popleft()
        for index, (wx, wy, _) in enumerate(targets):
            if (wx, wy) == (x, y):
                del targets[index]
                return True
        return False

    def grab(self) -> None:
        if self._grabbed:
            return
        self._root.grab_pointer(
            False,
            X.PointerMotionMask | X.ButtonPressMask | X.ButtonReleaseMask,
            X.GrabModeAsync,
            X.GrabModeAsync,
            X.NONE,
            X.NONE,
            X.CurrentTime,
        )
        self._grabbed = True
        if not self._keyboard_grabbed:
            self._root.grab_keyboard(
                False,
                X.GrabModeAsync,
                X.GrabModeAsync,
                X.CurrentTime,
            )
            self._keyboard_grabbed = True

    def ungrab(self) -> None:
        if not self._grabbed:
            return
        self._display.ungrab_pointer(X.CurrentTime)
        if self._keyboard_grabbed:
            self._display.ungrab_keyboard(X.CurrentTime)
            self._keyboard_grabbed = False
        self._flush()
        self._grabbed = False

    def start_capture(self, sink: EventSink) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._sink = sink
        self._record_display = display.Display(self._display_name)
        self._record_display.display.set_error_handler(lambda error, request: True)
        self._record_context = self._record_display.record_create_context(
            0,
            [record.AllClients],
            [
                {
                    "core_requests": (0, 0),
                    "core_replies": (0, 0),
                    "ext_requests": (0, 0, 0, 0),
                    "ext_replies": (0, 0, 0, 0),
                    "delivered_events": (0, 0),
                    "device_events": (X.KeyPress, X.MotionNotify),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }
            ],
        )
        self._thread = threading.Thread(
            target=self._record_display.record_enable_context,
            args=(self._record_context, self._handle),
            daemon=True,
        )
        self._thread.start()

    def _handle(self, reply) -> None:
        if not hasattr(reply, "data") or self._sink is None:
            return
        data = reply.data
        field = rq.EventField(None)
        while len(data) >= 32:
            event, data = field.parse_binary_value(
                data, self._record_display.display, None, None
            )
            t = event.type
            out: InputEvent | None = None
            if t == X.MotionNotify:
                x, y = int(event.root_x), int(event.root_y)
                if self._is_own_warp(x, y):
                    continue
                out = InputEvent("move", x, y)
            elif t == X.ButtonPress:
                out = button_event(event.detail, 1)
            elif t == X.ButtonRelease:
                out = button_event(event.detail, 0)
            elif t in (X.KeyPress, X.KeyRelease):
                keysym = self._display.keycode_to_keysym(event.detail, 0)
                key = keysym_to_key(keysym)
                if key is None:
                    continue
                out = InputEvent("key", key, 1 if t == X.KeyPress else 0)
            if out is not None and not self.is_own_injection(out):
                self._sink(out)

    def stop_capture(self) -> None:
        if self._record_context is not None:
            try:
                self._record_display.record_disable_context(self._record_context)
                self._record_display.record_free_context(self._record_context)
            except Exception:
                pass
            self._record_context = None
        self._sink = None

    def inject(self, event: InputEvent) -> None:
        d = self._display
        if event.kind == "scroll":
            direction = 1 if int(event.b) > 0 else -1
            for _ in range(abs(int(event.b)) or 1):
                self.remember_injection(InputEvent("scroll", 0, direction))
        else:
            self.remember_injection(event)
        if event.kind == "move":
            xtest.fake_input(d, X.MotionNotify, x=int(event.a), y=int(event.b))
        elif event.kind == "button":
            code = _BUTTON_CODES.get(str(event.a), 1)
            xtest.fake_input(
                d, X.ButtonPress if event.b else X.ButtonRelease, detail=code
            )
        elif event.kind == "scroll":
            button = 4 if int(event.b) > 0 else 5
            for _ in range(abs(int(event.b)) or 1):
                xtest.fake_input(d, X.ButtonPress, detail=button)
                xtest.fake_input(d, X.ButtonRelease, detail=button)
        elif event.kind == "key":
            code = d.keysym_to_keycode(_keysym_for(str(event.a)))
            if code:
                if event.b:
                    self._pressed_keys.add(code)
                else:
                    self._pressed_keys.discard(code)
                xtest.fake_input(
                    d, X.KeyPress if event.b else X.KeyRelease, detail=code
                )
        self._flush()

    def release_all_keys(self) -> None:
        for code in list(self._pressed_keys):
            xtest.fake_input(self._display, X.KeyRelease, detail=code)
        self._pressed_keys.clear()
        self._flush()
