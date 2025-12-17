# Contributing to CodeRally

Thank you for your interest in contributing to CodeRally! This document provides guidelines and standards for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment. Please:

- Be respectful and considerate in communications
- Accept constructive criticism gracefully
- Focus on what's best for the community
- Show empathy towards other contributors

### Unacceptable Behavior

- Harassment or discriminatory language
- Trolling, insulting comments, or personal attacks
- Publishing others' private information
- Other conduct inappropriate for a professional setting

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- Familiarity with FastAPI (backend) and React (frontend)

### Initial Setup

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/YOUR_USERNAME/code-rally.git
cd code-rally

# Add upstream remote
git remote add upstream https://github.com/ettoreferranti/code-rally.git

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Run tests to verify setup
cd ../backend
pytest tests/
cd ../frontend
npm test  # (when tests are added)
```

---

## Development Workflow

### Branch Strategy

- `main` branch is protected and represents production-ready code
- Create feature branches from `main`:
  - `feature/issue-number-short-description` (e.g., `feature/123-add-nitro-boost`)
  - `fix/issue-number-bug-description` (e.g., `fix/456-collision-detection`)
  - `docs/description` (e.g., `docs/update-bot-api-guide`)

### Workflow Steps

1. **Check for existing issues**
   ```bash
   gh issue list --milestone "M2: Racing"
   ```

2. **Create or assign yourself to an issue**
   - Comment on the issue to indicate you're working on it
   - Get clarification if requirements are unclear

3. **Create a feature branch**
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/123-add-feature
   ```

4. **Make your changes**
   - Write code following [coding standards](#coding-standards)
   - Add tests for new functionality
   - Update documentation if needed

5. **Test thoroughly**
   ```bash
   # Backend tests
   cd backend
   pytest tests/ -v

   # Frontend tests (when available)
   cd frontend
   npm test

   # Manual testing
   # Test your feature in both single-player and multiplayer modes
   ```

6. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add nitro boost system (#123)"
   ```
   See [commit message guidelines](#commit-message-format) below.

7. **Push to your fork**
   ```bash
   git push origin feature/123-add-feature
   ```

8. **Create a pull request**
   - Go to GitHub and create a PR from your branch to `main`
   - Fill out the PR template completely
   - Link the related issue(s)

---

## Coding Standards

### Python (Backend)

#### Style Guide

- Follow **PEP 8** style guide
- Use **type hints** on all functions
- Maximum line length: **88 characters** (Black formatter default)
- Use **docstrings** for all public functions and classes

#### Code Example

```python
"""
Module docstring explaining purpose.
"""

from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class CarState:
    """
    Represents the physical state of a car.

    Attributes:
        position: Position in 2D space (units)
        velocity: Velocity vector (units/second)
        heading: Direction car is facing (radians)
    """
    position: Tuple[float, float]
    velocity: Tuple[float, float]
    heading: float


def calculate_speed(velocity: Tuple[float, float]) -> float:
    """
    Calculate speed from velocity vector.

    Args:
        velocity: Velocity vector (vx, vy)

    Returns:
        float: Speed magnitude in units/second

    Example:
        >>> calculate_speed((3.0, 4.0))
        5.0
    """
    vx, vy = velocity
    return (vx ** 2 + vy ** 2) ** 0.5
```

#### Imports Order

```python
# 1. Standard library
import math
from dataclasses import dataclass

# 2. Third-party packages
from fastapi import APIRouter
from sqlalchemy import Column

# 3. Local imports
from app.config import get_settings
from app.core.physics import CarPhysics
```

### TypeScript/React (Frontend)

#### Style Guide

- Follow **TypeScript strict mode**
- Use **functional components** with hooks
- Use **named exports** (not default exports)
- Maximum line length: **100 characters**
- Use **JSDoc comments** for complex functions

#### Code Example

```typescript
/**
 * Game state types for CodeRally.
 */

export interface CarState {
  /** Position in 2D space (units) */
  position: Vector2;
  /** Velocity vector (units/second) */
  velocity: Vector2;
  /** Direction car is facing (radians, 0 = right) */
  heading: number;
}

/**
 * Calculate speed from velocity vector.
 *
 * @param velocity - Velocity vector
 * @returns Speed magnitude in units/second
 */
export function calculateSpeed(velocity: Vector2): number {
  return Math.sqrt(velocity.x ** 2 + velocity.y ** 2);
}

/**
 * Game canvas component for rendering the race.
 */
export const GameCanvas: React.FC<GameCanvasProps> = ({ gameState, onInput }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    // Setup code
    return () => {
      // Cleanup code
    };
  }, []);

  return <canvas ref={canvasRef} />;
};
```

### General Best Practices

1. **Keep functions small and focused** - Each function should do one thing well
2. **Avoid deep nesting** - Max 3 levels of indentation
3. **Use meaningful variable names** - `car_position` not `cp`
4. **Don't repeat yourself (DRY)** - Extract common code into functions
5. **Comment the "why", not the "what"** - Code explains what, comments explain why
6. **Handle errors gracefully** - Don't let exceptions crash the application

---

## Testing Requirements

### Backend Tests

All backend code must include tests. Use **pytest**.

#### Test Structure

```python
"""Tests for physics module."""

