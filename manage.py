#!/usr/bin/env python3
"""Django administrative utility."""

import os
import sys


def main() -> None:
    default_settings = (
        "config.test_settings" if sys.argv[1:2] == ["test"] else "config.settings"
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
