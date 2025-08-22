===============================================================
MASTER BLUEPRINT: R → Python (pandas) Conversion – One-Snippet Guide
===============================================================

Goal
----
A single, comprehensive reference to (a) map R syntax to Python/pandas,
(b) outline robust converter architecture (incl. indentation handling),
(c) cover complex dataframe idioms, and (d) provide tests & pitfalls.

Use this as the spec to build (or improve) an R→Python converter.


SECTION A — R → Python Syntax Reference (with examples)
-------------------------------------------------------

1) Assignment
   R:  x <- 10                 →  Py: x = 10
       y = 20                  →      y = 20   (unchanged)
       x -> z                  →      z = x    (reverse assign)

2) Function Definitions & Calls
   R:  my.func <- function(a=1, b="x") { return(a + 1) }
       g.date8(x)              (dots in names)
   Py: def my_func(a=1, b="x"):
           return a + 1
       g_date8(x)              (convert dots & camelCase → snake_case)

3) Control Flow
   If/Elif/Else:
   R:  if (x > 5) { ... } else if (x > 2) { ... } else { ... }
   Py: if x > 5:
           ...
       elif x > 2:
           ...
       else:
           ...

   Loops:
   R:  for (i in 1:5) { print(i) }
       while (x < 5) { x <- x + 1 }
   Py: for i in range(1, 6): print(i)
       while x < 5: x = x + 1

4) Vectors, Sequences
   R:  c("a","b","c")          →  Py: ["a","b","c"]
       c(1,2,3)                →      [1,2,3]
       1:5                     →      range(1, 6)
       seq(1, 10, 2)           →      range(1, 11, 2)   (# stop+1)

5) Data Frame Creation
   R:  df <- data.frame(id=c(1,2), name=c("a","b"))
   Py: df = pd.DataFrame({"id":[1,2], "name":["a","b"]})

6) Column Access & Name Normalization
   R:  df$id                   →  Py: df["id"]
       df[, "name"]            →      df["name"]
       df[, c("id","name")]    →      df[["id","name"]]
       df$col.1                →      df["col_1"]       (# dot→underscore)
       a$cip.pvt.rt            →      a["cip_pvt_rt"]

7) Column Removal
   R:  df$col1 <- df$col2 <- NULL
   Py: df.drop(columns=["col1","col2"], inplace=True)

8) Subset / Row Filtering
   R:  subset(df, age > 30 & !is.na(name))
   Py: df[(df["age"] > 30) & (df["name"].notna())]

   R:  df[df$age > 30, ]
   Py: df[df["age"] > 30]

9) Negative Indexing on Columns
   R:  df <- df[, -1]                  (# drop first column)
   Py: df = df.drop(df.columns[0], axis=1)

10) Merge / Joins
   R:  merge(x, y, by="id")                            →  Py: pd.merge(x, y, on="id", how="inner")
       merge(x, y, by="id", all.x=TRUE)                →      pd.merge(x, y, on="id", how="left")
       merge(x, y, by="id", all.y=TRUE)                →      pd.merge(x, y, on="id", how="right")
       merge(x, y, by="id", all=TRUE)                  →      pd.merge(x, y, on="id", how="outer")
       merge(abc, xyz[!is.na(rtr$isin),], by.x="ISIN", by.y="isin")
            → pd.merge(abc, xyz[rtr["isin"].notna()], left_on="ISIN", right_on="isin", how="inner")

11) rbind / cbind
   R:  rbind(df1, df2)   →  Py: pd.concat([df1, df2], axis=0)
       cbind(df1, df2)   →      pd.concat([df1, df2], axis=1)

12) names() / columns
   R:  names(df)                          →  Py: df.columns.tolist()
       names(df) <- c("id","name")        →      df.columns = ["id","name"]

   Mixed selection with names():
   R:  abc_f <- abc_f[, c("rtr","gfr", names(df2), "safsd.rr")]
   Py: abc_f = abc_f[["rtr", "gfr", *df2.columns.tolist(), "safsd_rr"]]

