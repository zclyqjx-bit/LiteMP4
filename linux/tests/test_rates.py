import unittest

from ui import LitePlayerApp


class FakeButton:
    def __init__(self):
        self.text = ""

    def config(self, text):
        self.text = text


class FakeBackend:
    def __init__(self):
        self.rates = []

    def set_rate(self, rate):
        self.rates.append(rate)


class PlaybackRateTests(unittest.TestCase):
    def test_2_5_and_3_times_rates_and_cycle_boundaries(self):
        app = LitePlayerApp.__new__(LitePlayerApp)
        app.rate = 2.0
        app.backend = FakeBackend()
        app.rate_button = FakeButton()

        app.step_rate(1)
        self.assertEqual(app.rate, 2.5)
        self.assertEqual(app.rate_button.text, "2.5×")
        app.step_rate(1)
        self.assertEqual(app.rate, 3.0)
        self.assertEqual(app.rate_button.text, "3×")
        app.step_rate(1)
        self.assertEqual(app.rate, 3.0)

        app.change_rate()
        self.assertEqual(app.rate, 0.5)
        app.step_rate(-1)
        self.assertEqual(app.rate, 0.5)
        app.change_rate()
        self.assertEqual(app.rate, 0.75)
        self.assertEqual(app.backend.rates, [2.5, 3.0, 3.0, 0.5, 0.5, 0.75])


if __name__ == "__main__":
    unittest.main()
