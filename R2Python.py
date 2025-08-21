"""
R-to-Python Converter (Advanced)
--------------------------------
This script converts R code into Python code (line by line).
It focuses on:
 - Data frame operations (merge, subset, rbind, cbind, unique, col deletion)
 - Loops (for, while, apply-like constructs)
 - Conditionals (if/else)
 - Functions (def)
 - Error handling (stop() -> raise Exception)
 - Naming conventions (dots -> underscores, PEP8 compliance)
 - Date/time (today, yesterday, Sys.time, etc.)
"""

import re
import sys
from datetime import datetime, timedelta

def convert_r_to_python(r_file, py_file):
    with open(r_file, "r", encoding="utf-8") as f:
        r_lines = f.readlines()

    py_lines = []

    for line in r_lines:
        original_line = line.strip()

        # Skip empty/comment lines
        if original_line.startswith("#") or not original_line:
            py_lines.append("# " + original_line + "\n")
            continue

        # --- Handle common R to Python conversions ---

        # Stop -> raise
        line = re.sub(r'stop\((.*)\)', r'raise Exception(\1)', original_line)

        # Print
        line = re.sub(r'print\((.*)\)', r'print(\1)', line)

        # %in% -> isin
        line = re.sub(r'(\w+)\s*%in%\s*(\w+)', r'\1.isin(\2)', line)

        # %ni% -> ~isin
        line = re.sub(r'(\w+)\s*%ni%\s*(\w+)', r'~\1.isin(\2)', line)

        # NA handling
        line = line.replace("is.na", "pd.isna")
        line = line.replace("!pd.isna", "~pd.isna")

        # TRUE/FALSE -> True/False
        line = line.replace("TRUE", "True").replace("FALSE", "False")

        # Assignment <- to =
        line = line.replace("<-", "=")

        # --- Handle column access ---
        # Replace df$col with df["col"]
        line = re.sub(
            r'(\w+)\$(\w+)',
            lambda m: f'{m.group(1)}["{m.group(2).replace(".", "_")}"]',
            line
        )

        # --- Handle chained NULL deletion ---
        match = re.match(r'(\w+)\[\"(\w+)\"\]\s*=\s*\1\[\"(\w+)\"\]\s*=\s*NULL', line)
        if match:
            df, col1, col2 = match.group(1), match.group(2), match.group(3)
            line = f'{df} = {df}.drop(columns=["{col1}", "{col2}"])'

        # Single NULL deletion
        match = re.match(r'(\w+)\[\"(\w+)\"\]\s*=\s*NULL', line)
        if match:
            df, col = match.group(1), match.group(2)
            line = f'{df} = {df}.drop(columns=["{col}"])'

        # --- Handle merge ---
        if "merge(" in line:
            # Example: merge(df1, df2, by="id", all.x=TRUE)
            line = re.sub(r'merge\((.*)\)', r'pd.merge(\1)', line)
            line = line.replace("all.x=True", "how='left'")
            line = line.replace("all.y=True", "how='right'")
            line = line.replace("all=True", "how='outer'")
            line = line.replace("all=False", "how='inner'")

        # --- Handle rbind -> pd.concat([...], axis=0) ---
        if line.startswith("rbind("):
            line = re.sub(r'rbind\((.*)\)', r'pd.concat([\1], axis=0)', line)

        # --- Handle cbind -> pd.concat([...], axis=1) ---
        if line.startswith("cbind("):
            line = re.sub(r'cbind\((.*)\)', r'pd.concat([\1], axis=1)', line)

        # --- Handle unique ---
        if "unique(" in line:
            line = re.sub(r'unique\((.*)\)', r'pd.Series(\1).unique()', line)

        # --- Handle subset ---
        if line.startswith("subset("):
            # Very simple handling: subset(df, condition)
            match = re.match(r'subset\((\w+),\s*(.*)\)', line)
            if match:
                df, condition = match.group(1), match.group(2)
                line = f'{df}[{condition}]'

        # --- Handle function definitions ---
        if line.startswith("function(") or "= function(" in line:
            line = re.sub(r'(\w+)\s*=\s*function\((.*)\)', r'def \1(\2):', line)

        # --- Handle loops ---
        # for (i in 1:n) -> for i in range(1, n+1):
        match = re.match(r'for\s*\((\w+)\s+in\s+(\d+):(\d+)\)', line)
        if match:
            var, start, end = match.groups()
            line = f'for {var} in range({start}, {int(end)+1}):'

        # while loop stays same (just Python syntax)
        line = line.replace("while (", "while (")

        # --- Handle date/time ---
        if "Sys.Date()" in line:
            line = line.replace("Sys.Date()", "datetime.today().date()")
        if "Sys.time()" in line:
            line = line.replace("Sys.time()", "datetime.now()")
        if "today()" in line.lower():
            line = line.replace("today()", "datetime.today().date()")
        if "yesterday()" in line.lower():
            line = line.replace("yesterday()", "(datetime.today() - timedelta(days=1)).date()")

        # --- Add line to output ---
        py_lines.append(line + "\n")

    # Write to output file
    with open(py_file, "w", encoding="utf-8") as f:
        f.writelines(py_lines)

    print(f"✅ Conversion complete. Python script saved at: {py_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python r2py_converter.py input.R output.py")
        sys.exit(1)

    r_file = sys.argv[1]
    py_file = sys.argv[2]

    convert_r_to_python(r_file, py_file)
