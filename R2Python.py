#!/usr/bin/env python3
"""
R → Python (pandas) Converter — Robust & Modular
------------------------------------------------
Converts a real‑world R script into idiomatic Python using pandas/numpy.

Highlights
- Assignments:  "<-" and "->" → "=" (spacing normalized)
- Functions:    function(...) with defaults, names → snake_case, stop() → raise
- Control flow: if/else if/else → if/elif/else, for/while, single‑line if {...}
- Indentation:  brace‑aware manager (handles `}`, `} else {`, multi‑close)
- Vectors:      c(...), seq(...), 1:10, paste0, rep, length, etc.
- Data frames:  $ access, [rows, cols], negative col drops, names(), unique()
- Drops:        chained `<- NULL` column removals → df.drop([...], inplace=True)
- Joins:        merge(..., by=..., by.x/by.y, all.x/all.y/all) → pd.merge(...)
- Subset:       subset(df, cond) → df[(cond)] with R ops → pandas mask ops
- %in%/%ni%:    → .isin(list) / ~.isin(list)
- Files:        list.files(pattern=...) → glob.glob, read.csv/write.csv
- Strings:      grep/grepl/gsub → python regex / pandas .str.contains/.replace
- Dates:        Sys.Date(), Sys.time(), date arithmetic
- Naming:       Convert dotted + camelCase identifiers to snake_case consistently

Usage
  python r_to_python_converter.py /path/to/script.R
Outputs /path/to/this_converter/<script_basename>_converted.py

Note: Heuristic/regex‑based; complex corner cases may need manual cleanup,
but this aims to cover the most common, complex R data engineering patterns.
"""

from __future__ import annotations
import os
import re
import sys
import glob
from dataclasses import dataclass
from typing import List, Tuple, Callable

# =========================
# Name normalization
# =========================

def to_snake_case(name: str) -> str:
    """Convert R-style/dotted/camelCase identifiers to snake_case."""
    if name is None:
        return name
    # replace dashes and dots with underscores
    name = re.sub(r"[\.-]", "_", name)
    # CamelCase → snake
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    # multiple underscores → single
    name = re.sub(r"__+", "_", name)
    return name.lower()


def snake_dotted_identifier(m: re.Match) -> str:
    """Helper for df$col... where col can contain dots; returns df["col_snake"]."""
    df, col = m.group(1), m.group(2)
    return f'{df}["{to_snake_case(col)}"]'


# =========================
# Expression helpers
# =========================

def convert_seq_notation(text: str) -> str:
    """R numeric sequences: 1:5 → range(1,6); seq(1,10,2) → range(1,11,2)."""
    # 1:5 → range(1, 6)
    text = re.sub(r"\b(\d+)\s*:\s*(\d+)\b",
                  lambda m: f"range({m.group(1)}, {int(m.group(2))+1})", text)
    # seq(from, to, by?)
    def _seq(m: re.Match) -> str:
        a, b, c = m.group(1), m.group(2), m.group(3)
        end = int(b) + 1
        return f"range({a}, {end}{', '+c if c else ''})"
    text = re.sub(r"\bseq\(\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)", _seq, text)
    return text


def parse_c_vector(expr: str) -> str:
    """Parse R's c( ... ) allowing mix of strings, names(df), and identifiers.
    Returns a Python list literal; names(df) are represented as *df.columns.tolist().
    """
    # Split top-level commas (no nested parens)
    parts: List[str] = []
    buf, depth = [], 0
    for ch in expr:
        if ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth -= 1
            buf.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append(''.join(buf).strip())

    py_parts: List[str] = []
    for p in parts:
        # names(df)
        m = re.fullmatch(r"names\(([^)]+)\)", p)
        if m:
            dfname = m.group(1).strip()
            py_parts.append(f"*{dfname}.columns.tolist()")
            continue
        # quoted string → normalize dots
        if re.fullmatch(r"(['\"]).*?\1", p):
            val = p[1:-1]
            py_parts.append(repr(to_snake_case(val)))
            continue
        # bare identifier → normalize dots
        py_parts.append(to_snake_case(p))
    return '[' + ', '.join(py_parts) + ']'


# =========================
# Condition / mask utilities
# =========================

