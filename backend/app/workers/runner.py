"""Worker entrypoint — invoked by the `worker` service in
docker-compose.yml as `python -m app.workers.runner`."""

from __future__ import annotations

import asyncio

from app.workers.scheduler import runner


def main() -> None:
    asyncio.run(runner())


if __name__ == "__main__":
    main()
