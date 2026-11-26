import unittest

from ui import LitePlayerApp


class FakeRoot:
    def __init__(self):
        self.callbacks = {}
        self.next_id = 1

    def after(self, _delay, callback):
        identifier = self.next_id
        self.next_id += 1
        self.callbacks[identifier] = callback
        return identifier

    def after_cancel(self, identifier):
        self.callbacks.pop(identifier, None)

    def fire(self, identifier):
        callback = self.callbacks.pop(identifier)
        callback()


class FakeVar:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class FakeBackend:
    def __init__(self):
        self.paused = False
        self.seek_calls = []

    def get(self, name, _default=None):
        if name == "pause":
            return self.paused
        return _default

    def set_paused(self, paused):
        self.paused = paused

    def seek(self, position):
        self.seek_calls.append(position)


class VideoClickTests(unittest.TestCase):
    def setUp(self):
        self.app = LitePlayerApp.__new__(LitePlayerApp)
        self.app.root = FakeRoot()
        self.app.backend = FakeBackend()
        self.app.video_click_after = None
        self.app.ended = False
        self.app.closing = False
        self.app.playlist = []
        self.app.playing = True
        self.app.update_play_button = lambda: None
        self.fullscreen_calls = 0
        self.app.toggle_fullscreen = self.record_fullscreen

    def record_fullscreen(self):
        self.fullscreen_calls += 1

    def click_once_and_run(self):
        self.app.on_video_single_click(None)
        identifier = self.app.video_click_after
        self.assertIsNotNone(identifier)
        self.app.root.fire(identifier)

    def test_single_click_pauses_and_second_click_resumes(self):
        self.click_once_and_run()
        self.assertTrue(self.app.backend.paused)
        self.app.playing = False
        self.click_once_and_run()
        self.assertFalse(self.app.backend.paused)

    def test_double_click_cancels_pending_play_pause(self):
        self.app.on_video_single_click(None)
        self.app.on_video_double_click(None)
        self.assertEqual(self.fullscreen_calls, 1)
        self.assertEqual(self.app.root.callbacks, {})
        self.assertFalse(self.app.backend.paused)

    def test_no_playback_or_ended_video_does_not_schedule_a_toggle(self):
        self.app.backend = None
        self.app.on_video_single_click(None)
        self.assertIsNone(self.app.video_click_after)
        self.app.backend = FakeBackend()
        self.app.ended = True
        self.app.on_video_single_click(None)
        self.assertIsNone(self.app.video_click_after)

    def test_transport_action_cancels_pending_click(self):
        self.app.on_video_single_click(None)
        self.app.toggle_play()
        self.assertEqual(self.app.root.callbacks, {})
        self.assertIsNone(self.app.video_click_after)
        self.assertTrue(self.app.backend.paused)

    def test_stop_cancels_pending_click(self):
        self.app.seek_var = FakeVar()
        self.app.position = 4.0
        self.app.on_video_single_click(None)
        self.app.stop()
        self.assertEqual(self.app.root.callbacks, {})
        self.assertIsNone(self.app.video_click_after)
        self.assertTrue(self.app.backend.paused)
        self.assertEqual(self.app.backend.seek_calls, [0])
        self.assertFalse(self.app.playing)
        self.assertEqual(self.app.position, 0.0)


if __name__ == "__main__":
    unittest.main()
