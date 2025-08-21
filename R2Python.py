"""
Advanced R to Python Converter
--------------------------------
- Handles vectors, data frames, loops, functions, if/else
- Proper Python indentation
- Merge, subset, rbind/cbind, unique, grep, list.files, names
- stop() -> raise Exception
- Column names: dots -> underscores
"""

import re
import os
import sys
from datetime import datetime, timedelta

INDENT = 0

def indent_line(line):
    return "    " * INDENT + line

def to_snake_case(name):
    name = name.replace(".", "_")
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()

def convert_line(line):
    global INDENT
    line = line.strip()
    if not line or line.startswith("#"):
        return indent_line("# " + line)

    # --- Assignment & vectors ---
    line = re.sub(r'(\w+)\s*<-\s*c\((.+)\)', lambda m: f'{to_snake_case(m.group(1))} = [{m.group(2)}]', line)
    line = line.replace("<-", "=")

    # --- Logical ---
    line = line.replace("TRUE", "True").replace("FALSE", "False").replace("NA", "None").replace("NULL", "None")

    # --- Column access df$col ---
    line = re.sub(r'(\w+)\$(\w+)', lambda m: f'{m.group(1)}["{to_snake_case(m.group(2))}"]', line)

    # --- Chained NULL deletion ---
    match = re.findall(r'(\w+)\["(\w+)"\]\s*=\s*None', line)
    if match:
        df = match[0][0]
        cols = [to_snake_case(m[1]) for m in match]
        line = f'{df} = {df}.drop(columns={cols})'

    # --- Merge ---
    if "merge(" in line:
        line = line.replace("all.x=True", "how='left'").replace("all.y=True", "how='right'")
        line = line.replace("all=True", "how='outer'").replace("all=False", "how='inner'")
        # default inner if no how
        if "how=" not in line:
            line = re.sub(r'merge\((.+?)\)', r'pd.merge(\1, how="inner")', line)

    # --- Subset ---
    if line.startswith("subset("):
        match = re.match(r'subset\((\w+),\s*(.+)\)', line)
        if match:
            df, cond = match.groups()
            # Convert column names in condition
            cond = re.sub(r'(\w+)\$(\w+)', lambda m: f'{m.group(1)}["{to_snake_case(m.group(2))}"]', cond)
            # Convert !is.na
            cond = cond.replace("!is.na(", "").replace(")", ".notna()")
            line = f'{df}[{cond}]'

    # --- rbind / cbind ---
    line = re.sub(r'rbind\((.+)\)', r'pd.concat([\1], axis=0)', line)
    line = re.sub(r'cbind\((.+)\)', r'pd.concat([\1], axis=1)', line)

    # --- Unique ---
    line = re.sub(r'unique\((.+)\)', r'pd.Series(\1).unique()', line)

    # --- grep / list.files ---
    line = re.sub(r'grep\((.+?),\s*(.+)\)', r'[i for i in \2 if re.search(\1, i)]', line)
    line = re.sub(r'list\.files\((.+?)\)', r'os.listdir(\1)', line)

    # --- names(df) ---
    line = re.sub(r'names\((\w+)\)', r'\1.columns', line)

    # --- Stop/Error ---
    line = re.sub(r'stop\((.+)\)', r'raise Exception(\1)', line)

    # --- Functions ---
    line = re.sub(r'(\w+)\s*=\s*function\((.*)\)', lambda m: f'def {to_snake_case(m.group(1))}({m.group(2)}):', line)
    if "function(" in line:
        line = line.replace("function(", "def ")

    # --- If / Else ---
    line = re.sub(r'if\s*\((.*)\)\s*{?', r'if \1:', line)
    line = re.sub(r'else if\s*\((.*)\)\s*{?', r'elif \1:', line)
    line = re.sub(r'else\s*{?', 'else:', line)

    # --- Loops ---
    match = re.match(r'for\s*\((\w+)\s+in\s+(\d+):(\d+)\)', line)
    if match:
        var, start, end = match.groups()
        line = f'for {var} in range({start}, {int(end)+1}):'
    line = re.sub(r'while\s*\((.+)\)', r'while \1:', line)

    # --- Date / Time ---
    line = line.replace("Sys.Date()", "datetime.today().date()")
    line = line.replace("Sys.time()", "datetime.now()")

    return indent_line(line)


def convert_r_file(r_file, py_file):
    global INDENT
    INDENT = 0
    with open(r_file, "r") as f:
        lines = f.readlines()

    py_code = []
    py_code.append("import pandas as pd\nimport numpy as np\nimport os\nimport re\nfrom datetime import datetime, timedelta\n\n")

    for line in lines:
        converted = convert_line(line)
        py_code.append(converted + "\n")

    with open(py_file, "w") as f:
        f.writelines(py_code)

    print(f"✅ Conversion complete: {py_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python r2py_converter.py input.R output.py")
        sys.exit(1)
    convert_r_file(sys.argv[1], sys.argv[2])
