# Agent guide

Instructions for AI coding agents working in this repo. The README covers
setup, configuration and the MCP tools. Planned changes live in `openspec/`.

## Commands

```sh
make install   # uv sync
make lint      # ruff check + ruff format --check
make test      # pytest; needs a Docker/Podman socket for testcontainers
make format    # fix lint and formatting
```

Run `make lint` and `make test` before calling a change done.

## Domain layout

Code is organized by domain (`units/`, `ingredients/`, `recipes/`), with
shared infrastructure in `common/`. Each domain has:

- `models.py`: SQLAlchemy tables.
- `schemas.py`: Pydantic inputs and outputs.
- `service.py`: all of the domain's logic (reads, listing and search,
  writes), framework-free, taking a plain `Session`. Keep this as **one
  file per domain**: don't split queries or listing into separate modules.
- `tools.py`: thin MCP tool adapters over the service, with `register(mcp, sessions)`.

The Pydantic schemas are what the model sees in `tools/list`. Give a field a
`Field(description=...)` whenever its name alone could be misread (units,
whole-recipe vs per-serving values, flags like `optional`, patch semantics).
Every field of a tool's input model gets one; `tests/test_catalogue.py`
checks the recipe inputs.

## Module layout

Order every Python module in `src/` top-down, so a reader sees what the
module offers before how it works:

1. Module docstring, then imports.
2. Constants and module-level values: configuration, type aliases, loggers,
   compiled regexes. Private constants (`_NAME`) go here too.
3. Public definitions: functions and classes without a leading underscore,
   most important first.
4. Private helpers (`_name`) at the bottom, roughly in the order the public
   code uses them.

Inside a class, the same order applies: class attributes first, then
`__init__` and other dunder methods, then public methods, then private ones.

**The one exception:** a helper that runs while the module is being
imported has to be defined before the line that calls it. That covers a
helper called to build a constant (`Number = Annotated[..., PlainSerializer(_json_number)]`),
or a helper called inside a class body (`json_schema_extra=_drop_defaults`,
`column_property(_per_serving(...))`). Put such a helper directly above its
first use, and keep the constants that depend on it as close to the top as
the dependency allows. Don't work around it with lambdas or late binding.
`common/fields.py` shows the pattern.

Calls from inside function bodies are resolved at call time, so they never
need the helper defined first.