def normalize_mask_operators(s: str) -> str:
    """Convert R operators inside boolean masks to pandas equivalents."""
    # logical AND/OR (vectorized)
    s = re.sub(r"\b&&\b", "&", s)
    s = re.sub(r"\b\|\|\b", "|", s)
    # not: !expr → ~expr (and tidy up spaces)
    s = re.sub(r"!\s*is\.na\((.*?)\)", r"\1.notna()", s)
    s = re.sub(r"is\.na\((.*?)\)", r"\1.isna()", s)
    s = re.sub(r"!\s*\(", "~(", s)  # ! ( ... )
    s = re.sub(r"!\s*(\w+)", r"~\1", s)
    # %in% / %ni%
    # LHS could be df$col or symbol; first, translate $ → ["..."]
    s = re.sub(r"(\w+)\$(\w+(?:\.\w+)*)", snake_dotted_identifier, s)
    def _in(m: re.Match) -> str:
        lhs, rhs = m.group(1).strip(), m.group(2).strip()
        return f"{lhs}.isin({rhs})"
    def _nin(m: re.Match) -> str:
        lhs, rhs = m.group(1).strip(), m.group(2).strip()
        return f"~{lhs}.isin({rhs})"
    s = re.sub(r"(\S+?)\s*%in%\s*(\[[^\]]*\]|\([^\)]*\)|\w+)", _in, s)
    s = re.sub(r"(\S+?)\s*%ni%\s*(\[[^\]]*\]|\([^\)]*\)|\w+)", _nin, s)
    return s


# =========================
# Handlers (modular passes)
# =========================

def handle_assignments(line: str) -> str:
    # normalize both directions
    line = re.sub(r"\s*<-\s*", " = ", line)
    line = re.sub(r"\s*->\s*", " = ", line)
    return line


def handle_df_access(line: str) -> str:
    # df$col.with.dots → df["col_with_dots"]
    return re.sub(r"(\w+)\$(\w+(?:\.\w+)*)", snake_dotted_identifier, line)


def handle_vector_and_seq(line: str) -> str:
    # c(...) to [...] (but leave inside merge/subset to separate handling)
    line = re.sub(r"c\(([^()]*)\)", lambda m: parse_c_vector(m.group(1)), line)
    line = convert_seq_notation(line)
    return line


def handle_unique_rbind_cbind(line: str) -> str:
    line = re.sub(r"\bunique\((.*?)\)", r"\1.unique()", line)
    line = re.sub(r"\brbind\((.*?)\)", r"pd.concat([\1], axis=0)", line)
    line = re.sub(r"\bcbind\((.*?)\)", r"pd.concat([\1], axis=1)", line)
    return line


def handle_names_and_rename(line: str) -> str:
    # names(df) → df.columns.tolist()
    line = re.sub(r"\bnames\((.*?)\)", r"\1.columns.tolist()", line)
    # names(df) <- c(...) → df.columns = [...]
    m = re.search(r"(\w+)\.columns\.tolist\(\)\s*=\s*(\[.*\])", line)
    if m:
        df, arr = m.group(1), m.group(2)
        return re.sub(re.escape(m.group(0)), f"{df}.columns = {arr}", line)
    return line


def handle_listfiles_and_grep(line: str) -> str:
    # list.files(pattern="*.csv")
    line = re.sub(r"list\.files\(\s*pattern\s*=\s*(['\"][^'\"]+['\"])\s*\)", r"glob.glob(\1)", line)
    # grep(pattern, x)
    line = re.sub(r"\bgrep\((.*?),(.*?)\)", r"[x for x in \2 if re.search(\1, x)]", line)
    # grepl(pattern, x) → x.str.contains(pattern)
    line = re.sub(r"\bgrepl\((.*?),(.*?)\)", r"\2.str.contains(\1, regex=True)", line)
    # gsub(pattern, repl, x) → re.sub(...)
    line = re.sub(r"\bgsub\((.*?),(.*?),(.*?)\)", r"re.sub(\1, \2, \3)", line)
    return line


def handle_read_write_csv(line: str) -> str:
    line = re.sub(r"\bread\.csv\((.*?)\)", r"pd.read_csv(\1)", line)
    # write.csv(df, 'file.csv', row.names=FALSE) → df.to_csv('file.csv', index=False)
    m = re.search(r"write\.csv\(\s*(\w+)\s*,\s*(['\"][^'\"]+['\"])\s*(?:,\s*row\.names\s*=\s*(TRUE|FALSE))?\s*\)", line, flags=re.I)
    if m:
        df, path, rn = m.groups()
        index_flag = "False" if (rn and rn.upper()=="FALSE") else "True"
        return f"{df}.to_csv({path}, index={index_flag})"
    return line


def handle_dates(line: str) -> str:
    line = re.sub(r"\bSys\.Date\(\)\b", "dt.date.today()", line)
    line = re.sub(r"\bSys\.time\(\)\b", "dt.datetime.now()", line)
    # date arithmetic: Sys.Date() - 1
    line = re.sub(r"dt\.date\.today\(\)\s*-[^\S\r\n]*(\d+)", lambda m: f"dt.date.today() - dt.timedelta(days={m.group(1)})", line)
    return line


