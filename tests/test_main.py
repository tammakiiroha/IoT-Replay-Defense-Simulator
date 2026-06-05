import pytest

import main
from sim.defaults import DEFAULT_ATTACK_MODE


def _parse_args(argv):
    # Helper wrapper to make tests explicit about provided CLI flags.
    return main.parse_args(argv)


def test_window_size_not_required_without_window_mode():
    args = _parse_args(["--modes", "no_def", "--window-size", "0", "--quiet"])

    # Should not raise when WINDOW mode is not requested
    main.validate_parameters(args)


def test_window_size_required_for_window_mode():
    args = _parse_args(["--modes", "window", "--window-size", "0", "--quiet"])

    with pytest.raises(SystemExit):
        main.validate_parameters(args)


def test_negative_window_size_is_rejected():
    args = _parse_args(["--modes", "no_def", "--window-size", "-1", "--quiet"])

    with pytest.raises(SystemExit):
        main.validate_parameters(args)


def test_attack_mode_default_uses_centralized_default():
    args = _parse_args(["--modes", "no_def", "--quiet"])
    assert args.attack_mode == DEFAULT_ATTACK_MODE.value
