# reorder_editable

Naive implementation to reorder my `easy-install.pth` file

It is meant to be used to make sure editable namespace packages in my `easy-install.pth` are in a specific order.

## Editable Namespace Packages?

To expand:

- Editable: A package that is installed in editable mode (like `pip install -e`), i.e., if you make any changes to the code, your changes are reflected immediately. Is useful for packages that you change very often, or while developing. See the [`site` module docs](https://docs.python.org/3.8/library/site.html) for more information on how this modifies `sys.path`
- Namespace Packages: Namespace packages let you split a package across multiple directories on disk, merging any submodules into the parent package. For more info, see [PEP420](https://www.python.org/dev/peps/pep-0420/#dynamic-path-computation)

_Sidenote_: A namespace package is typically installed using `setuptools.find_namespace_packages`, instead of `setuptools.find_packages`

So, an editable, namespace package is multiple directories on disk all installed as a single package. If any changes are made to any of the directories, the package updates immediately.

This is the current strategy [HPI](https://github.com/karlicoss/HPI) uses for extension. I can keep up to date with [upstream](https://github.com/karlicoss/HPI) and manage [my own modules](https://github.com/purarue/HPI) by installing both (or more) like:

```
pip install -e /local/clone/of/karlicoss/HPI
pip install -e /local/clone/of/purarue/HPI
```

This creates a file in your python installation that looks like this:

```bash
$ cat ~/.local/lib/python3.9/site-packages/easy-install.pth
/home/username/Repos/karlicoss/HPI
/home/username/Repos/purarue/HPI
```

... to link those installs to the paths you specified.

However, for namespace packages in particular, the order that those directories appear in the `easy-install.pth` matter. Since items in `easy-install.pth` are added to `sys.path` in order, that determines which order python searches for packages in when trying to resolve imports.

For example, given the following structure:

```
.
├── my_HPI
│   ├── package_name
│   │   ├── a.py
│   │   └── b.py
│   └── setup.py
└── upstream_HPI
    ├── package_name
    │   ├── a.py
    │   └── c.py
    └── setup.py
```

If `easy-install.pth` was ordered:

```
my_HPI
upstream_HPI
```

`import package_name.a` would import `my_HPI/package_name/a.py`, instead of `upstream_HPI/package_name/a.py`, because that's the first item it matched in the `easy-install.pth`. This process is described much more technically in the [PEP](https://www.python.org/dev/peps/pep-0420/#specification)

This is pretty much a native plugin system, as it lets me overlay specific files/modules with personal changes in my directory structure, while keeping up to date with the upstream changes. There's very little overhead since all I'm doing is adding python files to a local directory and the globally installed package immediately updates.

In the example above, I can still import `package_name.b` and `package_name.c` as normal, even though they're in different directory structures.

---

Now - to the problem this aims to solve.

There is no way to manage your `easy-install.pth` file, to make sure packages are in a defined order.

In particular, I want [my repository](https://github.com/purarue/HPI) to be above [my fork of the upstream repo](https://github.com/purarue/HPI-fork), as that means I'm able to override files from upstream with my own changes, while maintaining two separate directories - which prevents me from running into merge conflicts. While developing, I may end up uninstalling/reinstalling one or more of my local clones of the `HPI` packages, and that leads to it resolving to a file from the upstream repository, when I was expecting my own -- leading to confusing and difficult to debug errors.

The script itself is pretty basic. All `easy-install.pth` is lines of absolute paths pointing to directories, so this just takes the directories you pass as positional arguments and makes sure they're in that order in your `easy-install.pth` file by shuffling it around.

I don't believe this breaks and built-in python/pip behaviour, but please open a PR/Issue if you think there's an issue/this could be improved.

Should be noted that if you've already imported a namespace module [the `__path__` is cached](https://www.python.org/dev/peps/pep-0420/#rationale) (which determines the import order), so this (probably?) won't work if you re-order the `easy-install.pth` file after the module has already been loaded -- at least not for that python process/unless you re-import it by messing with `sys.modules` and re-import the library.

Still - at least this tells me when it breaks, and fixes it for the next time python runs, so I don't have to worry about it/do it manually.

The actual hack that runs in my `HPI` configuration script, so I never have to think about this again:

```python
def repo(name: str) -> str:
    return path.join(environ["REPOS"], name)


# https://github.com/purarue/reorder_editable
# if my easy-install.pth file was ordered wrong, fix it and exit!
from reorder_editable import Editable

if Editable().reorder([repo("HPI"), repo("HPI-fork")]):
    # this is true if we actually reordered the path, else path was already ordered
    print(
        "easy-install.pth was ordered wrong! It has been reordered, exiting to apply changes...",
        file=sys.stderr,
    )
    sys.exit(0)
```

Note: Either install all editable packages as `--user`, or all at the system level. Otherwise, the lines of text/packages are split across two separate `easy-install.pth` files, and its not possible to reorder.

## Custom editable.pth files

Instead of editing the default `.pth` file (`easy-install.pth`), you can pass a custom location in your user `site` directory, and pass the `--create-custom` flag to create the file if its missing.

The reasoning for this is slightly confusing, and it has some downsides, but it is (as of September 2025) the stopgap I'm using right now until I have an opportunity to test the additional build backends and find out if there's a easier solution.

[setuptools version 25.3 enforces a change](https://github.com/pypa/pip/issues/11457) described as follows:

> The underlying method to achieve an editable install is changing -- the execution of `setup.py develop` when pip does an editable install is being replaced by a standardised interface.

So, depending on the build backend (`setuptools`, `hatch`, `poetry`), as long as a build satisfies the requirements in [PEP 660](https://peps.python.org/pep-0660/), how it installs is not the same, so we can (maybe, depends on how your editable packages are installed) no longer depend on the hack above which just reorders the `easy-install.pth`.

In order to get imports to work in the order we wish to, we can instead depend on the CPython code that processes a `.pth` file [here](https://github.com/python/cpython/blob/5edfe55acf29f7c36f585bcff7f96c244c43f9ae/Lib/site.py#L234-L257), in particular:

```python
for name in sorted(names):
    addpackage(sitedir, name, known_paths)
```

As it sorts the `.pth` files in your site directory, sort of like [`rc`/alphabetical style init systems](https://linux-training.be/sysadmin/ch15.html#idp66138960), we can create `.pth` files like:

```bash
# ones we create, when `sorted` appear first
_00_editable.pth
_01_second.pth
# ones that are created by setuptools
__editable__.hpi_purarue-0.0.1.pth
__editable__.hpi_purarue_personal-0.0.1.pth
```

and assuming no other build backend creates files that are sorted lexicographically earlier, we can control the order by creating `_00_editble.pth` with contents (like above):

```bash
/home/username/Repos/purarue/HPI
/home/username/Repos/karlicoss/HPI
```

There is a downside, in that if you uninstall one of these packages, the absolute path will still remain in your custom (e.g., `_00_editble.pth` file), so you'd need to manually remove it or follow the workaround described [here](https://github.com/purarue/reorder_editable/issues/2#issuecomment-1868123552).

## Installation

Requires `python3.10+`

To install with pip, run:

    python3 -m pip install reorder_editable

Can always be accessed like `python3 -m reorder_editable`, if your python local bin directory isn't on your `$PATH`

## Usage

```
Usage: reorder_editable [OPTIONS] COMMAND [ARGS]...

  Manage your editable packages - your easy-install.pth file

Options:
  --help  Show this message and exit.

Commands:
  cat      print easy-install.pth contents
  check    check easy-install.pth
  locate   print easy-install.pth file location
  reorder  reorder easy-install.pth
```

To reorder:

```
Usage: reorder_editable reorder [OPTIONS] DIRECTORY...

  If the order specified in your easy-install.pth doesn't match the order of
  the directories specified as positional arguments, reorder them so that it
  does. This always places items you're reordering at the end of your easy-
  install.pth so make sure to include all items you care about the order of

  Also fails if one of the paths you provide doesn't exist, or it isn't
  already in you easy-install.pth

  e.g.
  reorder_editable reorder ./path/to/repo /another/path/to/repo

  If ./path/to/repo was below /another/path/to/repo, this would reorder
  items in your config file to fix it so that ./path/to/repo is above
  /another/path/to/repo

Options:
  -e, --easy-install-location TEXT
                                  Manually provide path to easy-install.pth
  --help                          Show this message and exit.
```

As an example using the descriptions above, If I wanted to make sure `my_HPI` was above `upstream_HPI`, I'd run:

```bash
$ python3 -m reorder_editable reorder ./my_HPI ./upstream_HPI
```

### Tests

```bash
git clone 'https://github.com/purarue/reorder_editable'
cd ./reorder_editable
pip install '.[testing]'
mypy ./reorder_editable
pytest
```
