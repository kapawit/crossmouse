from __future__ import annotations

import unittest

from crossmouse import protocol
from crossmouse.clipboard import Clipboard
from crossmouse.config import Config
from crossmouse.engine import Engine, at_edge, beyond_edge, entry_point
from crossmouse.platform_base import InputEvent, Platform


class FakePlatform(Platform):
    def __init__(self, size=(1000, 800), pointer=(500, 400)):
        self.size = size
        self.pointer = pointer
        self.grabbed = False
        self.moves: list[tuple[int, int]] = []
        self.set_points: list[tuple[int, int]] = []
        self.released = 0
        self.suppressed = False
        self.pointer_visible = True

    def screen_size(self):
        return self.size

    def pointer_position(self):
        return self.pointer

    def set_pointer(self, x, y):
        self.set_points.append((x, y))
        self.pointer = (x, y)

    def grab(self):
        self.grabbed = True

    def ungrab(self):
        self.grabbed = False

    def start_capture(self, sink):
        pass

    def stop_capture(self):
        pass

    def inject(self, event):
        if event.kind == "move":
            self.moves.append((event.a, event.b))

    def release_all_keys(self):
        self.released += 1

    def set_suppress(self, value):
        self.suppressed = value

    def set_pointer_visible(self, visible):
        self.pointer_visible = visible


class FakeClipboard(Clipboard):
    def __init__(self, text=""):
        self.text = text
        self.written = []

    def get_text(self):
        return self.text

    def set_text(self, text):
        self.written.append(text)
        self.text = text


class FakeLink:
    def __init__(self, screen=(1000, 800)):
        self.peer_screen = screen
        self.sent = []

    def send(self, kind, data=None):
        self.sent.append((kind, data or {}))


def make_engine(edge="right", peer=(1000, 800), primary=True):
    platform = FakePlatform()
    clipboard = FakeClipboard()
    engine = Engine(Config(secret="s", edge=edge, primary=primary), platform, clipboard)
    link = FakeLink(peer)
    engine.attach(link)
    return engine, platform, clipboard, link


class EdgeHelperTests(unittest.TestCase):
    def test_entry_point(self):
        self.assertEqual(entry_point("left", 1000, 800), (0, 400))
        self.assertEqual(entry_point("right", 1000, 800), (999, 400))
        self.assertEqual(entry_point("top", 1000, 800), (500, 0))
        self.assertEqual(entry_point("bottom", 1000, 800), (500, 799))

    def test_at_edge(self):
        self.assertTrue(at_edge("right", 999, 400, 1000, 800))
        self.assertFalse(at_edge("right", 998, 400, 1000, 800))
        self.assertTrue(at_edge("top", 500, 0, 1000, 800))

    def test_beyond_edge(self):
        self.assertTrue(beyond_edge("left", 0, 400, 1000, 800, 5, 400))
        self.assertFalse(beyond_edge("left", 5, 400, 1000, 800, 0, 400))


