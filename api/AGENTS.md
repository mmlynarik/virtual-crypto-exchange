# AGENTS.md

Backend-level guidance for coding agents working in `Virtual Crypto Exchange API`.

## Scope and precedence

- Applies to the `api` folder only

## Environment and setup

- Python: `>=3.14` (see `pyproject.toml`).
- Use `uv` for dependency/runtime commands.

## Minimal verification defaults

- Migration check: `just checkmig`
- Apply migrations (when needed): `just migrate`
- Tests: `uv run pytest`
- CI parity lint/format: `uv run pre-commit run --all-files`
- Other project commands: `justfile` (semantically named targets for common tasks)

## Python guidelines

- Build business logic around classes that represent the domain, rather than around free functions.
  Logic that depends on an object's own data belongs on its class as a method or property
  (the "fat models" approach, applied to any domain class);
  orchestration across several objects goes to a separate class.
- Use pydantic dataclasses instead of stdlib dataclasses for their built-in validation. Use pydantic `BaseModel` when validating user input or where JSON (de)serialization is needed.
- Helper functions:
  - Used by a single class: a `@staticmethod` on that class.
  - Used in several places: a plain function in utils module of the nearest package
    shared by its callers, not a class holding only static methods.
- Write tests first. For each change, write or update the tests, run them and see them fail for the
  expected reason, then implement until they pass.

## Skill routing

- Adding, changing, reviewing or testing a FastAPI route or a domain's `router.py`:
  `.agents/skills/fastapi-router/SKILL.md` (the auth domain's route conventions).


## Non-negotiable guardrails

- Before destructive actions, confirm clearly and keep the impact as small as possible.
- Read relevant files in `docs/` before implementing unfamiliar features.
- When implementation details are uncertain or version-sensitive, use MCP tools to fetch authoritative external references and validate against repository patterns.
