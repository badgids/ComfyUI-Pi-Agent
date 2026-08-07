import unittest

from comfy_pi_agent.fountain import build_fountain, create_shot_list, parse_fountain, screenplay_breakdown, validate_fountain


class FountainTests(unittest.TestCase):
    def test_build_and_parse(self):
        text = build_fountain("Test", "Alan", "A person enters the room.", "WORKSHOP")
        parsed = parse_fountain(text)
        self.assertEqual(parsed["title_page"]["title"], "Test")
        self.assertEqual(len(parsed["scenes"]), 1)

    def test_dialogue(self):
        text = """Title: Test\n\nINT. ROOM - DAY #1#\n\nALAN\nHello.\n"""
        parsed = parse_fountain(text)
        self.assertIn("ALAN", parsed["scenes"][0]["characters"])
        self.assertEqual(parsed["scenes"][0]["dialogue"], ["Hello."])
        self.assertTrue(validate_fountain(text)["valid"])

    def test_shot_list(self):
        text = "Title: Test\n\nEXT. ROAD - NIGHT\n\nA car stops.\n"
        breakdown = screenplay_breakdown(text)
        shots = create_shot_list(breakdown, "standard")
        self.assertEqual(len(shots["shots"]), 3)


if __name__ == "__main__":
    unittest.main()
