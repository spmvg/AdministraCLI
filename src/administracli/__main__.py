"""
CLI entry point: python -m administracli
"""

import argparse
import sys


DEFAULT_FILE = "administracli.xlsx"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="administracli",
        description="Command line tool for small business administration with local data in an Excel sheet.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # init
    init_parser = subparsers.add_parser("init", help="Create a new Excel sheet with the proper format.")
    init_parser.add_argument("file", nargs="?", default=DEFAULT_FILE, help="Path to the Excel file.")

    # run
    run_parser = subparsers.add_parser("run", help="Interactively close the books, then show financial reports.")
    run_parser.add_argument("file", nargs="?", default=DEFAULT_FILE, help="Path to the Excel file.")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "init":
        from administracli.excel_io import init_workbook

        init_workbook(args.file)
        print(f"Created {args.file}")

    elif args.command == "run":
        from administracli.app import AdministracliApp

        app = AdministracliApp(file_path=args.file)
        app.run()


if __name__ == "__main__":
    main()
