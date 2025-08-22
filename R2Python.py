"""
Advanced R to Python Converter (Production-Ready)
-------------------------------------------------
- Handles vectors, data frames, loops, functions, if/else
- Proper Python indentation and block handling
- Merge, subset, rbind/cbind, unique, grep, list.files, names
- stop() -> raise Exception
- Column names: dots -> underscores (PEP8)
- Vectors c(...) anywhere
"""

import re
import os
import sys
from datetime import datetime, timedelta

INDENT = 0  # Tracks current indentation level

def indent_line(line):
    return "    " * INDENT + line

def to_snake_case(name):
    # Replace dots with underscores and convert to lower case
    name = name.replace(".", "_")
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()

def convert_vectors(line):
    # Convert R vectors c(...) to Python lists [...]
    pattern = r'c\(([^()]+?)\)'
    while re.search(pattern, line):
        line = re.sub(pattern, lambda m: f"[{m.group(1)}]", line)
    return line

def convert_merge(line):
    # Handle merge with default inner join and all.x/all.y/all
    if "merge(" in line:
        args = line[line.find("(")+1:line.rfind(")")]
        how = "inner"  # default inner
        if "all.x=True" in args:
            how = "left"
            args = args.replace("all.x=True", "")
        elif "all.y=True" in args:
            how = "right"
            args = args.replace("all.y=True", "")
        elif "all=True" in args:
            how = "outer"
            args = args.replace("all=True", "")
        elif "all=False" in args:
            how = "inner"
            args = args.replace("all=False", "")
        args = args.strip().rstrip(",")
        line = f"pd.merge({args}, how='{how}')"
    return line

def convert_line(line):
    global INDENT
    original_line = line
    line = line.strip()
    if not line or line.startswith("#"):
        return indent_line("# " + line)

    # --- Convert vectors first ---
    line = convert_vectors(line)

    # --- Logical / constants ---
    line = line.replace("TRUE", "True").replace("FALSE", "False")
    line = line.replace("NA", "None").replace("NULL", "None")

    # --- Column access df$col ---
    line = re.sub(
        r'(\w+)\$(\w+)',
        lambda m: f'{m.group(1)}["{to_snake_case(m.group(2))}"]',
        line
    )

    # --- Chained NULL column deletion ---
    match = re.findall(r'(\w+)\["(\w+)"\]\s*=\s*None', line)
    if match:
        df = match[0][0]
        cols = [to_snake_case(m[1]) for m in match]
        line = f'{df} = {df}.drop(columns={cols})'

    # --- Merge ---
    line = convert_merge(line)

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
    line = re.sub(
        r'(\w[\w\.]*)\s*<-\s*function\((.*)\)',
        lambda m: f'def {to_snake_case(m.group(1))}({m.group(2)}):',
        line
    )
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

    # --- Dates / Time ---
    line = line.replace("Sys.Date()", "datetime.today().date()")
    line = line.replace("Sys.time()", "datetime.now()")
    line = line.replace("today()", "datetime.today().date()")
    line = line.replace("yesterday()", "(datetime.today() - timedelta(days=1)).date()")

    # --- Handle braces for indentation ---
    if line.endswith(":"):
        INDENT += 1
    if "}" in line:
        INDENT -= line.count("}")
        line = line.replace("}", "")

    return indent_line(line)

def convert_r_file(r_file, py_file):
    global INDENT
    INDENT = 0
    with open(r_file, "r") as f:
        lines = f.readlines()

    py_code = []
    # Add imports at top
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
