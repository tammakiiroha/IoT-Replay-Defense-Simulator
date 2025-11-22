# Contributing to Replay Attack Simulation

Thank you for your interest in contributing to this project! This document provides guidelines for contributing.

## How to Contribute

### Reporting Issues

If you find a bug or have a suggestion:

1. Check if the issue already exists in the [Issues](https://github.com/tammakiiroha/Replay-simulation/issues) section
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Your environment (OS, Python version)

### Submitting Changes

1. **Fork the repository**
   ```bash
   git clone https://github.com/tammakiiroha/Replay-simulation.git
   cd Replay-simulation
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new features
   - Update documentation as needed

4. **Test your changes**
   ```bash
   # Run tests
   python3 -m pytest tests/
   
   # Run a quick simulation
   python3 main.py --runs 10 --modes window
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

6. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style Guidelines

### Python Code

- Follow PEP 8 style guide
- Use type hints where appropriate
- Add docstrings for functions and classes
- Keep functions focused and concise

Example:
```python
def compute_acceptance_rate(accepted: int, total: int) -> float:
    """
    Calculate the acceptance rate.
    
    Args:
        accepted: Number of accepted frames
        total: Total number of frames
        
    Returns:
        Acceptance rate as a percentage (0-100)
    """
    if total == 0:
        return 0.0
    return (accepted / total) * 100
```

### Documentation

- Use clear, concise language
- Provide examples where helpful
- Keep README files up to date
- Maintain consistency across language versions (EN/ZH/JA)

## Project Structure

```
.
├── main.py              # Main entry point
├── gui.py               # Graphical interface
├── sim/                 # Core simulation modules
│   ├── sender.py        # Sender logic
│   ├── receiver.py      # Receiver and defense mechanisms
│   ├── channel.py       # Channel simulation
│   ├── attacker.py      # Attacker model
│   ├── experiment.py    # Monte Carlo experiments
│   └── security.py      # Cryptographic primitives
├── scripts/             # Analysis and plotting scripts
├── tests/               # Test suite
└── docs/                # Documentation

```

## Testing

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/

# Run specific test file
python3 -m pytest tests/test_receiver.py

# Run with coverage
python3 -m pytest --cov=sim tests/
```

### Adding Tests

- Place test files in the `tests/` directory
- Name test files as `test_*.py`
- Use descriptive test function names
- Test both normal and edge cases

Example:
```python
def test_window_accepts_reordered_frames():
    """Test that sliding window accepts out-of-order frames."""
    # Setup
    state = ReceiverState(mode=Mode.WINDOW, window_size=5)
    
    # Test
    result = verify_frame(frame, state, key)
    
    # Assert
    assert result[0] == True
```

## Adding New Features

### New Defense Mechanism

1. Add the mode to `sim/types.py`:
   ```python
   class Mode(Enum):
       YOUR_MODE = "your_mode"
   ```

2. Implement verification in `sim/receiver.py`:
   ```python
   def _verify_your_mode(frame, state, key):
       # Your implementation
       pass
   ```

3. Add tests in `tests/test_receiver.py`

4. Update documentation in README files

### New Experiment

1. Add configuration to `scripts/experiment_config.py`
2. Implement sweep logic in `scripts/run_sweeps.py`
3. Add plotting function in `scripts/plot_results.py`
4. Document parameters in `EXPERIMENTAL_PARAMETERS_EN.md`

## Documentation Updates

When updating documentation:

1. **Maintain consistency** across all language versions:
   - `README.md` (English)
   - `README_CH.md` (Chinese)
   - `README_JP.md` (Japanese)

2. **Update all relevant files**:
   - Main README files
   - PRESENTATION technical documents
   - EXPERIMENTAL_PARAMETERS configuration docs

3. **Verify links** work correctly on GitHub

## Commit Message Guidelines

Use conventional commit format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Adding or updating tests
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `style:` Code style changes (formatting, etc.)

Examples:
```
feat: add challenge-response defense mechanism
fix: correct window size calculation in receiver
docs: update README with new installation steps
test: add tests for attacker replay logic
```

## Questions?

If you have questions:

1. Check the [README](README.md) and [PRESENTATION](PRESENTATION_EN.md) documents
2. Look at existing code for examples
3. Open an issue for discussion

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to make this project better! 🎉

