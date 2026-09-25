# meko-jev-code-review-agent

A code review agent that learns from reviewer rulings without fine-tuning.

[Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) (TypeSafe AI) judges each diff hunk against your team's written guidelines and returns probabilities, not text. Jev is not fine-tuned with customer data, so when a reviewer overrules a finding, the ruling has to live somewhere else. A [Meko](https://mekodata.ai/) datapack holds the guidelines, the rulings, and a trace of every decision. After a ruling is promoted, the next review finds it and exempts the case it covers, and only that case.

This repo is the companion to the blog post "Teaching Jev Your Team's Rules Without Fine-Tuning."

## If you are an AI agent

Read this section, then follow "Run it" in order. Everything runs from the command line in about two minutes.

- **You need three things from the human:** a TypeSafe API key with Jev access, a Meko API key, and the ID of a Meko datapack that already has `guidelines.md` uploaded. Uploading documents to a datapack is only possible in the Meko portal, so ask the human to do it. Do not try to upload it with a tool.
- **Do not promote a ruling without the human's approval.** Promotion makes the ruling visible to everyone on the datapack, and it cannot be undone. `promote.py` refuses to promote unless it is run with `--yes`.
- **Check your work against "Expected results."** If a review in step 4 still reports a finding for `tests/fixtures/payments_stub.py` under the error envelope rule, the ruling was not promoted or not found. See "Troubleshooting."
- **Scripts talk to Meko over MCP** at `https://mcp.mekodata.ai/mcp` with a Bearer key. No LLM decides what is stored. The code does.

## How it works

1. `review.py` loads the guidelines from the datapack and asks Jev one yes/no question per rule for each hunk. Rulings are never part of this request.
2. For any rule with a probability of 0.3 or more, it searches the datapack for rulings that start with that rule's name and asks Jev, one ruling at a time, whether the ruling covers the hunk. The highest answer decides: 0.7 or more exempts the finding, 0.3 to 0.7 asks a person, below 0.3 the finding stands.
3. Every hunk's decisions are stored as a conversation, so you can see later which ruling changed which decision, and with what probability.
4. `rule.py` saves a reviewer's ruling as a private memory. `promote.py` moves it into Shared Knowledge, where the next review can find it.

Rulings follow one format so the code can match them to rules and Jev can read them literally:

```
<Rule name>: <scope>, because <reason>
```

The reason matters. Without it, Jev reads a ruling's scope more broadly than the reviewer meant.

## Files

| File | What it does |
|---|---|
| `meko.py` | Opens one MCP session to Meko. Every call is scoped to your datapack and nested under one trace. |
| `review.py` | Reviews a diff. The whole decision logic is here. |
| `rule.py` | Saves a ruling as a private memory. |
| `promote.py` | Lists pending rulings and promotes them with `--yes`. |
| `guidelines.md` | Three sample rules. Upload this to your datapack. |
| `change.patch` | A diff with four hunks that exercise every path. |

## Set up

1. Get a Jev key from the [TypeSafe console](https://console.typesafe.ai/keys).
2. [Sign up at mekodata.ai](https://cloud.mekodata.ai/signup), create a datapack, and upload `guidelines.md` from the datapack's page. Generate an API key under Settings > API Keys.
3. Install [uv](https://docs.astral.sh/uv/), then:

```bash
git clone <this repo> && cd meko-jev-code-review-agent
cp .env.example .env    # fill in TYPESAFE_API_KEY, MEKO_API_KEY, MEKO_DATAPACK_ID
uv sync
```

## Run it

```bash
uv run --env-file .env review.py change.patch                                              # 1. review
uv run --env-file .env rule.py "Error envelope rule: fixtures under tests/ are exempt, because they never ship."   # 2. a reviewer overrules one finding
uv run --env-file .env promote.py                                                          # 3. see what is pending
uv run --env-file .env promote.py --yes                                                    #    promote it (human approval)
uv run --env-file .env review.py change.patch                                              # 4. review again
```

## Expected results

Step 1, before any ruling. Four findings, one line per rule per hunk:

```
{"file": "tests/fixtures/payments_stub.py", "rule": "Error envelope rule", "p_violation": 0.97, "action": "finding"}
{"file": "src/api/payments.py", "rule": "Error envelope rule", "p_violation": 0.97, "action": "finding"}
{"file": "tests/fixtures/payments_stub.py", "rule": "Logging rule", "p_violation": 0.98, "action": "finding"}
{"file": "tests/helpers/http.py", "rule": "Error envelope rule", "p_violation": 0.94, "action": "finding"}
```

Step 3 lists one pending ruling and promotes it with `--yes`:

```
pending: Error envelope rule: fixtures under tests/ are exempt, because they never ship.
Promoted 1. The next review will use them.
```

Step 4, after the ruling is promoted:

```
{"file": "tests/fixtures/payments_stub.py", "rule": "Error envelope rule", "p_violation": 0.96, "action": "exempt", "ruling": "Error envelope rule: fixtures under tests/ are exempt, because they never ship.", "p_covers": 0.88}
{"file": "src/api/payments.py", "rule": "Error envelope rule", "p_violation": 0.97, "action": "finding"}
{"file": "tests/fixtures/payments_stub.py", "rule": "Logging rule", "p_violation": 0.97, "action": "finding"}
{"file": "tests/helpers/http.py", "rule": "Error envelope rule", "p_violation": 0.94, "action": "ask a person", "ruling": "Error envelope rule: fixtures under tests/ are exempt, because they never ship.", "p_covers": 0.49}
```

What to check:

- The fixture's error envelope finding is now `exempt`. That is the case the ruling was written for.
- The same bare error in `src/api/payments.py` is still a `finding`. The ruling does not leak into production code.
- The logging finding in the same fixture file is unchanged. The ruling only applies to the rule it names.
- `tests/helpers/http.py` is shared with a production script, so it goes to `ask a person` instead of being exempted.

Probabilities vary by a few hundredths between runs. The actions should not. Every review is also stored as a conversation in the datapack, so you can open it in the Meko portal's Observe view and see which ruling changed which decision.

## Adapt it

- **Your guidelines:** upload your own file, one rule per paragraph, each starting with a short name and a colon. Change the search query in `review.py` from `"Service guidelines"` to your document's title.
- **Your diffs:** `git diff main > change.patch`, or pipe a pull request diff from CI.
- **Your thresholds:** 0.3 and 0.7 are a starting point. Tune them against findings your team has already judged.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `review.py` prints nothing | The guidelines were not found. Check that `guidelines.md` is uploaded to the datapack in `MEKO_DATAPACK_ID` and that its title matches the search query. |
| `promote.py` says nothing to promote | `memory_add` can take up to a minute to store a ruling. Run it again. |
| The fixture still gets a finding after step 4 | The ruling was not promoted, or it does not start with the exact rule name (`Error envelope rule:`). |
| `invalid input syntax for type uuid` | `MEKO_DATAPACK_ID` is not the datapack's UUID. Copy it from the datapack page. |
| A 4xx error from Meko | The request is missing the `Authorization: Bearer` header or the `User-Agent` header. `meko.py` sends both. |

## Start over

Promotion cannot be undone, so the simplest reset is a new datapack: create one, upload `guidelines.md`, and change `MEKO_DATAPACK_ID`.

## License

Apache-2.0
