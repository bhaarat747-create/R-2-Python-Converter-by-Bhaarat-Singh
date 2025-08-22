import re
import os
import sys
import glob
import datetime as dt

# =========================
# Utility functions
# =========================

def to_snake_case(name: str) -> str:
    """Convert R-style names (dots, camelCase) to Python snake_case"""
    # Replace dots/dashes with underscores
    name = re.sub(r'[\.\-]', '_', name)
    # Convert CamelCase → snake_case
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    return name.lower()


def handle_assignment(line: str) -> str:
    """Convert R assignment <- or -> to Python ="""
    line = re.sub(r'\s*<-\s*', ' = ', line)
    line = re.sub(r'\s*->\s*', ' = ', line)  # support reverse assignment
    return line


def handle_vectors(line: str) -> str:
    """Convert R vectors c("a","b") and sequences to Python lists/ranges"""
    # c(...) → list
    line = re.sub(r'c\((.*?)\)', r'[\1]', line)

    # 1:5 → range(1,6)
    line = re.sub(r'(\d+):(\d+)', lambda m: f'range({m.group(1)}, {int(m.group(2))+1})', line)

    # seq(1,10,2) → range(1,11,2)
    line = re.sub(r'seq\((\d+),\s*(\d+)(?:,\s*(\d+))?\)',
                  lambda m: f'range({m.group(1)}, {int(m.group(2))+1}' +
                            (f', {m.group(3)})' if m.group(3) else ')'),
                  line)

    return line


def handle_dataframes(line: str) -> str:
    """Handle R dataframe syntax: $, drops, subset of cols"""
    # df$col → df["col"]
    line = re.sub(r'(\w+)\$(\w+(?:\.\w+)*)',
                  lambda m: f'{m.group(1)}["{to_snake_case(m.group(2))}"]', line)

    # Drop columns: df$col1 <- df$col2 <- NULL
    if re.search(r'<-\s*NULL', line):
        cols = re.findall(r'(\w+)\$(\w+(?:\.\w+)*)', line)
        if cols:
            df = cols[0][0]
            col_list = [f'"{to_snake_case(c[1])}"' for c in cols]
            return f'{df}.drop(columns=[{", ".join(col_list)}], inplace=True)'

    # df <- df[, c("id","name")]
    match = re.match(r'(\w+)\s*=\s*\1\[, *\[(.*?)\]\]', line)
    if match:
        df = match.group(1)
        cols = match.group(2).replace('"', "'")
        return f'{df} = {df}[[{cols}]]'

    # Negative indexing: df <- df[, -1]
    neg_match = re.match(r'(\w+)\s*=\s*\1\[, *-(\d+)\]', line)
    if neg_match:
        df, idx = neg_match.groups()
        return f'{df} = {df}.drop({df}.columns[{int(idx)-1}], axis=1)'

    return line


def handle_merge(line: str) -> str:
    """Convert R merge() to pandas merge()"""
    if "merge(" not in line:
        return line

    how = "inner"
    left_on, right_on, on = None, None, None

    if "all.x=TRUE" in line:
        how = "left"
    if "all.y=TRUE" in line:
        how = "right"
    if "all=TRUE" in line:
        how = "outer"

    # by, by.x, by.y
    m = re.search(r'by\s*=\s*["\'](\w+)["\']', line)
    if m: on = m.group(1)

    m = re.search(r'by\.x\s*=\s*["\'](\w+)["\']', line)
    if m: left_on = m.group(1)

    m = re.search(r'by\.y\s*=\s*["\'](\w+)["\']', line)
    if m: right_on = m.group(1)

    args = re.findall(r'merge\(([^,]+),\s*([^,\)]+)', line)
    if args:
        left, right = [a.strip() for a in args[0]]
    else:
        return line

    merge_expr = f'pd.merge({left}, {right}, how="{how}"'
    if on: merge_expr += f', on="{on}"'
    if left_on: merge_expr += f', left_on="{left_on}"'
    if right_on: merge_expr += f', right_on="{right_on}"'
    merge_expr += ')'

    return re.sub(r'merge\(.*\)', merge_expr, line)