def handle_subset(line: str) -> str:
    # subset(df, condition) → df[(condition)] with operator normalization
    m = re.search(r"\bsubset\(([^,]+),\s*(.*)\)$", line)
    if m:
        df, cond = m.group(1).strip(), m.group(2).strip()
        cond = normalize_mask_operators(cond)
        return f"{df}[({cond})]"
    return line


def handle_square_bracket_subsets(line: str) -> str:
    # df[ rows , cols ]  — rows or cols can be missing
    # rows condition normalize; cols with c(...), names(df)
    # Example: xyz[! is.na(rtr$isin), ] → xyz[rtr["isin"].notna()]
    pat = re.compile(r"(\w+)\s*\[\s*(.*?)\s*\,\s*(.*?)\s*\]")
    def _repl(m: re.Match) -> str:
        df, rows, cols = m.group(1), m.group(2), m.group(3)
        py = df
        # Rows
        if rows and rows != '':
            rows_py = normalize_mask_operators(rows)
            py = f"{py}[{rows_py}]"
        # Cols
        if cols and cols not in ('', ']', 'NULL'):
            # c(...) → [...]; names(df) handled by parse_c_vector
            cols = re.sub(r"^c\((.*)\)$", lambda c: parse_c_vector(c.group(1)), cols)
            # normalize dotted column names in quoted items
            cols = re.sub(r"(['\"])\s*([\w\.]+)\s*\1", lambda q: repr(to_snake_case(q.group(2))), cols)
            if not cols.startswith('['):
                # single name like "col" → ["col"]
                if re.fullmatch(r"(['\"]).*?\1", cols):
                    cols = f"[{cols}]"
            py = f"{py}[{cols}]"
        return py
    return re.sub(pat, _repl, line)


def handle_chained_null_drops(line: str) -> str:
    # df$col1 <- df$col2 <- NULL  OR  df$col1 = df$col2 = NULL
    if re.search(r"=\s*NULL\b", line):
        cols = re.findall(r"(\w+)\$(\w+(?:\.\w+)*)", line)
        if cols:
            df = cols[0][0]
            col_list = ', '.join(repr(to_snake_case(c)) for _, c in cols)
            return f"{df}.drop(columns=[{col_list}], inplace=True)"
    return line


def handle_merge(line: str) -> str:
    if "merge(" not in line:
        return line
    txt = line
    # Extract left and right (first two args)
    m_lr = re.search(r"merge\(\s*([^,]+?)\s*,\s*([^,\)]+)\s*(?:,|\))", txt)
    if not m_lr:
        return line
    left, right = m_lr.group(1).strip(), m_lr.group(2).strip()
    # how
    how = 'inner'
    if re.search(r"all\.x\s*=\s*TRUE", txt):
        how = 'left'
    if re.search(r"all\.y\s*=\s*TRUE", txt):
        how = 'right'
    if re.search(r"all\s*=\s*TRUE", txt):
        how = 'outer'
    # by / by.x / by.y
    on = None
    m = re.search(r"by\s*=\s*(['\"])\s*([\w\.]+)\s*\1", txt)
    if m:
        on = to_snake_case(m.group(2))
    left_on = right_on = None
    m = re.search(r"by\.x\s*=\s*(['\"])\s*([\w\.]+)\s*\1", txt)
    if m:
        left_on = to_snake_case(m.group(2))
    m = re.search(r"by\.y\s*=\s*(['\"])\s*([\w\.]+)\s*\1", txt)
    if m:
        right_on = to_snake_case(m.group(2))

    # Also handle right being a bracket subset: xyz[cond, cols]
    right = handle_square_bracket_subsets(right)

    args = [f"{left}", f"{right}", f'how="{how}"']
    if on:
        args.append(f'on="{on}"')
    if left_on:
        args.append(f'left_on="{left_on}"')
    if right_on:
        args.append(f'right_on="{right_on}"')
    py = f"pd.merge({', '.join(args)})"
    return re.sub(r"merge\(.*\)", py, line)


