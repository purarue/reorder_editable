"""
Core functionality, reads/writes to the editable and checks if order matches what the user specifies
"""

import os
import site


class ReorderEditableError(FileNotFoundError):
    """ReorderEditable related errors"""

    pass


class Editable:
    """
    Encapsulates all possible interaction with the easy-install.pth file
    """

    def __init__(
        self,
        *,
        location: str | None = None,
        use_user_site: bool = True,
        allow_missing: bool = False,
    ) -> None:
        """
        can optionally pass a location, to prevent the locate_editable editable call
        """
        if location is None:
            found_editable = self.__class__.locate_editable(use_user_site=use_user_site)
            if found_editable is not None:
                self.location = found_editable
            else:
                raise ReorderEditableError("Could not locate easy-install.pth")
        else:
            self.location = location

        self.lines: list[str] = []
        if allow_missing is False:
            assert os.path.exists(
                self.location
            ), f"The easy-install.pth file at '{self.location}' doesn't exist"
        else:
            # if allow_missing=True, and the file doesn't exist, then
            # skip read_lines, we will manually populate them below in
            # _create_custom_editable
            if not os.path.exists(self.location):
                return
        self.lines = self.read_lines()

    def read_lines(self) -> list[str]:
        """
        Read lines from the editable path file

        splitlines removes newlines from the end of each line
        """
        with open(self.location, "r") as src:
            self.lines = src.read().splitlines()
        return self.lines

    def write_lines(self, new_lines: list[str]) -> None:
        """
        Write lines back to the editable path file

        new_lines is a list of absolute paths, so for the format of
        the file to be the same, add newlines on each write
        """
        with open(self.location, "w") as target:
            for line in new_lines:
                target.write(f"{line}\n")

    def _create_custom_editable(self, lines: list[str]) -> bool:
        """
        This creates a custom easy-install.pth file at self.location

        If it doesn't exist, creates it with the lines
        If it does exist, it ensures the order is correct

        This can be used to hack the import order without messing
        with an easy-install.pth, since using that has/will become less
        common with the deprecation of setuptools' editable installs

        see:
        https://github.com/purarue/reorder_editable/issues/2#issuecomment-1868123552
        """
        if os.path.exists(self.location):
            self.lines = self.read_lines()
            # this can throw a ReorderEditableError if it reorders
            return self.reorder(lines)
        else:
            self.lines = lines
            self.write_lines(lines)
            return True  # I guess? this will only happen once, so it is always "edited"

    def assert_ordered(self, expected: list[str]) -> None:
        """
        returns None on success, an Error if the file is not ordered correctly given 'expected'

        expected should be a list of absolute paths, in the order you expect to see
        them in the easy-install.pth
        """
        # iterated through all the items in the easy-install.pth file
        # but 'i' didn't reach the end of the list of expected items
        left = self.find_unordered(expected)
        if len(left) > 0:
            raise ReorderEditableError(
                f"Reached the end of the easy-install.pth, but did not encounter '{left}' in the correct order"
            )

    def find_unordered(self, expected: list[str]) -> list[str]:
        """
        Given a list of absolute paths in an expected order, compares that against
        the read order from the easy-install.pth file

        Returns any items not found in the correct order by the
        time it reaches the end of the easy-install.pth
        """
        return self.__class__.find_unordered_pure(self.lines, expected)

    @staticmethod
    def find_unordered_pure(lines: list[str], expected: list[str]) -> list[str]:
        """
        Pure function encapsulating all the logic for find_unordered
        """

        if len(expected) == 0:
            return expected
        i = 0  # current index of the expected items
        for path in lines:
            # use os.stat instead?
            if path == expected[i]:
                i += 1
                if len(expected) == i:
                    break

        return expected[i:]

    def reorder(self, expected: list[str]) -> bool:
        """
        If needed, reorder the easy-install.pth

        If the user specifies an item which doesn't exist in the
        easy-install.pth, this throws an error, since it has
        no way to determine where that value should go

        Return value is True if the file was edited, False
        if it didn't need to be edited.
        """
        do_reorder, new_lines = self.__class__.reorder_pure(self.lines, expected)
        if do_reorder is False:
            return False
        # write new_lines to file
        self.write_lines(new_lines)
        return True

    @classmethod
    def reorder_pure(
        cls, lines: list[str], expected: list[str]
    ) -> tuple[bool, list[str]]:
        """
        Pure function encapsulating all the logic for reordering
        Returns (whether or not to edit the file, resulting changes)
        """
        unordered: list[str] = cls.find_unordered_pure(lines, expected)
        # everything is ordered right, dont need to reorder anything!
        if len(unordered) == 0:
            return False, lines

        # check that expected is a subset of lines
        expected_set = set(expected)
        lines_set = set(lines)
        if not expected_set.issubset(lines_set):
            raise ReorderEditableError(
                f"Provided one or more value(s) which don't appear in the easy-install.pth: {expected_set - lines_set}"
            )

        result: list[str] = []

        # if an item isn't mentioned in expected, leave it in the same
        # order -- extract all items not mentioned
        for path in lines:
            if path not in expected_set:
                result.append(path)

        # add anything in expected, in the order the user specified
        for path in expected:
            assert path in lines_set
            result.append(path)

        # sanity check
        assert len(result) == len(lines)

        return True, result

    @staticmethod
    def locate_editable(*, use_user_site: bool) -> str | None:
        """
        try to find an editable install path in the user site-packages
        """
        if use_user_site:
            site_packages_dir = site.getusersitepackages()
        else:
            system_site_packages_dirs = site.getsitepackages()
            if len(system_site_packages_dirs) != 1:
                raise ReorderEditableError(
                    f"Expected exactly one package in system site, got: {system_site_packages_dirs}"
                )
            site_packages_dir = system_site_packages_dirs[0]

        editable_pth = os.path.join(site_packages_dir, "easy-install.pth")
        if not os.path.exists(editable_pth):
            return None
        return editable_pth
