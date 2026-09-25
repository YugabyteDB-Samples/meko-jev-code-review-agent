"""Review a diff: Jev judges each hunk against the guidelines, then checks promoted rulings."""
import asyncio, json, sys
from typesafe_sdk import AsyncTypeSafeClient, Noul, NoulCriteria
from meko import meko

VIOLATES = NoulCriteria(true="The hunk breaks this specific rule.",
                        false="The rule is followed, or it does not apply to this code.")
COVERS = Noul(
    instructions="Does the ruling in `ruling` cover `hunk` exactly as the ruling states its scope?",
    criteria=NoulCriteria(true="The hunk is squarely inside the scope the ruling names.",
                          false="The hunk is outside that scope, only resembles it, or goes further than the ruling allows."))


def hunks(diff: str) -> list[str]:
    """One string per @@ hunk, each keeping its file's --- / +++ lines so Jev sees the path."""
    out, header = [], []
    for line in diff.splitlines():
        if line.startswith("--- "): header = [line]
        elif line.startswith("+++ "): header.append(line)
        elif line.startswith("@@"): out.append("\n".join(header + [line]))
        elif out and not line.startswith(("diff --git", "index ", "new file", "deleted file")): out[-1] += "\n" + line
    return out


async def main(patch: str) -> str | None:
    jev = AsyncTypeSafeClient()  # reads TYPESAFE_API_KEY
    async with meko(f"review {patch}") as call:
        # Load the uploaded guidelines once. Promoted rulings live in the same store, so skip them here.
        hits = (await call("knowledgebase_search", query="Service guidelines", limit=8))["results"]
        rules = [p.strip() for h in hits if h["metadata_filters"].get("source") != "memory"
                 for p in h["chunk_text"].split("\n\n") if p.strip() and not p.startswith(("Section:", "#"))]
        if not rules:
            return "No guidelines found. Upload guidelines.md to this datapack in the Meko portal, then run again."

        for hunk in hunks(open(patch).read()):
            # 1. Judge the hunk against the guidelines. No rulings in this request.
            qs = {f"r{i}": Noul(instructions=f"Does the code in `hunk` violate the rule in `rules[{i}]`?", criteria=VIOLATES)
                  for i in range(len(rules))}
            answers = (await jev.system_one({"hunk": hunk, "rules": rules}, qs)).answers

            decisions = []
            for i, rule in enumerate(rules):
                p = answers[f"r{i}"].noul
                if p < 0.3:
                    continue  # no finding
                decision = {"file": hunk.splitlines()[1][6:], "rule": rule.split(":")[0], "p_violation": round(p, 2),
                            "action": "finding" if p >= 0.7 else "escalate"}

                # 2. A contested finding looks up rulings recorded for this rule, one Jev question per ruling.
                hits = (await call("knowledgebase_search", query=f"{decision['rule']}: {hunk}", limit=8))["results"]
                rulings = [h["chunk_text"] for h in hits if h["metadata_filters"].get("source") == "memory"
                           and h["chunk_text"].startswith(decision["rule"] + ":")]
                if rulings:
                    covers = await asyncio.gather(*[jev.system_one({"hunk": hunk, "ruling": r}, {"covers": COVERS})
                                                    for r in rulings])
                    p_cov, ruling = max((c.answers["covers"].noul, r) for c, r in zip(covers, rulings))
                    if p_cov >= 0.3:
                        decision.update(action="exempt" if p_cov >= 0.7 else "ask a person",
                                        ruling=ruling, p_covers=round(p_cov, 2))
                decisions.append(decision)
                print(json.dumps(decision))

            # 3. Record the decisions as a trace. The hunk goes in the output: Meko extracts memories from the input.
            await call("conversation_add_message", input="Review of one diff hunk",
                       output=json.dumps({"hunk": hunk, "decisions": decisions}))


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "change.patch")))