13) Membership: %in% / %ni%
   Scalar context:
   R:  x %in% c(1,2,3)     →  Py: x in [1,2,3]
       x %ni% c(1,2,3)     →      x not in [1,2,3]

   Vectorized (pandas Series):
   R:  df$age %in% c(20,30) → Py: df["age"].isin([20,30])
       df$age %ni% c(20,30) →     ~df["age"].isin([20,30])

14) Missingness
   R:  is.na(df$col1)       →  Py: df["col1"].isna()
       !is.na(df$col1)      →      df["col1"].notna()

15) Pattern / Files
   R:  list.files(pattern="*.csv")        →  Py: glob.glob("*.csv")
       grep("abc", names(df))             →     df.filter(like="abc").columns.tolist()

16) Dates & Times
   R:  Sys.Date()                         →  Py: datetime.date.today()
       Sys.time()                         →      datetime.datetime.now()
       Sys.Date() - 1                     →      datetime.date.today() - datetime.timedelta(days=1)

17) Error
   R:  stop("Error occurred!")            →  Py: raise Exception("Error occurred!")


SECTION B — Converter Architecture (Robust & Maintainable)
----------------------------------------------------------

1) Pass Pipeline (multi-pass transforms):
   - Preprocess:
     * Normalize whitespace; preserve comments & blank lines.
     * Replace `<-` and `->` with `=` (with spacing).
     * Normalize identifiers to snake_case (function & column names; dots→underscores).
   - Token/AST-ish Pass (regex-guided):
     * Column access `df$col` → `df["col"]` (normalize `col`).
     * Vectors: `c(...)` → `[...]`; `1:5` → `range(1,6)`; `seq(...)` → `range(...)`.
     * Membership: `%in%`/`%ni%`:
         - If LHS is Series-like → `.isin([...])` / `~.isin([...])`
         - Else scalar context → `in` / `not in`.
     * Missingness: `is.na(x)`/`!is.na(x)` → `.isna()` / `.notna()`.
     * DF ops: `rbind`, `cbind`, `unique`, `names`, `subset`, chained `<- NULL` drops.
     * Merge: parse args (`by`, `by.x`, `by.y`, `all.x`, `all.y`, `all`).
     * Column subsets: `df[, c("a", names(df2), "b")]` with `*df2.columns.tolist()`.
   - Control Flow & Functions:
     * `function(...) {` → `def ...(...):`
     * `if (..){`, `else if(..){`, `else{`, `for(.. in ..){`, `while(..){` → Python forms + `:`
     * `stop("...")` → `raise Exception("...")`
   - Indentation Manager (brace-driven):
     * BEFORE emitting a line: dedent by count of `}` on that line.
     * Remove `{`/`}`.
     * Emit with current indent.
     * AFTER emitting: if line endswith `:`, then indent++.
     * Handle `} else {` / `} else if (...) {` using a two-step: dedent for `}`, rewrite to `else:`/`elif ...:`, then (since it ends with `:`) re-indent for block.

2) Name Normalization:
   - `to_snake_case`: replace `.`/`-` → `_`, split camelCase `aB` → `a_b`, lower().
   - Apply to function names, and to column names inside `df$...`, `c("...")`, `names<-`.
   - DO NOT alter literal strings except when they are clearly column literals in selection contexts; when in doubt, prefer leaving string literals unchanged (or make this configurable).

3) Expression Handling Inside `c(...)`:
   - Support mixing: literals, identifiers, `names(df)`, nested `c(...)`.
   - Expand `names(df)` → `*df.columns.tolist()` to allow list unpacking in Python.

4) Merge Parsing:
   - Extract left & right expressions (not just names): e.g., `xyz[!is.na(...),]`.
   - Recognize `by`, `by.x`, `by.y`, `all.x`, `all.y`, `all` to build `pd.merge(..., how=...)`.
   - Default how=`"inner"`.

