"""Lab subpackage for physical experiment compatibility."""

from replay.services.lab import (
    compare_sim_vs_hardware,
    load_lab_validation_artifact,
    validate_lab_run,
)

__all__ = ["compare_sim_vs_hardware", "load_lab_validation_artifact", "validate_lab_run"]
