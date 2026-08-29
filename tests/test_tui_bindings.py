"""Unit coverage for `lifetxt.tui_bindings` (#595): resolving `tui.bindings`
overrides on top of the built-in prompt/vim/arrows keymap presets."""

import unittest

from lifetxt.tui_bindings import (
    ACTION_IDS,
    RESERVED_KEYS,
    normalize_key_name,
    resolve_bindings,
)


class NormalizeKeyNameTests(unittest.TestCase):
    def test_single_visible_characters_stay_case_sensitive(self):
        self.assertEqual("g", normalize_key_name("g"))
        self.assertEqual("G", normalize_key_name("G"))

    def test_symbolic_names_normalize_to_lowercase(self):
        self.assertEqual("enter", normalize_key_name("Enter"))
        self.assertEqual("up", normalize_key_name("UP"))

    def test_space_aliases_normalize_to_a_literal_space(self):
        self.assertEqual(" ", normalize_key_name("space"))
        self.assertEqual(" ", normalize_key_name("spacebar"))

    def test_esc_normalizes_to_escape(self):
        self.assertEqual("escape", normalize_key_name("esc"))

    def test_ctrl_combinations_normalize_to_lowercase(self):
        self.assertEqual("ctrl-p", normalize_key_name("Ctrl-P"))

    def test_rejects_an_empty_key(self):
        with self.assertRaises(ValueError):
            normalize_key_name("")

    def test_rejects_an_unsupported_multi_character_name(self):
        with self.assertRaises(ValueError):
            normalize_key_name("supercalifragilistic")


class ResolveBindingsTests(unittest.TestCase):
    def test_prompt_keymap_has_no_nav_mode_bindings(self):
        action_by_key, keys_by_action = resolve_bindings("prompt", None)
        self.assertEqual({}, dict(action_by_key))
        self.assertEqual({}, dict(keys_by_action))

    def test_vim_and_arrows_presets_share_the_same_base_bindings(self):
        vim_action_by_key, _ = resolve_bindings("vim", None)
        arrows_action_by_key, _ = resolve_bindings("arrows", None)
        self.assertEqual(dict(vim_action_by_key), dict(arrows_action_by_key))

    def test_every_documented_action_has_a_default_binding_in_vim(self):
        _action_by_key, keys_by_action = resolve_bindings("vim", None)
        for action in ACTION_IDS:
            self.assertIn(action, keys_by_action)
            self.assertTrue(keys_by_action[action])

    def test_no_overrides_reproduces_the_exact_default_binding_set(self):
        default_action_by_key, _ = resolve_bindings("vim", None)
        overridden_action_by_key, _ = resolve_bindings("vim", {})
        self.assertEqual(dict(default_action_by_key), dict(overridden_action_by_key))

    def test_a_single_custom_navigation_key_is_added_to_the_action(self):
        _action_by_key, keys_by_action = resolve_bindings("vim", {"move_down": ["n"]})
        self.assertEqual(["n"], keys_by_action["move_down"])

    def test_a_custom_mutation_action_key_replaces_the_default(self):
        action_by_key, keys_by_action = resolve_bindings("vim", {"done": ["x"]})
        self.assertEqual(["x"], keys_by_action["done"])
        self.assertEqual("done", action_by_key["x"])
        self.assertNotIn("d", action_by_key)

    def test_a_single_string_override_is_accepted_like_a_one_item_list(self):
        _action_by_key, keys_by_action = resolve_bindings("vim", {"quit": "x"})
        self.assertEqual(["x"], keys_by_action["quit"])

    def test_multiple_aliases_may_map_to_one_action(self):
        action_by_key, keys_by_action = resolve_bindings(
            "vim", {"open": ["enter", "l"]}
        )
        self.assertEqual(["enter", "l"], keys_by_action["open"])
        self.assertEqual("open", action_by_key["enter"])
        self.assertEqual("open", action_by_key["l"])

    def test_duplicate_aliases_for_one_action_are_deduplicated(self):
        _action_by_key, keys_by_action = resolve_bindings(
            "vim", {"quit": ["x", "x", "y"]}
        )
        self.assertEqual(["x", "y"], keys_by_action["quit"])

    def test_a_normalized_key_bound_to_two_different_actions_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_bindings("vim", {"quit": ["x"], "help": ["x"]})
        message = str(ctx.exception)
        self.assertIn("quit", message)
        self.assertIn("help", message)

    def test_an_override_colliding_with_a_default_action_key_is_rejected(self):
        # "j" already means move_down by default; binding "quit" to "j" too
        # without first vacating move_down is an unresolvable ambiguity.
        with self.assertRaises(ValueError):
            resolve_bindings("vim", {"quit": ["j"]})

    def test_unknown_action_id_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_bindings("vim", {"nonexistent_action": ["x"]})
        self.assertIn("nonexistent_action", str(ctx.exception))

    def test_unsupported_key_name_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_bindings("vim", {"quit": ["not-a-real-key"]})

    def test_empty_key_list_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_bindings("vim", {"quit": []})

    def test_non_dict_overrides_are_rejected(self):
        with self.assertRaises(ValueError):
            resolve_bindings("vim", "not-a-dict")

    def test_reserved_keys_cannot_be_assigned_to_a_registry_action(self):
        for reserved in RESERVED_KEYS:
            with self.assertRaises(ValueError):
                resolve_bindings("vim", {"quit": [reserved]})

    def test_unknown_keymap_falls_back_to_the_vim_base(self):
        fallback_action_by_key, _ = resolve_bindings("nonexistent-keymap", None)
        vim_action_by_key, _ = resolve_bindings("vim", None)
        self.assertEqual(dict(vim_action_by_key), dict(fallback_action_by_key))


if __name__ == "__main__":
    unittest.main()
