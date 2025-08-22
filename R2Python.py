import re
import os
import pandas as pd

# -----------------------------
# Utility: Clean column names
# -----------------------------
def clean_colname(name: str) -> str:
    return name.strip().replace(".", "_")

# -----------------------------
# Expression parser (for c(...))
# -----------------------------
def parse_c_expression(expr: str) -> str:
    parts = re.split(r",\s*", expr.strip())
    py_parts = []
    for p in parts:
        if p.startswith("\"") or p.startswith("'"):
            py_parts.append(p.replace(".", "_"))
        elif p.startswith("names("):
            df = re.search(r"names\((.*?)\)", p).group(1)
            py_parts.append(f"*{df}.columns.tolist()")
        else:
            py_parts.append(p.replace(".", "_"))
    return "[" + ", ".join(py_parts) + "]"

# -----------------------------
# Line-by-line R → Python translator
# -----------------------------
def r_to_python_line(line: str, indent_level: int):
    original = line

    # Dedent if closing brace
    if "}" in line:
        indent_level = max(indent_level - line.count("}"), 0)

    # Replace assignment <- with =
    line = re.sub(r"<-", "=", line)

    # DataFrame column access: df$col → df["col"]
    line = re.sub(r"(\w+)\$(\w+(?:\.\w+)*)", lambda m: f'{m.group(1)}["{clean_colname(m.group(2))}"]', line)

    # unique() → .unique()
    line = re.sub(r"unique\((.*?)\)", r"\1.unique()", line)

    # rbind / cbind → pd.concat
    line = re.sub(r"rbind\((.*?)\)", r"pd.concat([\1], axis=0)", line)
    line = re.sub(r"cbind\((.*?)\)", r"pd.concat([\1], axis=1)", line)

    # names(df)
    line = re.sub(r"names\((.*?)\)", r"\1.columns.tolist()", line)

    # %in% → .isin()
    line = re.sub(r"(\w+) %in% (\S+)", r"\1.isin(\2)", line)
    # %ni% → ~.isin()
    line = re.sub(r"(\w+) %ni% (\S+)", r"~\1.isin(\2)", line)

    # is.na / !is.na
    line = re.sub(r"is.na\((.*?)\)", r"\1.isna()", line)
    line = re.sub(r"!\s*is.na\((.*?)\)", r"\1.notna()", line)

    # subset(df, cond)
    line = re.sub(r"subset\((.*?),\s*(.*?)\)", r"\1[\2]", line)

    # merge()
    if "merge(" in line:
        m = re.search(r"merge\((.*?),(.*?),by.x=\"(.*?)\", by.y=\"(.*?)\"\)", line)
        if m:
            left, right, byx, byy = m.groups()
            line = f"pd.merge({left.strip()}, {right.strip()}, left_on=\"{byx}\", right_on=\"{byy}\", how=\"inner\")"

    # Column subset like df[, c(...)]
    if re.search(r"(\w+)\s*=.*\[,\s*c\((.*?)\)\]", line):
        df, expr = re.search(r"(\w+)\s*=.*\[,\s*c\((.*?)\)\]", line).groups()
        pylist = parse_c_expression(expr)
        line = f"{df} = {df}[{pylist}]"

    # Function definitions
    line = re.sub(r"(\w+)\s*=\s*function\((.*?)\)", r"def \1(\2):", line)

    # if / else if / else
    line = re.sub(r"if \((.*?)\)", r"if \1:", line)
    line = re.sub(r"else if \((.*?)\)", r"elif \1:", line)
    line = re.sub(r"else", r"else:", line)

    # stop()
    line = re.sub(r"stop\((.*?)\)", r"raise Exception(\1)", line)

    # Remove leftover braces
    line = line.replace("{", "").replace("}", "")

    # Add indentation
    py_line = ("    " * indent_level) + line.strip()

    # Increase indent after block openers
    if py_line.endswith(":"):
        indent_level += 1

    return py_line, indent_level

# -----------------------------
# File-level converter
# -----------------------------
def convert_r_to_python(r_file):
    with open(r_file, "r") as f:
        r_lines = f.readlines()

    py_lines = []
    indent_level = 0

    for line in r_lines:
        if not line.strip():
            py_lines.append("")
            continue
        py_line, indent_level = r_to_python_line(line, indent_level)
        py_lines.append(py_line)

    # Save next to script
    base = os.path.splitext(os.path.basename(r_file))[0]
    py_file = os.path.join(os.path.dirname(__file__), base + ".py")
    with open(py_file, "w") as f:
        f.write("\n".join(py_lines))

    print(f"Converted {r_file} → {py_file}")


# Example usage:
# convert_r_to_python("/path/to/input.R")