5) Subset:
   - `subset(df, CONDITION)` → `df[(CONDITION)]`
   - Inside CONDITION:
     * Map `df$col` → `df["col"]`
     * Map `&` / `|` / `!` appropriately (respect pandas operator precedence).
     * Map `%in%`/`%ni%`, `is.na`/`!is.na`.

6) Chained NULL Drops:
   - Pattern: `df$col1 <- df$col2 <- ... <- NULL`
   - Convert to single: `df.drop(columns=[...], inplace=True)` (columns normalized).

7) Comments & Blank Lines:
   - Preserve as-is for readability and debugging.

8) Safety:
   - Avoid transforming string literals except evident column-name contexts.
   - Keep a config flag for aggressive name normalization vs. preserve-original.

9) Output:
   - Always header-imports: `import pandas as pd`, `import numpy as np`, `import glob`, `import datetime as datetime` (or `as dt`), `import re`, `import os`.


SECTION C — Indentation Algorithm (Pseudo-Code)
-----------------------------------------------

function emit(line, indent):
    # 1) compute dedent by number of '}'
    close_count = count('}', line)
    indent = max(indent - close_count, 0)

    # 2) transform control tokens BEFORE removing braces:
    #    "} else if (COND) {" → "elif COND:"
    #    "} else {"          → "else:"
    #    "if (COND) {"       → "if COND:"
    #    similarly for for/while/function

    # 3) strip braces
    line = line.replace('{','').replace('}','').rstrip()

    # 4) write with current indent
    write("    " * indent + line)

    # 5) if line endswith ':' then indent++
    if line.endswith(':'):
        indent += 1

    return indent


SECTION D — Test Matrix (Realistic Cases)
-----------------------------------------

1) Basic:
   - assignments `<-`, `->`, function with defaults, simple if/elif/else.

2) DataFrame Access:
   - `df$foo`, `df$foo.bar`, `df[, "a"]`, `df[, c("a","b")]`, `df[,-1]`.

3) Vector & Conditions:
   - `%in%` / `%ni%` for scalar and vector contexts.
   - `is.na` / `!is.na` inside complex boolean logic: `a & (b | !c)`.

4) Subset Forms:
   - `subset(df, a %in% c(1,2) & !is.na(b))`
   - `df[df$age > 30 & df$city %in% c("NY","SF"), c("id", names(df2), "zip")]`

5) Merge Forms:
   - `merge(x, y, by="id")`
   - `merge(x, y, by.x="a", by.y="b", all=TRUE)`
   - `merge(abc, xyz[! is.na(rtr$isin),], by.x="ISIN", by.y="isin")`

6) Drops:
   - `df$a <- df$b <- df$c <- NULL`

7) rbind/cbind/unique/names:
   - `rbind(df1, df2)`, `cbind(df1, df2)`, `unique(df$id)`, `names(df) <- c(...)`.

8) Edge Cases:
   - `} else if (...) {` on the same line.
   - Multiple `}}` closing nested blocks.
   - Strings containing `in`, `%in%`, `is.na` (ensure we don't rewrite inside quotes).


SECTION E — Known Pitfalls & Guidance
-------------------------------------

1) Vectorized vs Scalar Semantics:
   - In pandas, `in` checks Python collections for membership of a scalar.
   - For Series membership, ALWAYS use `.isin([...])`.
   - Provide heuristics: if LHS matches `df["..."]` or `something[...]`, prefer `.isin`.

2) Operator Precedence in Pandas:
   - Use `&`, `|`, `~` for boolean masks; parentheses are REQUIRED.
   - Do NOT use `and/or/not` with Series.

3) 1-based vs 0-based Indexing:
   - R’s `1:5` includes 5; Python `range(1, 6)`.
   - Negative column indices in R count positions; translate carefully.

4) Factors / Categorical:
   - R factors map to pandas `CategoricalDtype`; you may need explicit handling when modeling levels.

