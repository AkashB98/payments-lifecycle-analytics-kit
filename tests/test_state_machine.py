import unittest
from payments_lifecycle.state_machine import LifecycleMachine, transition, is_allowed, IllegalTransitionError

class TestStateMachine(unittest.TestCase):
    def test_valid_path_settled(self):
        m = LifecycleMachine()
        m.move("authorized"); m.move("settled")
        self.assertTrue(m.is_terminal)
        self.assertEqual(m.state, "settled")

    def test_valid_retry_path(self):
        m = LifecycleMachine()
        m.move("failed"); m.move("retry_scheduled"); m.move("initiated"); m.move("authorized"); m.move("settled")
        self.assertEqual(m.state, "settled")

    def test_illegal_initiated_to_settled(self):
        with self.assertRaises(IllegalTransitionError):
            transition("initiated", "settled")

    def test_illegal_from_terminal(self):
        with self.assertRaises(IllegalTransitionError):
            transition("settled", "initiated")

    def test_illegal_failed_to_settled(self):
        with self.assertRaises(IllegalTransitionError):
            transition("failed", "settled")

    def test_is_allowed(self):
        self.assertTrue(is_allowed("initiated", "authorized"))
        self.assertFalse(is_allowed("initiated", "written_off"))

    def test_written_off_path(self):
        m = LifecycleMachine()
        m.move("authorized"); m.move("failed"); m.move("written_off")
        self.assertTrue(m.is_terminal)

if __name__ == "__main__":
    unittest.main()
