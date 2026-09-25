"""Promote this agent's rulings into Shared Knowledge. One-way: a person should approve each one."""
import asyncio, sys
from meko import meko


async def main(approved: bool) -> None:
    async with meko("promote rulings") as call:
        pending = (await call("memory_get_all"))["memories"]
        for m in pending:
            print("pending:", m["data"])
        if not pending:
            print("Nothing to promote. memory_add can take up to a minute to store a ruling.")
        elif approved:
            await call("memory_promote", memory_ids=[m["id"] for m in pending])
            print(f"Promoted {len(pending)}. The next review will use them.")
        else:
            print("Re-run with --yes to promote these. Promotion cannot be undone.")


if __name__ == "__main__":
    asyncio.run(main("--yes" in sys.argv))
