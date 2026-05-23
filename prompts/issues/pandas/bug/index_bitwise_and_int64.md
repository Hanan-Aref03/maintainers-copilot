# BUG: `Index & Index` returns bitwise AND instead of set intersection for integer indexes

You are triaging a pandas correctness bug report.

Issue summary:
- Two integer `Index` objects combined with the `&` operator produce a NumPy-style bitwise AND result.
- The reporter says `.intersection()` already gives the expected set intersection.
- The bug affects users who expect `&` to behave like an index intersection operator.

Task:
- classify the issue
- summarize the user-visible breakage
- identify the likely compatibility risk if behavior changes
- write a short maintainer reply

Return:
- label
- rationale
- next step
- maintainer reply

