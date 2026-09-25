"""Record a reviewer's ruling as a private memory. Format: '<Rule name>: <scope>, because <reason>'."""
import asyncio, sys
from meko import meko


async def main(ruling: str) -> None:
    async with meko("record ruling") as call:
        await call("memory_add", text=ruling)
    print("Saved as a private memory. Run promote.py to share it with the next review.")


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:])))