import pytest
from app.core.physics import CarPhysics, Vector2, CarState


class TestCarPhysics:
    """Test cases for CarPhysics class."""

    def test_acceleration_increases_speed(self):
        """Test that acceleration increases car speed."""
        physics = CarPhysics()
        state = CarState(
            position=Vector2(0, 0),
            velocity=Vector2(0, 0),
            heading=0
        )

        # Apply acceleration for 1 second
        new_state = physics.apply_acceleration(state, dt=1.0)

        assert new_state.velocity.magnitude() > 0

    def test_braking_decreases_speed(self):
        """Test that braking decreases car speed."""
        # ... test implementation
```

#### Running Tests

```bash
cd backend

# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_physics.py

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run verbose
pytest tests/ -v
```

#### Test Coverage Requirements

- **Minimum 80% coverage** for new code
- All public functions must have tests
- Edge cases must be tested (e.g., zero values, boundary conditions)

### Frontend Tests

Frontend tests use **React Testing Library** (to be implemented).

```typescript
import { render, screen } from '@testing-library/react';
import { GameCanvas } from './GameCanvas';

describe('GameCanvas', () => {
  it('renders canvas element', () => {
    const mockState = { /* ... */ };
    render(<GameCanvas gameState={mockState} onInput={() => {}} />);

    const canvas = screen.getByRole('canvas');
    expect(canvas).toBeInTheDocument();
  });
});
```

---

## Commit Message Format

Follow **Conventional Commits** specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates

### Examples

```bash
# Feature
git commit -m "feat(physics): add nitro boost system"

# Bug fix
git commit -m "fix(collision): correct boundary detection for curved segments"

# Documentation
git commit -m "docs: update bot API guide with checkpoint examples"

# With body and footer
git commit -m "feat(multiplayer): add race lobby system

Implement lobby where players can join before race starts.
Includes ready status and countdown timer.

Closes #126"
```

### PR Title Format

PR titles should follow the same format as commits:

```
feat(physics): add nitro boost system (#123)
```

Always reference the issue number in the PR title.

---

## Pull Request Process

### Before Creating a PR

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated (if needed)
- [ ] Commit messages follow format
- [ ] Branch is up to date with `main`

### PR Template

When creating a PR, fill out this template:

```markdown
## Description
Brief description of what this PR does.

## Related Issue
Closes #123

## Changes Made
- Added nitro boost mechanics to physics engine
- Updated car state to track nitro charges
- Added visual effects for nitro activation

## Testing Done
- [ ] Unit tests pass
- [ ] Manual testing in single-player mode
- [ ] Manual testing in multiplayer mode
- [ ] Tested edge cases (e.g., using nitro with 0 charges)

## Screenshots (if applicable)
[Add screenshots or GIFs showing the changes]

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or breaking changes documented)
```

### Review Process

1. **Automated checks** run (tests, linting)
2. **Maintainer review** - At least one maintainer must approve
3. **Address feedback** - Make requested changes
4. **Squash and merge** - PRs are squashed into a single commit on merge

### Review Timeline

- Expect initial review within **48 hours**
- Complex PRs may take longer
- Tag maintainers if no response after 3 days

---

## Issue Guidelines

### Creating Issues

#### Bug Report Template

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g., macOS 13.0]
- Browser: [e.g., Chrome 120]
- Version: [e.g., 0.1.0]

**Additional context**
Any other relevant information.
```

#### Feature Request Template

```markdown
**Feature Description**
Clear description of the proposed feature.

**Use Case**
Describe why this feature would be useful.

**Proposed Implementation**
(Optional) Ideas on how to implement this.

**Alternatives Considered**
Other approaches you've thought about.

**Additional Context**
Related issues, screenshots, mockups, etc.
```

### Issue Labels

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `enhancement` | New feature or improvement |
| `documentation` | Documentation improvements |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention needed |
| `milestone-X` | Part of milestone X |
| `backend` | Backend-related |
| `frontend` | Frontend-related |
| `game-engine` | Game engine/physics |
| `bot-system` | Bot programming system |

---

## Architecture Decisions

### When to Discuss Architecture

Open an issue for discussion before implementing:

- New major features
- Breaking changes
- Changes to public APIs
- Performance optimizations that change behavior
- New dependencies

### Architecture Review

Major architectural changes require:
1. GitHub issue with proposal
2. Discussion with maintainers
3. Approval before implementation
4. Documentation updates

---

## Questions?

- **General questions**: Open a GitHub Discussion
- **Bug reports**: Open an issue
- **Security issues**: Email maintainers directly (see README)
- **Feature proposals**: Open an issue with `enhancement` label

---

## Recognition

Contributors are recognized in:
- GitHub contributors list
- Release notes for significant contributions
- Special thanks in documentation

Thank you for contributing to CodeRally! 🏎️
