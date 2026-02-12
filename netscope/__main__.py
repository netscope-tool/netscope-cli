"""
Entry point for the NetScope CLI application.
"""

import sys
from netscope.cli.main import app


def main():
    """Main entry point."""
    try:
        app()
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()