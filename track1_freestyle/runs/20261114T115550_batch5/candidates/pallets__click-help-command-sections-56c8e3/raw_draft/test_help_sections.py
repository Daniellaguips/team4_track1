import click
from click.testing import CliRunner


def _cli():
    @click.group()
    def cli():
        pass

    @cli.command(help="Create a repo.")
    def init():
        pass

    @cli.command(help="Drop caches.", help_section="Users")
    def purge_cache():
        pass

    @cli.command(help="Export data.", help_section="Data")
    def export():
        pass

    @cli.command(help="Sync it.")
    def sync():
        pass

    @cli.command(help="Add a user.", help_section="Users")
    def adduser():
        pass

    @cli.command(help="Secret.", help_section="Ops", hidden=True)
    def zap():
        pass

    return cli


def _help(cli):
    r = CliRunner().invoke(cli, ["--help"])
    assert r.exit_code == 0, r.output
    return r.output


def _headings(out):
    return [l[:-1] for l in out.splitlines() if l and not l.startswith(" ") and l.endswith(":")
            and l != "Options:"]


def test_attribute():
    """[R2 interface] help_section stored on Command, default None."""
    assert click.Command("x").help_section is None
    assert click.Command("x", help_section="Admin").help_section == "Admin"
    assert click.Group("g", help_section="Admin").help_section == "Admin"
    assert "help_section" not in click.Command("x", help_section="A").to_info_dict(
        click.Context(click.Command("x")))


def test_sections_and_order():
    """[R1][R2][R3][R4]"""
    assert _headings(_help(_cli())) == ['Data', 'Users', 'Commands']


def test_rows_per_section_aligned_independently():
    """[R3][R5]"""
    out = _help(_cli())
    assert "Commands:\n  init  Create a repo.\n  sync  Sync it.\n" in out
    assert "Users:\n  adduser      Add a user.\n  purge-cache  Drop caches.\n" in out
    assert "Data:\n  export  Export data.\n" in out


def test_hidden_only_section_omitted():
    """[R1][R4]"""
    out = _help(_cli())
    assert "Ops" not in out
    assert "zap" not in out


def test_explicit_commands_section_merges_with_default():
    """[R2]"""
    @click.group()
    def cli():
        pass

    @cli.command(help="One.", help_section="Commands")
    def one():
        pass

    @cli.command(help="Two.")
    def two():
        pass

    out = _help(cli)
    assert _headings(out) == ["Commands"]
    assert "Commands:\n  one  One.\n  two  Two.\n" in out


def test_case_sensitive_names():
    """[R3][R4]"""
    @click.group()
    def cli():
        pass

    @cli.command(help_section="Admin")
    def b():
        pass

    @cli.command(help_section="admin")
    def a():
        pass

    assert _headings(_help(cli)) == ['Admin', 'admin']


def test_only_named_sections():
    """[R4] no default section when every command is in a named section."""
    @click.group()
    def cli():
        pass

    @cli.command(help_section="Zeta")
    def a():
        pass

    @cli.command(help_section="Alpha")
    def b():
        pass

    assert _headings(_help(cli)) == ['Alpha', 'Zeta']


def test_short_help_limit_uses_all_commands():
    """[R5]"""
    long_help = "This sentence is definitely much longer than thirty two characters in total."

    @click.group(context_settings={"terminal_width": 60})
    def cli():
        pass

    @cli.command(help=long_help)
    def a():
        pass

    @cli.command("very-long-command-name", help="Short.", help_section="Admin")
    def v():
        pass

    out = _help(cli)
    expected = cli.commands["a"].get_short_help_str(60 - 6 - len("very-long-command-name"))
    assert expected.endswith("...")
    assert f"Commands:\n  a  {expected}\n" in out


def test_no_sections_output_unchanged():
    """[R6]"""
    @click.group()
    def cli():
        pass

    @cli.command(help="Hello.")
    def hello():
        pass

    @cli.command(help="World.")
    def world():
        pass

    out = _help(cli)
    assert out.endswith("Commands:\n  hello  Hello.\n  world  World.\n")
    assert cli.commands["hello"].help_section is None


def test_subgroup_section():
    """[R3] groups can be placed in sections too."""
    @click.group()
    def cli():
        pass

    @cli.group(help="Manage users.", help_section="Admin")
    def users():
        pass

    @cli.command(help="Run.")
    def run():
        pass

    out = _help(cli)
    assert "Admin:\n  users  Manage users.\n" in out
