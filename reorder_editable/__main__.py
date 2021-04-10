import os
import sys
from typing import Sequence, List, Callable, Optional

import click

from .core import Editable, ReorderEditableError


def absdirs(pos: Sequence[str]) -> List[str]:
    """
    Convert all paths to abolsute paths, and make sure they all exist
    """
    res = []
    for p in pos:
        absfile = os.path.abspath(os.path.expanduser(p))
        if not os.path.exists(absfile):
            click.echo(f"{absfile} does not exist", err=True)
            sys.exit(1)
        res.append(absfile)
    return res


@click.group()
def main() -> None:
    """
    Manage your editable namespace packages - your easy-install.pth file
    """
    pass


def _print_editable_contents(stderr: bool = False) -> None:
    click.echo(Editable().location.read_text(), nl=False, err=stderr)


@main.command(short_help="print easy-install.pth contents")
def cat() -> None:
    """
    Locate and print the contents of your easy-install.pth
    """
    try:
        _print_editable_contents()
    except ReorderEditableError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


# shared click options/args between check/reorder
SHARED = [
    click.option(
        "-e",
        "--easy-install-location",
        "ei",
        default=None,
        help="Manually provide path to easy-install.pth",
    ),
    click.argument("DIRECTORY", nargs=-1, required=True),
]


# decorator to apply arguments
def shared(func: Callable[..., None]) -> Callable[..., None]:
    for s in SHARED:
        func = s(func)
    return func


@main.command(short_help="check easy-install.pth")
@shared
def check(ei: Optional[str], directory: Sequence[str]) -> None:
    """
    If the order specified in your easy-install.pth doesn't match
    the order of the directories specified as positional arguments,
    exit with a non-zero exit code

    Also fails if one of the paths you provide doesn't exist

    \b
    e.g.
    reorder_editable check ./path/to/repo /another/path/to/repo

    In this case, ./path/to/repo should be above ./another/path/to/repo
    in your easy-install.pth file
    """
    dirs = absdirs(directory)
    try:
        Editable(ei).assert_ordered(dirs)
    except ReorderEditableError as exc:
        click.echo("Error: " + str(exc))
        _print_editable_contents(stderr=True)
        sys.exit(1)


@main.command(short_help="reorder easy-install.pth")
@shared
def reorder(ei: Optional[str], directory: Sequence[str]) -> None:
    """
    If the order specified in your easy-install.pth doesn't match
    the order of the directories specified as positional arguments,
    reorder them so that it does. This always places items
    you're reordering at the end of your easy-install.pth so
    make sure to include all items you care about the order of

    Also fails if one of the paths you provide doesn't exist, or
    it isn't already in you easy-install.pth

    \b
    e.g.
    reorder_editable reorder ./path/to/repo /another/path/to/repo

    If ./path/to/repo was below /another/path/to/repo, this would
    reorder items in your config file to fix it so that ./path/to/repo
    is above /another/path/to/repo
    """
    dirs = absdirs(directory)
    try:
        Editable(ei).reorder(dirs)
    except ReorderEditableError as exc:
        click.echo("Error: " + str(exc))
        _print_editable_contents(stderr=True)
        sys.exit(1)


if __name__ == "__main__":
    main(prog_name="reorder_editable")