class EngineTests(unittest.TestCase):
    def test_crossing_edge_begins_controlling(self):
        engine, platform, _, link = make_engine()
        engine.local_event(InputEvent("move", 900, 400))
        engine.local_event(InputEvent("move", 999, 400))
        self.assertEqual(engine.mode, "controlling")
        self.assertTrue(platform.grabbed)
        self.assertIn((protocol.HANDOFF, {"from": "controlling"}), link.sent)

    def test_handoff_sends_initial_position_to_peer_not_locally(self):
        engine, platform, _, link = make_engine()
        engine.local_event(InputEvent("move", 900, 400))
        engine.local_event(InputEvent("move", 999, 400))
        self.assertEqual(platform.moves, [])
        moves = [d for k, d in link.sent if k == protocol.MOVE]
        self.assertEqual(moves, [{"x": 0, "y": 400}])

    def test_controlling_forwards_move_mapped_to_peer(self):
        engine, platform, _, link = make_engine()
        engine.local_event(InputEvent("move", 900, 400))
        engine.local_event(InputEvent("move", 999, 400))
        link.sent.clear()
        engine.local_event(InputEvent("move", 510, 410))
        moves = [d for k, d in link.sent if k == protocol.MOVE]
        self.assertTrue(moves)
        self.assertEqual(moves[-1]["x"], 10)
        self.assertEqual(moves[-1]["y"], 410)

    def test_non_owner_never_initiates_handoff(self):
        engine, platform, _, link = make_engine(primary=False)
        engine.local_event(InputEvent("move", 999, 400))
        engine.request_handoff()
        self.assertEqual(engine.mode, "idle")
        self.assertFalse(platform.grabbed)
        self.assertNotIn((protocol.HANDOFF, {"from": "controlling"}), link.sent)

    def test_non_owner_still_accepts_remote_control(self):
        engine, platform, _, _ = make_engine(primary=False)
        engine.remote_message(protocol.HANDOFF, {"from": "controlling"})
        engine.remote_message(protocol.MOVE, {"x": 10, "y": 20})
        self.assertEqual(engine.mode, "controlled")
        self.assertEqual(platform.moves[-1], (10, 20))

    def test_inward_motion_at_edge_does_not_handoff(self):
        engine, _, _, link = make_engine()
        engine.local_event(InputEvent("move", 999, 400))
        engine.local_event(InputEvent("move", 990, 400))
        self.assertEqual(engine.mode, "idle")
        engine.local_event(InputEvent("move", 995, 400))
        engine.local_event(InputEvent("move", 999, 400))
        self.assertEqual(engine.mode, "controlling")

    def test_first_leftward_delta_does_not_hand_back(self):
        engine, _, _, link = make_engine()
        engine.local_event(InputEvent("move", 900, 400))
        engine.local_event(InputEvent("move", 999, 400))
        link.sent.clear()
        engine.local_event(InputEvent("move", 490, 400))
        self.assertEqual(engine.mode, "controlling")
        self.assertNotIn((protocol.HANDOFF, {"from": "controlled"}), link.sent)

    def test_handoff_controlling_sets_controlled(self):
        engine, _, _, _ = make_engine()
        engine.remote_message(protocol.HANDOFF, {"from": "controlling"})
        self.assertEqual(engine.mode, "controlled")

    def test_controlled_injects_moves(self):
        engine, platform, _, _ = make_engine()
        engine.remote_message(protocol.HANDOFF, {"from": "controlling"})
        engine.remote_message(protocol.MOVE, {"x": 10, "y": 20})
        engine.remote_message(protocol.MOVE, {"x": 11, "y": 21})
        self.assertEqual(platform.moves[-1], (11, 21))

    def test_controlled_handoff_back_at_edge(self):
        engine, _, _, link = make_engine(edge="left")
        engine.remote_message(protocol.HANDOFF, {"from": "controlling"})
        engine.remote_message(protocol.MOVE, {"x": 0, "y": 400})
        engine.remote_message(protocol.MOVE, {"x": 20, "y": 400})
        link.sent.clear()
        engine.remote_message(protocol.MOVE, {"x": 0, "y": 400})
        self.assertEqual(engine.mode, "idle")
        self.assertIn((protocol.HANDOFF, {"from": "controlled"}), link.sent)

    def test_clipboard_sync(self):
        engine, _, clipboard, link = make_engine()
        clipboard.text = "hello"
        engine._clock = lambda: 1000.0
        engine.poll_clipboard()
        self.assertIn((protocol.CLIPBOARD, {"text": "hello"}), link.sent)

    def test_suppression_tracks_controlling_mode(self):
        engine, platform, _, _ = make_engine()
        engine.local_event(InputEvent("move", 900, 400))
        engine.local_event(InputEvent("move", 999, 400))
        self.assertTrue(platform.suppressed)
        engine.detach()
        self.assertFalse(platform.suppressed)

    def test_pointer_hidden_while_controlling(self):
        engine, platform, _, _ = make_engine()
        engine.local_event(InputEvent("move", 900, 400))
        engine.local_event(InputEvent("move", 999, 400))
        self.assertFalse(platform.pointer_visible)
        engine.detach()
        self.assertTrue(platform.pointer_visible)

    def test_detach_releases(self):
        engine, platform, _, _ = make_engine()
        engine.local_event(InputEvent("move", 900, 400))
        engine.local_event(InputEvent("move", 999, 400))
        engine.detach()
        self.assertFalse(platform.grabbed)
        self.assertEqual(engine.mode, "idle")


class PumpLinkTests(unittest.TestCase):
    def test_clipboard_polled_without_messages(self):
        from crossmouse.main import pump_link

        class Link:
            alive = True

            def recv(self, timeout=None):
                return None

        class Engine:
            link = object()

            def __init__(self):
                self.polls = 0
                self.detached = 0

            def remote_message(self, *args):
                pass

            def poll_clipboard(self):
                self.polls += 1

            def detach(self):
                self.detached += 1
                self.link = None

        engine = Engine()
        calls = []

        def should_stop():
            calls.append(1)
            return len(calls) > 3

        pump_link(engine, Link(), should_stop)
        self.assertEqual(engine.polls, 3)

    def test_dead_link_detaches_for_reconnect(self):
        from crossmouse.main import pump_link

        class Link:
            alive = False

            def recv(self, timeout=None):
                return None

        class Engine:
            link = object()

            def __init__(self):
                self.detached = 0

            def poll_clipboard(self):
                pass

            def detach(self):
                self.detached += 1

        engine = Engine()
        pump_link(engine, Link(), lambda: False)
        self.assertEqual(engine.detached, 1)


if __name__ == "__main__":
    unittest.main()
