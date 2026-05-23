# PERF: DataFrame row-wise `.loc` assignment is slow with `string_storage="pyarrow"`

You are triaging a pandas performance bug report.

Issue summary:
- A benchmark shows that repeatedly growing a string-typed DataFrame with row-wise `.loc` assignment is much slower when `pd.options.mode.string_storage` is set to `"pyarrow"` than when it is set to `"python"`.
- The slowdown grows quickly as the DataFrame gets larger.
- The reporter includes a reproducible benchmark and asks for the cause of the regression.

Task:
- classify the issue
- summarize the likely performance risk
- say whether a regression benchmark or microbenchmark should be added
- write a short maintainer reply

Return:
- label
- rationale
- next step
- maintainer reply

