"""og_image: today's link-preview image keeps every word inside the centred crops social apps use."""
import os, tempfile, unittest

try:
    import og_image
except ImportError:   # Pillow missing (CI installs it from requirements.txt)
    og_image = None

FC = {"live": [{"fuel": "U91", "now": 202.9, "verdict": {"cls": "down", "head": "Wait if you can"}}]}


@unittest.skipIf(og_image is None, "Pillow not installed")
class OgImage(unittest.TestCase):
    def test_todays_words_and_tone(self):
        self.assertEqual(og_image.today(FC, "Tue 24 Nov"), ("Wait if you can", "Sydney U91 median 202.9c/L", "wait", "Tue 24 Nov"))
        up = {"live": [{"fuel": "DL", "now": 257.9, "verdict": {"cls": "up", "head": "Fill up today"}}]}
        self.assertEqual(og_image.today(up, "x")[1:3], ("Sydney Diesel median 257.9c/L", "act"))
        self.assertIsNone(og_image.today({"live": []}, "x"))
        self.assertIsNone(og_image.today({"live": [{"fuel": "U91", "now": None, "verdict": {"head": "Wait"}}]}, "x"))

    def test_everything_inside_a_centred_4_5_crop(self):
        for args in [("No rush either way", "Sydney Diesel median 257.9c/L", "calm", "Wed 25 Nov"), ()]:
            im = og_image.draw(*args)
            self.assertEqual(im.size, (1200, 630))
            ink = og_image.INK
            # no drawn pixel outside the middle 504 px (a 4:5 crop of the 630 px height), nor in the top/bottom 40 px
            for x0, x1 in [(0, 348), (852, 1200)]:
                box = im.crop((x0, 0, x1, 630))
                self.assertEqual(box.getextrema(), tuple((c, c) for c in ink), args)
            for y0, y1 in [(0, 40), (590, 630)]:
                self.assertEqual(im.crop((0, y0, 1200, y1)).getextrema(), tuple((c, c) for c in ink), args)

    def test_write(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(og_image.write(d, FC, "Tue 24 Nov"), "og/today.png")
            self.assertTrue(os.path.getsize(os.path.join(d, "og", "today.png")) > 5000)
            self.assertIsNone(og_image.write(d, {"live": []}, "x"))


if __name__ == "__main__":
    unittest.main()
