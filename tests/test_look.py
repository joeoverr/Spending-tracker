# Checks the colours and icons from theme.py and icons.py
import unittest
import icons
import theme

class TestColours(unittest.TestCase):
    def test_every_category_has_its_own_colour(self):
        import categorise
        for category in categorise.CATEGORIES + [categorise.UNSORTED]:
            self.assertIn(category, theme.CATEGORY_COLOURS)
        spending = [theme.CATEGORY_COLOURS[c] for c in categorise.CATEGORIES if c not in categorise.NOT_SPENDING]
        self.assertEqual(len(spending), len(set(spending)))   # no two spending categories look the same

    def test_new_category_always_gets_the_same_spare_colour(self):
        self.assertEqual(theme.colour_for("Pets"), theme.colour_for("Pets"))
        self.assertIn(theme.colour_for("Pets"), theme.SPARE_COLOURS)

class TestIcons(unittest.TestCase):
    def test_dot(self):
        image = icons.dot("#2FB45A", 12)
        self.assertEqual(image.size, (12, 12))
        self.assertLess(image.getpixel((0, 0))[3], 10)        # corners see-through (out of 255)
        self.assertEqual(image.getpixel((6, 6))[:3], (47, 180, 90))   # middle is the colour

    def test_every_badge_draws(self):
        for kind in ("up", "down", "dot", "day", "shop", "average", "alert", "download"):
            self.assertEqual(icons.badge(kind, "#2F6BFF", 36).size, (36, 36))

    def test_mix(self):
        self.assertEqual(icons.mix("#000000", "#FFFFFF", 0.5), "#808080")

if __name__ == "__main__":
    unittest.main()
