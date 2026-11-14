"""Capability cards: each fixes an AREA of click and a capability SHAPE. The model picks the
concrete feature inside it. Variation comes from the cards differing in what kind of reasoning
the feature needs (value parsing vs argv rewriting vs output layout vs test isolation vs
interactive/completion behavior), not in wording."""

CARDS = {
    "types": {
        "blueprint": "click.Duration: a ParamType converting human durations such as '1h30m', "
        "'90s', '2d 4h' into an int number of seconds (or timedelta), with unit order, duplicate "
        "units, decimals, overflow and min/max bounds rules",
        "shape": "a new ParamType that parses a structured human-written value into a Python value, "
        "with exact arithmetic or normalization rules, bounds, and exact error messages",
        "ground": ["src/click/types.py", "src/click/__init__.py", "tests/test_imports.py"],
        "p2p": [
            "tests/test_imports.py",
            "tests/test_info_dict.py",
            "tests/test_types/test_IntRange.py",
            "tests/test_types/test_FloatRange.py",
            "tests/test_types/test_ParamType.py",
            "tests/test_types/test_convert_type.py",
            "tests/test_options.py",
        ],
        "test_dir": "tests/test_types",
    },
    "argv": {
        "shape": "argument-list preprocessing before parsing (for example expanding @response-file "
        "arguments, with quoting, comments, nesting/recursion limits, escapes, and error rules), "
        "opt-in via a new keyword argument on Command/Context",
        "ground": ["src/click/core.py", "src/click/parser.py", "src/click/utils.py"],
        "p2p": [
            "tests/test_basic.py",
            "tests/test_commands.py",
            "tests/test_arguments.py",
            "tests/test_parser.py",
            "tests/test_context.py",
        ],
        "test_dir": "tests",
    },
    "help": {
        "shape": "a help-page rendering feature with a precise layout contract (ordering, grouping, "
        "wrapping, alignment, truncation) that is opt-in and leaves default help output unchanged",
        "ground": ["src/click/formatting.py", "src/click/core.py"],
        "p2p": [
            "tests/test_formatting.py",
            "tests/test_basic.py",
            "tests/test_commands.py",
            "tests/test_options.py",
        ],
        "test_dir": "tests",
    },
    "testing": {
        "shape": "a CliRunner / Result capability for tests (isolation, captured state, environment "
        "or filesystem bookkeeping, assertion helpers) with exact semantics across invocations",
        "ground": ["src/click/testing.py"],
        "p2p": ["tests/test_testing.py", "tests/test_basic.py", "tests/test_utils"],
        "test_dir": "tests",
    },
    "completion": {
        "shape": "a shell-completion behavior change (candidate generation, filtering, ordering, "
        "descriptions) with precise rules, opt-in, default behavior unchanged",
        "ground": ["src/click/shell_completion.py", "src/click/types.py"],
        "p2p": ["tests/test_shell_completion.py", "tests/test_basic.py"],
        "test_dir": "tests",
    },
    "sources": {
        "blueprint": "a new opt-in value source for options (e.g. a per-command `config` mapping or "
        "file) slotted into click's existing resolution order CLI > envvar > default_map > prompt > "
        "default, reported through ParameterSource, shown in --help, and honoured for multiple=True, "
        "nargs, is_flag/flag_value and counting options",
        "shape": "precedence across many existing value sources, cross-module (core + types + help)",
        "ground": ["src/click/core.py", "src/click/types.py", "src/click/decorators.py", "src/click/__init__.py"],
        "p2p": ["tests/test_options.py", "tests/test_defaults.py", "tests/test_context.py",
                "tests/test_basic.py", "tests/test_imports.py"],
        "test_dir": "tests",
    },
    "state": {
        "blueprint": "an invocation-scoped feature (e.g. per-run deprecation/usage tracking or "
        "call-ledger on the Context) that must propagate through ctx.invoke, ctx.forward, nested and "
        "chained groups and result_callback, be visible to custom context_class subclasses, and reset "
        "between separate CliRunner.invoke calls",
        "shape": "state across calls + extension points + cross-module (core + testing)",
        "ground": ["src/click/core.py", "src/click/testing.py", "src/click/decorators.py", "src/click/__init__.py"],
        "p2p": ["tests/test_context.py", "tests/test_chain.py", "tests/test_commands.py",
                "tests/test_testing.py", "tests/test_basic.py"],
        "test_dir": "tests",
    },
    "argv_hard": {
        "blueprint": "@response-file argument expansion that is opt-in per Context, applies before "
        "parsing in main() and in ctx.invoke-based subcommand dispatch, interacts with '--' and "
        "chained groups, is reflected in shell completion and usage errors, and works with a "
        "custom context_class",
        "shape": "argv rewriting across core + parser + shell_completion with extension points",
        "ground": ["src/click/core.py", "src/click/parser.py", "src/click/shell_completion.py", "src/click/__init__.py"],
        "p2p": ["tests/test_basic.py", "tests/test_commands.py", "tests/test_arguments.py",
                "tests/test_parser.py", "tests/test_shell_completion.py", "tests/test_chain.py"],
        "test_dir": "tests",
    },
    "help_hard": {
        "blueprint": "grouping commands and options into titled help sections with explicit ordering "
        "rules that must hold for nested Groups, chain=True groups, hidden/deprecated commands, user "
        "subclasses overriding format_commands/format_options, and stay consistent with shell "
        "completion candidate order",
        "shape": "output layout + extension points + cross-module (core + formatting + completion)",
        "ground": ["src/click/core.py", "src/click/formatting.py", "src/click/shell_completion.py"],
        "p2p": ["tests/test_formatting.py", "tests/test_commands.py", "tests/test_basic.py",
                "tests/test_shell_completion.py", "tests/test_options.py"],
        "test_dir": "tests",
    },
    "argv_completion": {
        "blueprint": "opt-in @response-file expansion that is shared CORRECTLY between normal parsing and "
        "shell completion: recursive includes resolved relative to the including file, a cycle error "
        "naming the include stack, '--' stops expansion, the incomplete word being completed is never "
        "expanded, each file read exactly once per invocation, the same file may be included twice "
        "non-recursively. ctx.invoke/ctx.forward are unchanged (N/A). Completion follows UNCHANGED click "
        "8.5.1 precedence for an option-looking incomplete word; response-file reader errors during completion "
        "are handled by ONE stated rule (no contradicting 'never escapes' rule); token-occurrence identity is "
        "defined by position in the original argv. The exact token '--' is NEVER a response-file token, "
        "whatever the configured prefix.",
        "shape": "one semantic feature on two distinct execution paths (parse + completion) with recursion and I/O state",
        "ground": ["src/click/core.py", "src/click/parser.py", "src/click/shell_completion.py", "src/click/__init__.py"],
        "p2p": ["tests/test_basic.py", "tests/test_parser.py", "tests/test_shell_completion.py",
                "tests/test_commands.py", "tests/test_arguments.py"],
        "test_dir": "tests",
    },
    "lazy_defaults": {
        "blueprint": "options whose default is computed from OTHER parameters' final values: an explicit "
        "dependency DAG, evaluation only after all sources are resolved, a dependent default is "
        "suppressed when its own value came from CLI/env/default_map, falsey values are real values, "
        "cycle errors name the cycle, computed once per context, and NEVER evaluated while rendering "
        "--help or during shell completion. ParameterSource reports a new DEPENDENT source without "
        "renumbering existing members. MUST define: resilient parsing evaluates nothing and leaves explicitly "
        "resolved values untouched; with a cycle in resilient mode, callbacks run in declaration order ignoring "
        "edges; dependents receive a fresh kwargs mapping of original values (no deep copy); invalid "
        "depends_on containers and duplicate dependency names raise a stated error; retry semantics after "
        "default_from raises on the same Context are stated. Callback multiplicity of ordinary and prompted "
        "parameters stays EXACTLY as in click 8.5.1 (a prompt may call a callback more than once); only "
        "computed non-prompt dependents promise exactly-once. Duplicate storage names involving a dependent "
        "are rejected with a stated error.",
        "shape": "cross-parameter dependency resolution across parse, help and completion paths",
        "ground": ["src/click/core.py", "src/click/shell_completion.py", "src/click/decorators.py", "src/click/__init__.py"],
        "p2p": ["tests/test_options.py", "tests/test_defaults.py", "tests/test_basic.py",
                "tests/test_shell_completion.py", "tests/test_context.py"],
        "test_dir": "tests",
    },
    "atomic_output": {
        "blueprint": "opt-in buffered output for a command tree: click.echo output is committed to the "
        "real stream ONLY after the whole ROOT invocation (including result_callback and chained "
        "subcommands) succeeds; on any exception or ctx.exit with non-zero code it is discarded "
        "(stderr policy stated explicitly); nested groups share the root's buffer (no double commit); "
        "ctx.exit(0) commits; CliRunner observes exactly the committed bytes.",
        "shape": "transactional state across nested/chained invocation with success/failure/rollback paths",
        "ground": ["src/click/core.py", "src/click/utils.py", "src/click/testing.py", "src/click/__init__.py"],
        "p2p": ["tests/test_basic.py", "tests/test_chain.py", "tests/test_commands.py",
                "tests/test_testing.py", "tests/test_utils"],
        "test_dir": "tests",
    },
}
