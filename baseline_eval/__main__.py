"""CLI entry point for baseline_eval."""

import asyncio
from .runner import main

if __name__ == "__main__":
    asyncio.run(main())