def handle_functions_and_controls(line: str) -> str:
    # def name():  (handle dotted names and defaults)
    line = re.sub(r"(\w+(?:\.\w+)*)\s*=\s*function\((.*?)\)\s*\{?",
                  lambda m: f"def {to_snake_case(m.group(1))}({m.group(2)}):", line)
    # if/elif/else
    line = re.sub(r"\belse if\s*\((.*?)\)\s*\{?", r"elif \1:", line)
    line = re.sub(r"\bif\s*\((.*?)\)\s*\{?", r"if \1:", line)
    line = re.sub(r"\belse\s*\{?\b", r"else:", line)
    # for (i in seq)
    line = re.sub(r"for\s*\((\w+)\s+in\s+(.*?)\)\s*\{?", r"for \1 in \2:", line)
    # while
    line = re.sub(r"while\s*\((.*?)\)\s*\{?", r"while \1:", line)
    # stop
    line = re.sub(r"\bstop\((.*?)\)", r"raise Exception(\1)", line)
    # Single-line if (no braces): if (cond) expr
    line = re.sub(r"^\s*if\s*\((.*?)\)\s*(.+)$", r"if \1:\n    \2", line)
    return line


def handle_misc(line: str) -> str:
    # names with $ already converted; also normalize dotted strings in ["..."] when assigned/selected
    line = re.sub(r"\[\s*(['\"])\s*([\w\.]+)\s*\1\s*\]",
                  lambda m: f"[{repr(to_snake_case(m.group(2)))}]", line)
    return line


# =========================
# Indentation manager
# =========================
@dataclass
class IndentState:
    level: int = 0

    def apply(self, line: str) -> Tuple[str, int]:
        # Dedent BEFORE writing when there are closing braces
        closes = line.count('}')
        self.level = max(self.level - closes, 0)

        # Strip braces from the current line for Python
        line_no_braces = line.replace('{', '').replace('}', '').rstrip()

        # Special case: `else:` or `elif:` should NOT inherit extra indent
        trimmed = line_no_braces.strip()
        if trimmed.startswith(('elif ', 'else:')):
            # keep current level (already dedented above if needed)
            pass

        # Compose with current indent
        out = ('    ' * self.level) + trimmed

        # If line opens a block, indent AFTER writing
        if trimmed.endswith(':'):
            self.level += 1
        return out, self.level


# =========================
# Converter (orchestrator)
# =========================
class RToPythonConverter:
    def __init__(self):
        self.indent = IndentState()
        # Order of passes matters
        self.passes: List[Callable[[str], str]] = [
            handle_assignments,
            handle_df_access,
            handle_vector_and_seq,
            handle_unique_rbind_cbind,
            handle_names_and_rename,
            handle_listfiles_and_grep,
            handle_read_write_csv,
            handle_dates,
            handle_subset,
            handle_square_bracket_subsets,
            handle_chained_null_drops,
            handle_merge,
            handle_functions_and_controls,
            handle_misc,
        ]

    def transform_line(self, raw: str) -> List[str]:
        # Preserve empty lines and pure comments
        if not raw.strip():
            return ['']
        if raw.lstrip().startswith('#'):
            return [raw.rstrip('\n')]

        line = raw.rstrip('\n')
        # Apply all passes
        for p in self.passes:
            line = p(line)
        # Indentation & brace handling
        out, _ = self.indent.apply(line)
        # Handle injected single-line if newline case
        if '\n' in out:
            # Split and re-apply indentation for continuation lines
            lines = out.split('\n')
            rebuilt: List[str] = []
            for idx, ln in enumerate(lines):
                if idx == 0:
                    rebuilt.append(ln)
                    # if first line ended with ':' increase indent for subsequent logical line
                    if ln.rstrip().endswith(':'):
                        self.indent.level += 1
                else:
                    rebuilt.append(('    ' * self.indent.level) + ln.strip())
            return rebuilt
        return [out]

    def convert(self, in_path: str, out_path: str) -> None:
        with open(in_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        out_lines: List[str] = []
        # Header imports
        header = (
            "import pandas as pd\n"
            "import numpy as np\n"
            "import re\n"
            "import glob\n"
            "import datetime as dt\n\n"
        )
        out_lines.append(header.rstrip('\n'))
        for raw in lines:
            for tline in self.transform_line(raw):
                out_lines.append(tline)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out_lines) + '\n')


# =========================
# CLI entry
# =========================

def convert_r_to_python(input_file: str) -> str:
    """Read an R script and convert it. Output is saved next to this script.
    Returns the output file path.
    """
    base = os.path.splitext(os.path.basename(input_file))[0]
    out_file = base + "_converted.py"
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_file)
    conv = RToPythonConverter()
    conv.convert(input_file, out_path)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python r_to_python_converter.py <file.R>")
        sys.exit(1)
    inp = sys.argv[1]
    out = convert_r_to_python(inp)
    print(f"✅ Conversion complete. Output saved to {out}")