5) Strings vs Column Names:
   - Avoid rewriting inside string literals unless they represent explicit column labels in known contexts (e.g., inside `c("...")` for column selection).
   - Consider a config flag: `normalize_column_strings=True/False`.

6) Data Types:
   - R `NA` vs NumPy/Pandas `NaN`/`NaT`; behavior differs in some ops.

7) Piping & Tidyverse:
   - If `%>%` / `dplyr` is present, you’ll need a separate pass (or `siuba/polars`) to translate verbs (`select`, `mutate`, `filter`, `left_join`, etc.).

8) I/O Semantics:
   - `read.csv(...)` vs `pd.read_csv(...)` parameters differ (sep, header, stringsAsFactors).


SECTION F — Example Gold Tests (should pass)
--------------------------------------------

# 1) Merge with filter on right & by.x/by.y
R:
abc <- merge(abc, xyz[! is.na(rtr$isin),], by.x="ISIN", by.y="isin")
Py:
abc = pd.merge(abc, xyz[rtr["isin"].notna()], left_on="ISIN", right_on="isin", how="inner")

# 2) Mixed column subset using names()
R:
abc_f <- abc_f[, c("rtr","gfr",names(df2),"safsd.rr")]
Py:
abc_f = abc_f[["rtr","gfr", *df2.columns.tolist(), "safsd_rr"]]

# 3) Chained column drops
R:
a$curt.prt <- a$curt.rt.x <- NULL
Py:
a.drop(columns=["curt_prt","curt_rt_x"], inplace=True)

# 4) Complex subset
R:
subset(df, (age >= 21 & !is.na(city)) | (score %in% c(90, 95)))
Py:
df[((df["age"] >= 21) & (df["city"].notna())) | (df["score"].isin([90, 95]))]


SECTION G — Minimal Converter Skeleton (Pseudo-Implementation)
--------------------------------------------------------------

# Imports to add at top of generated Python:
# import pandas as pd
# import numpy as np
# import glob
# import datetime as datetime
# import re, os

