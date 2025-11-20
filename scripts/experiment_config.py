"""
Experimental Parameters Configuration

This module centralizes all experimental parameters for the replay attack
defense evaluation study. It ensures consistency between documentation and
code implementation.

For detailed parameter justification, see:
- Documentation: EXPERIMENTAL_PARAMETERS.md
- Technical details: PRESENTATION.zh.md (Lines 710-829)

Version: 1.0
Last Updated: 2024
"""

# ============================================================================
# Core Fixed Parameters
# ============================================================================

RUNS = 200  # Monte Carlo iterations (95% confidence level)
NUM_LEGIT = 20  # Legitimate packets per run
NUM_REPLAY = 100  # Replay attack attempts per run
SEED = 42  # Fixed random seed for reproducibility
ATTACKER_LOSS = 0.0  # Ideal attacker (no recording loss)
DEFAULT_WINDOW_SIZE = 5  # Recommended sliding window size

# ============================================================================
# Experiment 1: Packet Loss Impact
# ============================================================================

EXPERIMENT_1_P_LOSS = {
    "name": "Packet Loss Impact",
    "output_file": "results/p_loss_sweep.json",
    "figure": "Figure 1",
    
    # Fixed parameters
    "runs": RUNS,
    "num_legit": NUM_LEGIT,
    "num_replay": NUM_REPLAY,
    "seed": SEED,
    "window_size": DEFAULT_WINDOW_SIZE,
    "attack_mode": "post",
    "attacker_loss": ATTACKER_LOSS,
    
    # Variable parameter
    "p_loss_values": [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    
    # Fixed channel conditions
    "p_reorder": 0.0,  # Isolate packet loss effect
}

# ============================================================================
# Experiment 2: Packet Reordering Impact
# ============================================================================

EXPERIMENT_2_P_REORDER = {
    "name": "Packet Reordering Impact",
    "output_file": "results/p_reorder_sweep.json",
    "figure": "Figure 2",
    "note": "Reveals rolling counter vulnerability in real networks",
    
    # Fixed parameters
    "runs": RUNS,
    "num_legit": NUM_LEGIT,
    "num_replay": NUM_REPLAY,
    "seed": SEED,
    "window_size": DEFAULT_WINDOW_SIZE,
    "attack_mode": "post",
    "attacker_loss": ATTACKER_LOSS,
    
    # Variable parameter
    "p_reorder_values": [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    
    # Fixed channel conditions
    "p_loss": 0.10,  # Typical IoT environment (single-variable control)
}

# ============================================================================
# Experiment 3: Window Size Tradeoff
# ============================================================================

EXPERIMENT_3_WINDOW_SIZE = {
    "name": "Window Size Tradeoff",
    "output_file": "results/window_sweep.json",
    "figure": "Figure 3",
    
    # Fixed parameters
    "runs": RUNS,
    "num_legit": NUM_LEGIT,
    "num_replay": NUM_REPLAY,
    "seed": SEED,
    "attack_mode": "inline",  # More challenging attack scenario
    "attacker_loss": ATTACKER_LOSS,
    
    # Variable parameter
    "window_sizes": [1, 3, 5, 7, 9, 15, 20],
    
    # Fixed channel conditions
    "p_loss": 0.15,      # Moderate stress
    "p_reorder": 0.15,   # Moderate stress
    
    # Test configuration
    "defense_modes": ["window"],  # Only test sliding window
}

# ============================================================================
# Default Sweep Configuration
# ============================================================================

DEFAULT_SWEEP_CONFIG = {
    "runs": RUNS,
    "num_legit": NUM_LEGIT,
    "num_replay": NUM_REPLAY,
    "seed": SEED,
    "window_size_base": DEFAULT_WINDOW_SIZE,
    "attack_mode": "post",
    "attacker_loss": ATTACKER_LOSS,
    
    # Sweep ranges
    "p_loss_values": EXPERIMENT_1_P_LOSS["p_loss_values"],
    "p_reorder_values": EXPERIMENT_2_P_REORDER["p_reorder_values"],
    "window_values": EXPERIMENT_3_WINDOW_SIZE["window_sizes"],
    
    # Output files
    "p_loss_output": EXPERIMENT_1_P_LOSS["output_file"],
    "p_reorder_output": EXPERIMENT_2_P_REORDER["output_file"],
    "window_output": EXPERIMENT_3_WINDOW_SIZE["output_file"],
}

# ============================================================================
# Utility Functions
# ============================================================================

def get_experiment_config(experiment_id: int) -> dict:
    """
    Retrieve configuration for a specific experiment.
    
    Args:
        experiment_id: Experiment number (1, 2, or 3)
    
    Returns:
        Configuration dictionary for the specified experiment
    """
    experiments = {
        1: EXPERIMENT_1_P_LOSS,
        2: EXPERIMENT_2_P_REORDER,
        3: EXPERIMENT_3_WINDOW_SIZE,
    }
    
    if experiment_id not in experiments:
        raise ValueError(
            f"Invalid experiment_id: {experiment_id}. "
            f"Must be 1, 2, or 3."
        )
    
    return experiments[experiment_id]


def print_config_summary():
    """Print summary of all experiment configurations."""
    print("=" * 70)
    print("Experimental Parameters Configuration Summary")
    print("=" * 70)
    print()
    
    print("Core Fixed Parameters:")
    print(f"  runs          = {RUNS}")
    print(f"  num_legit     = {NUM_LEGIT}")
    print(f"  num_replay    = {NUM_REPLAY}")
    print(f"  seed          = {SEED}")
    print(f"  window_size   = {DEFAULT_WINDOW_SIZE}")
    print()
    
    for exp_id in [1, 2, 3]:
        config = get_experiment_config(exp_id)
        print(f"Experiment {exp_id}: {config['name']}")
        print(f"  Output: {config['output_file']}")
        print(f"  Figure: {config['figure']}")
        
        if exp_id == 1:
            print(f"  Variable: p_loss = {config['p_loss_values']}")
            print(f"  Fixed: p_reorder = {config['p_reorder']}")
        elif exp_id == 2:
            print(f"  Variable: p_reorder = {config['p_reorder_values']}")
            print(f"  Fixed: p_loss = {config['p_loss']}")
            if "note" in config:
                print(f"  Note: {config['note']}")
        elif exp_id == 3:
            print(f"  Variable: window_size = {config['window_sizes']}")
            print(f"  Fixed: p_loss = {config['p_loss']}, "
                  f"p_reorder = {config['p_reorder']}")
            print(f"  Mode: {config['attack_mode']}")
        
        print()
    
    print("=" * 70)
    print("For details, see: EXPERIMENTAL_PARAMETERS.md")
    print("=" * 70)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    print_config_summary()
    
    print("\nTest: Retrieve Experiment 2 configuration")
    exp2 = get_experiment_config(2)
    print(f"  Variable parameter: {exp2['p_reorder_values']}")
    print(f"  Fixed parameter: p_loss = {exp2['p_loss']}")
