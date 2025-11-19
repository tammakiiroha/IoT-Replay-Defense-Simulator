# Contributing Guide

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/tammakiiroha/Replay-simulation.git
cd Replay-simulation
```

2. Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run tests to verify setup:
```bash
python -m pytest tests/ -v
```

## Code Structure

### Core Simulation (`sim/`)
- `types.py`: Data structures (Frame, SimulationConfig, ReceiverState, etc.)
- `sender.py`: Generates legitimate frames with counters and MACs
- `receiver.py`: Verification logic for all defense modes
- `channel.py`: Simulates packet loss and reordering
- `attacker.py`: Record-and-replay attack model
- `experiment.py`: Monte Carlo simulation runner
- `security.py`: Cryptographic primitives (MAC, constant-time compare)
- `commands.py`: Command sequence loading and generation

### Scripts (`scripts/`)
- `run_sweeps.py`: Automated parameter sweeps for thesis experiments
- `plot_results.py`: Generate publication-quality figures
- `export_tables.py`: Convert JSON results to Markdown tables

### Tests (`tests/`)
- `test_receiver.py`: Unit tests for receiver verification logic

## Adding New Features

### Adding a new defense mode
1. Add enum value to `Mode` in `sim/types.py`
2. Implement verification function in `sim/receiver.py`
3. Update `VERIFIER_MAP` in `sim/receiver.py`
4. Add test cases in `tests/test_receiver.py`

### Adding new metrics
1. Extend `RunStats` and `AggregateStats` in `sim/types.py`
2. Update aggregation logic in `sim/experiment.py`
3. Modify plotting functions in `scripts/plot_results.py`

## Testing

Run all tests:
```bash
python -m pytest tests/ -v
```

Run with coverage:
```bash
pip install pytest-cov
python -m pytest tests/ --cov=sim --cov-report=html
```

## Code Style

- Use type hints for all function parameters and return values
- Follow PEP 8 naming conventions
- Add docstrings to public functions and classes
- Keep functions focused and under 50 lines when possible

## Submitting Changes

1. Create a new branch for your feature
2. Make your changes and add tests
3. Ensure all tests pass
4. Update documentation (README.md, docstrings)
5. Submit a pull request with a clear description

## Questions?

Open an issue on GitHub: https://github.com/tammakiiroha/Replay-simulation/issues