def to_snake_case(name):
    name = re.sub(r"[.-]", "_", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()

def normalize_col_in_brackets(s):
    # apply to strings that are column literals in c("...") lists
    return s.replace(".", "_")

def transform_line(line, indent):
    # 1) Dedent by count of '}' BEFORE emitting
    indent = max(indent - line.count("}"), 0)

    # 2) Assignments
    line = re.sub(r"\s*<-\s*", " = ", line)
    line = re.sub(r"\s*->\s*", " = ", line)

    # 3) Column access: df$col.with.dots → df["col_with_dots"]
    line = re.sub(r"(\w+)\$(\w+(?:\.\w+)*)",
                  lambda m: f'{m.group(1)}["{to_snake_case(m.group(2))}"]', line)

    # 4) Vectors & sequences
    line = re.sub(r"c\((.*?)\)", r"[\1]", line)
    line = re.sub(r"(\d+):(\d+)", lambda m: f'range({m.group(1)}, {int(m.group(2))+1})', line)
    line = re.sub(r"seq\((\d+),\s*(\d+)(?:,\s*(\d+))?\)",
                  lambda m: f'range({m.group(1)}, {int(m.group(2))+1}' + (f', {m.group(3)})' if m.group(3) else ')'),
                  line)

    # 5) Missingness / membership (vectorized by default)
    line = re.sub(r"!\s*is\.na\((.*?)\)", r"\1.notna()", line)
    line = re.sub(r"is\.na\((.*?)\)",   r"\1.isna()",   line)
    line = re.sub(r"%in%",  ".isin", line)
    line = re.sub(r"%ni%",  ".__NOT_IN__", line)  # temp token; replace after parentheses pass

    # 6) rbind/cbind/unique/names
    line = re.sub(r"rbind\((.*?)\)", r"pd.concat([\1], axis=0)", line)
    line = re.sub(r"cbind\((.*?)\)", r"pd.concat([\1], axis=1)", line)
    line = re.sub(r"unique\((.*?)\)", r"\1.unique()", line)
    # names(df) retrieval vs assignment: handle assignment separately if needed
    line = re.sub(r"names\((.*?)\)", r"\1.columns.tolist()", line)

    # 7) subset(df, cond) → df[(cond)]
    line = re.sub(r"subset\(\s*([^,]+)\s*,\s*(.+)\)", r"\1[\2]", line)

    # 8) Merge parsing (simplified; production should parse args robustly)
    #    Support by, by.x/by.y, and all/all.x/all.y → how
    #    Convert xyz[! is.na(rtr$isin),] remains as-is after earlier passes
    # (omitted here for brevity; see Section A examples for target strings)

    # 9) Chained NULL drops: df$col1 = df$col2 = NULL
    if re.search(r"=\s*NULL", line):
        cols = re.findall(r'(\w+)\["([^"]+)"\]', line)  # from earlier df$col→df["col"]
        if cols:
            df = cols[0][0]
            unique_cols = sorted(set(c for (_, c) in cols))
            return "    " * indent + f'{df}.drop(columns={[c for c in unique_cols]}, inplace=True)'

    # 10) Controls & functions
    line = re.sub(r"else if\s*\((.*?)\)", r"elif \1:", line)
    line = re.sub(r"if\s*\((.*?)\)",      r"if \1:",   line)
    line = re.sub(r"else\s*:?$",          r"else:",    line)
    line = re.sub(r"for\s*\((\w+)\s+in\s+(.*?)\)", r"for \1 in \2:", line)
    line = re.sub(r"while\s*\((.*?)\)",   r"while \1:", line)
    line = re.sub(r"(\w+(?:\.\w+)*)\s*=\s*function\s*\((.*?)\)",
                  lambda m: f'def {to_snake_case(m.group(1))}({m.group(2)}):', line)
    line = re.sub(r"stop\((.*?)\)", r"raise Exception(\1)", line)

    # 11) Handle %ni% temp token to a NOT IN for Series: ~(Series.isin([...]))
    #     Heuristic: if left side looks like a Series (contains [") or $ transformed), use ~.isin
    line = re.sub(r'(\w+\[.*?\])\s*\.__NOT_IN__\s*(\[[^\]]*\])', r'~\1.isin(\2)', line)
    line = re.sub(r'(\w+)\s*\.__NOT_IN__\s*(\[[^\]]*\])',        r'\1 not in \2', line)

    # 12) Remove braces then emit
    line = line.replace("{", "").replace("}", "").strip()
    out  = "    " * indent + line

    # 13) Indent after block openers
    if out.endswith(":"):
        indent += 1

    return out, indent


SECTION H — How to Analyze a Real R Codebase
--------------------------------------------

1) Inventory:
   - Count frequency of: `merge`, `subset`, `$`, `[ , ]`, `rbind`, `cbind`, `%in%`, `is.na`, `function`, braces.
   - Detect tidyverse/data.table usage (`%>%`, `dplyr::`, `data.table` syntaxes).

2) Patterns to Extract:
   - Column naming conventions (dots, spaces, camelCase).
   - Common join keys and join types.
   - Typical filters (missingness patterns, `%in%` lists).
   - I/O (read.csv, fwrite, etc.) and date/time utilities.

3) Risks:
   - Factor handling, releveling, ordered factors.
   - 1-based indexing assumptions.
   - Non-standard evaluation (NSE) in tidyverse.

4) Plan:
   - Start with base-R data.frame rules (this blueprint).
   - Add modules for tidyverse (`select`, `mutate`, `filter`, `left_join`) as a later pass.
   - Add a verification step: run translated code against sample data; compare shapes, null counts, key uniqueness, and basic aggregates to catch semantic drift.


END
---
This single snippet can serve as your spec + checklist + pseudo-implementation
to build a robust, bug-resistant R→Python converter for complex dataframe code.
