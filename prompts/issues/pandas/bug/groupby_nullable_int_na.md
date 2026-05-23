# BUG: `groupby` cumulative ops lose nullable integer dtype when the key contains `NA`

You are triaging a pandas correctness bug report.

Issue summary:
- `groupby().cumprod()`, `groupby().cummin()`, and `groupby().cummax()` return `Float64` instead of preserving the nullable integer dtype when the grouping key contains `NA`.
- `groupby().cumsum()` does not show the same issue.
- The reporter expects the output dtype to stay aligned with the input nullable integer dtype.

Task:
- classify the issue
- explain the dtype regression in plain language
- state whether a targeted regression test is needed
- write a short maintainer reply

Return:
- label
- rationale
- next step
- maintainer reply

