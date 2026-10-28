"""Behaviour evals: scripted conversations run through a real Claude model with the shipped
skill and tool, graded by plain-code checks.

- `cases.py`: the conversations and what each one must show.
- `grade.py`: the transcript format and the checks. Offline; tested in tests/test_evals_grade.py.
- `run.py`: the live runner (`python -m evals`). Needs requirements-evals.txt and an API key.

See docs/evals.md.
"""
