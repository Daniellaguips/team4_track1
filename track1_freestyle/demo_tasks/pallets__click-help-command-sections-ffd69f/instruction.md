# Help sections for subcommands

A group with many subcommands prints them all under one `Commands:` heading. Allow commands to
declare a help section so the group's help page lists them under separate headings.

## Public interface

- New keyword argument `help_section: str | None = None` on `click.Command.__init__`, stored as
  the attribute `Command.help_section`. It is therefore accepted by `@click.command(...)`,
  `@group.command(...)`, `@group.group(...)` and `click.Group(...)`.
- `Command.to_info_dict()` output does **not** change.
- The rendering lives in `Group.format_commands(ctx, formatter)`.

## Requirements

**R1 — Which commands.** As today, the listed commands are those returned by
`self.list_commands(ctx)` for which `get_command` returns a command that is not hidden, in that
order.

**R2 — Default section.** Commands whose `help_section` is `None` or exactly `"Commands"` are
listed in the default section with the heading `Commands` (the same heading as today).

**R3 — Named sections.** Every other `help_section` value is a section heading of its own, used
verbatim (case-sensitive; `"Admin"` and `"admin"` are different sections). Inside a section,
commands keep the R1 order.

**R4 — Section order.** The default section is placed before all named sections. Named sections are ordered
sorted alphabetically by section name (plain string comparison). Sections without any listed command (e.g. only hidden commands) are not printed.

**R5 — Rendering.** Each section is written exactly like today's commands section — with
`formatter.section(<heading>)` followed by `formatter.write_dl(rows)` where a row is
`(command name, short help)` — so the output for a section looks like:

```
Admin:
  purge-cache  Drop caches.
```

Because each section is a separate `write_dl` call, the description column is aligned
independently within each section. The short-help length limit stays one value computed over
**all** listed commands, as today: `formatter.width - 6 - <length of the longest listed command
name>`, passed to `cmd.get_short_help_str(limit)`.

**R6 — Compatibility.** When no listed command has a named section, the help output is identical
to the current output.
