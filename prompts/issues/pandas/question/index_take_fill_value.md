# Question: What should `Index.take` do when `fill_value` is passed for integer indexes?

You are triaging an open pandas API design question.

Issue summary:
- The reporter wants `Index.take(..., allow_fill=True, fill_value=...)` to respect the provided fill value for integer indexes.
- The current behavior feels inconsistent because it can ignore the explicit fill value or raise on indexes that cannot hold `NA`.
- The question is whether pandas should keep the current behavior, change the semantics, or deprecate the old contract first.

Task:
- classify the issue
- summarize the API design tension
- note whether this looks like a bug fix or a deprecation discussion
- write a short maintainer reply

Return:
- label
- rationale
- next step
- maintainer reply

