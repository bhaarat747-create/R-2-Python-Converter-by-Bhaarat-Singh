#!/usr/bin/env python3
"""
R → Python Converter Script
---------------------------

This script converts R code into Python code line by line.
It attempts to handle the most common syntax differences:
- Assignments
- Loops (for, foreach)
- If/Else
- Functions
- Data structures (vectors, lists, data frames)
- Operators (%%, ^, %*%, %in%)
- Dates and times
- Objects / Classes
- Printing
- apply/lapply/sapply
- paste/paste0 → f-strings
- Naming conventions → PEP8 (snake_case)
- Handling NA/NULL, TRUE/FALSE

Fallback: If a line cannot be converted, it will be added as a Python comment.
"""

import re
import datetime
import pandas as pd
import numpy as np
import keyword

# ----------------------------
# Utility: Convert to snake_case
# ----------------------------
def to_snake_case(name: str) -> str:
    """
    Convert CamelCase, PascalCase, or dot.separated names to snake_case.
    Ensures compliance with Python PEP8.
    """
    if not name:
        return name
    name = name.replace(".", "_")
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    snake = s2.lower()
    if keyword.iskeyword(snake):  # Avoid Python keywords
        snake += "_var"
    return snake


# ----------------------------
# Core Conversion Function
# ----------------------------
def convert_line(line: str) -> str:
    """
    Convert a single line of R code into Python.
    Handles known patterns; otherwise, returns as a Python comment.
    """
    original = line.strip()

    # Skip empty lines
    if original == "":
        return ""

    # Comments
    if original.startswith("#"):
        return original.replace("#", "#", 1)

    # Replace TRUE/FALSE/NA/NULL
    line = re.sub(r"\bTRUE\b", "True", line)
    line = re.sub(r"\bFALSE\b", "False", line)
    line = re.sub(r"\bNA\b", "None", line)
    line = re.sub(r"\bNULL\b", "None", line)

    # Assignments
    line = re.sub(r"<-", "=", line)

    # Sys.Date() → datetime.date.today()
    line = re.sub(r"Sys\.Date\(\)", "datetime.date.today()", line)
    # Sys.Date()-1 → datetime.date.today() - datetime.timedelta(days=1)
    line = re.sub(r"datetime\.date\.today\(\)\s*-\s*1",
                  "datetime.date.today() - datetime.timedelta(days=1)", line)
    # Sys.time() → datetime.datetime.now()
    line = re.sub(r"Sys\.time\(\)", "datetime.datetime.now()", line)
    # as.POSIXct → datetime.datetime.strptime
    line = re.sub(r"as\.POSIXct\((.+?),\s*format\s*=\s*\"(.+?)\"\)",
                  r"datetime.datetime.strptime(\1, '\2')", line)

    # Operators
    line = line.replace("%%", "%")
    line = line.replace("^", "**")
    line = line.replace("%*%", "@")
    line = line.replace("%in%", " in ")

    # paste / paste0 → f-strings
    line = re.sub(r"paste0?\((.+)\)", r"f'{\1}'", line)

    # ifelse(cond, a, b) → a if cond else b
    line = re.sub(r"ifelse\((.+?),\s*(.+?),\s*(.+?)\)", r"\2 if \1 else \3", line)

    # for loops
    match = re.match(r"for\s*\((\w+)\s+in\s+(\d+):(\d+)\)", line)
    if match:
        var, start, end = match.groups()
        return f"for {to_snake_case(var)} in range({start}, {int(end)+1}):"

    match = re.match(r"for\s*\((\w+)\s+in\s+(.+)\)", line)
    if match:
        var, it = match.groups()
        return f"for {to_snake_case(var)} in {it}:"

    # while loop
    line = re.sub(r"while\s*\((.+)\)", r"while \1:", line)

    # if/else
    line = re.sub(r"if\s*\((.+)\)", r"if \1:", line)
    line = re.sub(r"else if\s*\((.+)\)", r"elif \1:", line)
    line = re.sub(r"else\s*\\{?", "else:", line)

    # Functions
    line = re.sub(r"(\w+)\s*=\s*function\s*\((.*?)\)", lambda m: f"def {to_snake_case(m.group(1))}({m.group(2)}):", line)

    # Data structures
    line = re.sub(r"c\((.+)\)", r"[\1]", line)
    line = re.sub(r"list\((.+)\)", lambda m: "{" + ", ".join([f'"{kv.split("=")[0].strip()}": {kv.split("=")[1].strip()}' for kv in m.group(1).split(",")]) + "}", line)
    line = re.sub(r"data\.frame\((.+)\)", r"pd.DataFrame({\1})", line)

    # apply / lapply / sapply
    line = re.sub(r"sapply\((.+?),\s*(.+?)\)", r"list(map(\2, \1))", line)
    line = re.sub(r"lapply\((.+?),\s*(.+?)\)", r"list(map(\2, \1))", line)
    line = re.sub(r"apply\((.+?),\s*1,\s*(.+?)\)", r"np.apply_along_axis(\2, 1, \1)", line)
    line = re.sub(r"apply\((.+?),\s*2,\s*(.+?)\)", r"np.apply_along_axis(\2, 0, \1)", line)

    # Classes (setClass)
    match = re.match(r"setClass\(\s*\"(\w+)\".*slots\s*=\s*list\((.+)\)\s*\)", line)
    if match:
        classname, slots = match.groups()
        classname = classname.capitalize()
        slots = [s.strip() for s in slots.split(",")]
        args = ", ".join([f"{to_snake_case(s.split('=')[0])}=None" for s in slots])
        init_body = "\n        ".join([f"self.{to_snake_case(s.split('=')[0])} = {to_snake_case(s.split('=')[0])}" for s in slots])
        return f"class {classname}:\n    def __init__(self, {args}):\n        {init_body}"

    # Variable naming: Convert left-hand side to snake_case
    assign_match = re.match(r"(\w+)\s*=", line)
    if assign_match:
        lhs = assign_match.group(1)
        snake = to_snake_case(lhs)
        line = line.replace(lhs, snake, 1)

    # Ensure indentation for blocks (simple heuristic)
    if line.endswith("{"):
        line = line[:-1] + ":"

    # Default: return as comment if no match
    return line if line != original else f"# TODO: Manual conversion required: {original}"


# ----------------------------
# Main converter function
# ----------------------------
def convert_r_to_python(r_file: str, py_file: str):
    with open(r_file, "r") as rf, open(py_file, "w") as pf:
        # Always include imports
        pf.write("import pandas as pd\nimport numpy as np\nimport datetime\n\n")
        for line in rf:
            converted = convert_line(line)
            pf.write(converted + "\n")


# ----------------------------
# CLI Usage
# ----------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python r2py_converter.py input.R output.py")
    else:
        convert_r_to_python(sys.argv[1], sys.argv[2])
        print(f"✅ Conversion complete. Python file saved to {sys.argv[2]}")
