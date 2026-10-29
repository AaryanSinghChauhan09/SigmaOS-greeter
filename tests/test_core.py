"""Comprehensive Arrange-Act-Assert FIRST unit test suite for SigmaOS-greeter."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import core


SAMPLE_PASSWD = "\n".join([
    "root:x:0:0:root:/root:/bin/bash",
    "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin",
    "alice:x:1000:1000:Alice A:/home/alice:/bin/bash",
    "bob:x:1001:1001:Bob B:/home/bob:/bin/zsh",
    "svc:x:999:999:Service:/var/lib/svc:/usr/sbin/nologin",
    "carol:x:1002:1002:Carol C:/home/carol:/bin/bash",
    "",
])


class TestGreeterPasswd(unittest.TestCase):
    def test_parse_passwd_filters_system_accounts_and_sorts(self):
        # Arrange
        text = SAMPLE_PASSWD

        # Act
        users = core.parse_passwd(text)

        # Assert: AAA & Secure Defaults (system accounts hidden, sorted by uid)
        self.assertEqual([u["name"] for u in users], ["alice", "bob", "carol"])
        self.assertEqual([u["uid"] for u in users], [1000, 1001, 1002])
        self.assertEqual(users[0]["home"], "/home/alice")

    def test_parse_passwd_toggles_min_uid_and_nologin(self):
        # Arrange
        text = SAMPLE_PASSWD

        # Act & Assert
        all_uid_users = core.parse_passwd(text, min_uid=0)
        self.assertEqual(len(all_uid_users), 4)  # alice, bob, carol + root

        all_inclusive = core.parse_passwd(text, min_uid=0, include_nologin=True)
        self.assertEqual(len(all_inclusive), 6)

    def test_parse_passwd_malformed_fields_fail_fast(self):
        # Arrange: Invalid line with wrong field count
        bad_text = "alice:x:1000:bad:only:fields"

        # Act & Assert: Fail-Fast
        with self.assertRaises(core.GreeterError):
            core.parse_passwd(bad_text)

    def test_parse_passwd_invalid_username_rejected(self):
        # Arrange: Invalid username capital
        bad_text = "Alice:x:1000:1000:A:/home/A:/bin/bash"

        # Act & Assert
        with self.assertRaises(core.GreeterError):
            core.parse_passwd(bad_text)

    def test_parse_passwd_duplicate_user_rejected(self):
        # Arrange: Duplicate user entry
        duplicate_text = SAMPLE_PASSWD + "\nalice:x:1005:1005:Alice 2:/home/alice2:/bin/bash"

        # Act & Assert
        with self.assertRaises(core.GreeterError):
            core.parse_passwd(duplicate_text)


class TestGreeterThemes(unittest.TestCase):
    def test_theme_config_valid(self):
        # Arrange & Act
        dark = core.theme_config("sigma-dark")
        plain = core.theme_config("sigma-plain")

        # Assert
        self.assertEqual(dark["name"], "sigma-dark")
        self.assertTrue(dark["blur"])
        self.assertFalse(plain["blur"])

    def test_theme_config_invalid_rejected(self):
        # Arrange & Act & Assert
        with self.assertRaises(core.GreeterError):
            core.theme_config("nonexistent-theme")


class TestGreeterAccessibility(unittest.TestCase):
    def test_a11y_valid_settings_and_normalization(self):
        # Arrange
        settings = {
            "font_scale": 1.5,
            "high_contrast": True,
            "keyboard_navigation": True,
            "screen_reader": True,
        }

        # Act
        normalized = core.a11y(settings)

        # Assert
        self.assertEqual(normalized["font_scale"], 1.5)
        self.assertTrue(normalized["screen_reader"])
        self.assertEqual(list(normalized.keys()), sorted(normalized.keys()))

    def test_a11y_font_scale_bounds_validation(self):
        # Arrange & Act & Assert: out of bounds [1.0, 3.0]
        with self.assertRaises(core.GreeterError):
            core.a11y({"font_scale": 0.5})

        with self.assertRaises(core.GreeterError):
            core.a11y({"font_scale": 4.0})

    def test_a11y_user_timeout_bounds_validation(self):
        # Arrange & Act & Assert
        with self.assertRaises(core.GreeterError):
            core.a11y({"user_timeout": -1})

        with self.assertRaises(core.GreeterError):
            core.a11y({"user_timeout": 200})

    def test_a11y_screen_reader_requires_keyboard_nav(self):
        # Arrange: Screen reader enabled without keyboard navigation
        settings = {"screen_reader": True, "keyboard_navigation": False}

        # Act & Assert
        with self.assertRaises(core.GreeterError):
            core.a11y(settings)


class TestGreeterLaunchPlan(unittest.TestCase):
    def test_launch_plan_ordered_sequence(self):
        # Arrange & Act
        plan = core.launch_plan("sigma-dark", "wayland", user="alice")

        # Assert: Strict pipeline sequence
        self.assertEqual([s["step"] for s in plan], ["compositor", "greeter", "session"])
        self.assertEqual([s["order"] for s in plan], [1, 2, 3])
        self.assertTrue(plan[0]["cmd"].endswith("--session wayland"))
        self.assertTrue(plan[2]["cmd"].endswith("--user alice"))

    def test_launch_plan_session_and_user_validation(self):
        # Arrange & Act & Assert
        with self.assertRaises(core.GreeterError):
            core.launch_plan("sigma-dark", "unsupported_session")

        with self.assertRaises(core.GreeterError):
            core.launch_plan("sigma-dark", "wayland", user="Invalid User!")


class TestGreeterCliSmoke(unittest.TestCase):
    def test_cli_smoke_commands(self):
        # Arrange
        with tempfile.TemporaryDirectory() as d:
            pw = os.path.join(d, "passwd")
            with open(pw, "w", encoding="utf-8") as fh:
                fh.write(SAMPLE_PASSWD)
            ap = os.path.join(d, "a11y.json")
            with open(ap, "w", encoding="utf-8") as fh:
                json.dump({"font_scale": 1.25, "keyboard_navigation": True}, fh)

            # Act & Assert
            self.assertEqual(core.main(["users", pw]), 0)
            self.assertEqual(core.main(["theme", "sigma-light"]), 0)
            self.assertEqual(core.main(["a11y", ap]), 0)
            self.assertEqual(core.main(["launch-plan", "--theme", "sigma-dark", "--user", "alice"]), 0)


if __name__ == "__main__":
    unittest.main()