def handle_functions(line: str) -> str:
    """Convert R function definitions and stop()"""
    # function definition with defaults
    line = re.sub(r'(\w+(?:\.\w+)*)\s*=\s*function\s*\((.*?)\)',
                  lambda m: f'def {to_snake_case(m.group(1))}({m.group(2)}):',
                  line)

    # stop("msg") -> raise Exception("msg")
    line = re.sub(r'stop\((.*?)\)', r'raise Exception(\1)', line)
    return line


def handle_controls(line: str) -> str:
    """Handle if/else/for/while"""
    line = re.sub(r'if\s*\((.*?)\)\s*\{?', r'if \1:', line)
    line = re.sub(r'else if\s*\((.*?)\)\s*\{?', r'elif \1:', line)
    line = re.sub(r'else\s*\{?', r'else:', line)
    line = re.sub(r'for\s*\((\w+)\s+in\s+(.*?)\)\s*\{?', r'for \1 in \2:', line)
    line = re.sub(r'while\s*\((.*?)\)\s*\{?', r'while \1:', line)
    return line


def handle_misc(line: str) -> str:
    """Miscellaneous translations"""
    line = re.sub(r'!is\.na\((.*?)\)', r'\1.notna()', line)
    line = re.sub(r'is\.na\((.*?)\)', r'\1.isna()', line)
    line = re.sub(r'unique\((.*?)\)', r'\1.unique()', line)
    line = re.sub(r'rbind\((.*?)\)', r'pd.concat([\1], axis=0)', line)
    line = re.sub(r'cbind\((.*?)\)', r'pd.concat([\1], axis=1)', line)
    line = re.sub(r'names\((.*?)\)', r'list(\1.columns)', line)
    line = re.sub(r'names\((.*?)\)\s*=\s*\[(.*?)\]', r'\1.columns = [\2]', line)
    line = re.sub(r'list\.files\(pattern\s*=\s*"(.*?)"\)', r'glob.glob("\1")', line)
    line = re.sub(r'grep\((.*?),(.*?)\)', r'[x for x in \2 if re.search(\1, x)]', line)
    line = re.sub(r'%in%\s*', '.isin', line)
    return line


# =========================
# Indentation Manager
# =========================
def adjust_indentation(line: str, indent_level: int) -> (str, int):
    close_count = line.count("}")
    indent_level = max(indent_level - close_count, 0)

    line = line.replace("{", "").replace("}", "").rstrip()

    indented_line = "    " * indent_level + line.strip()

    if indented_line.endswith(":"):
        indent_level += 1

    return indented_line, indent_level


# =========================
# Main Converter
# =========================
def convert_r_to_python(input_file: str):
    """Convert an R script into Python (output saved in script folder)"""
    output_file = os.path.splitext(os.path.basename(input_file))[0] + "_converted.py"
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_file)

    with open(input_file, 'r') as infile, open(output_path, 'w') as outfile:
        outfile.write("import pandas as pd\nimport numpy as np\nimport os\nimport re\nimport glob\nimport datetime as dt\n\n")

        indent_level = 0
        for raw_line in infile:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                outfile.write(line + "\n")
                continue

            line = handle_assignment(line)
            line = handle_vectors(line)
            line = handle_dataframes(line)
            line = handle_merge(line)
            line = handle_functions(line)
            line = handle_controls(line)
            line = handle_misc(line)

            line, indent_level = adjust_indentation(line, indent_level)

            outfile.write(line + "\n")

    print(f"✅ Conversion complete. Output saved to {output_path}")


# =========================
# Entry Point
# =========================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python r_to_python_converter.py <R_script_file>")
    else:
        convert_r_to_python(sys.argv[1])
