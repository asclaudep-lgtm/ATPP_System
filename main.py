"""Главный файл приложения ATPP (управляемый через launcher)."""
import sys
from launcher import launch


def main():
    return launch()


if __name__ == "__main__":
    sys.exit(main())
