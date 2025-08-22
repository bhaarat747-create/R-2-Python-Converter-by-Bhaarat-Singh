import re
import os

# =========================
# Utility functions
# =========================

def to_snake_case(name: str) -> str:
    """Convert R-style names with dots to Python snake_case"""
    return re.sub(r'[\.\-]', '_', name)


def handle_assignment(line: str) -> str:
    """Convert R assignment <- or = to Python ="""
    line = re.sub(r'\s*<-\s*', ' = ', line)
    return line


def handle_vectors(line: str) -> str:
    """Convert R vectors c("a","b") to Python lists ["a","b"]"""
    return re.sub(r'c\((.*?)\)', r'[\1]', line)


def handle_dataframes(line: str) -> str:
    """Handle R dataframe syntax: $, column removal, subset of cols"""
    # df$col -> df["col"]
    line = re.sub(r'(\w+)\$(\w+)', lambda m: f'{m.group(1)}["{to_snake_case(m.group(2))}"]', line)
    
    # Remove columns: df$col1 <- df$col2 <- NULL
    if "<- NULL" in line:
        cols = re.findall(r'(\w+)\$(\w+)', line)
        if cols:
            df = cols[0][0]
            col_list = [f'"{to_snake_case(c[1])}"' for c in cols]
            return f'{df}.drop(columns=[{", ".join(col_list)}], inplace=True)'
    
    # Column subset: df <- df[, c("id","name")]
    match = re.match(r'(\w+)\s*=\s*\1\[, *c\((.*?)\)\]', line)
    if match:
        df = match.group(1)
        cols = match.group(2).replace('"', "'")
        return f'{df} = {df}[[{cols}]]'
    
    return line


def handle_merge(line: str) -> str:
    """Convert R merge() to pandas merge()"""
    if "merge(" not in line:
        return line
    
    # Default = inner join
    how = "inner"
    by = None
    left, right = "left", "right"
    
    # Parse args
    if "all.x=TRUE" in line:
        how = "left"
    if "all.y=TRUE" in line:
        how = "right"
    if "all=TRUE" in line:
        how = "outer"
    if "by=" in line:
        by = re.findall(r'by\s*=\s*c?\((.*?)\)', line)
        if by:
            by = by[0].replace('"', "'")
    
    # Extract dataframes
    args = re.findall(r'merge\(([^,]+),([^,\)]+)', line)
    if args:
        left, right = [a.strip() for a in args[0]]
    
    merge_expr = f"{left}.merge({right}, how='{how}'"
    if by:
        merge_expr += f", on=[{by}]"
    merge_expr += ")"
    
    return re.sub(r'merge\(.*\)', merge_expr, line)


def handle_functions(line: str) -> str:
    """Convert R function definitions and stop()"""
    # function definition
    line = re.sub(r'(\w+)\s*=\s*function\s*\((.*?)\)', lambda m: f'def {to_snake_case(m.group(1))}({m.group(2)}):', line)
    # stop("msg") -> raise Exception("msg")
    line = re.sub(r'stop\((.*?)\)', r'raise Exception(\1)', line)
    return line


def handle_controls(line: str) -> str:
    """Handle if, for, while, braces"""
    # Convert if (...) {  -> if ...:
    line = re.sub(r'if\s*\((.*?)\)\s*\{?', r'if \1:', line)
    # Convert for (x in seq) {  -> for x in seq:
    line = re.sub(r'for\s*\((\w+)\s+in\s+(.*?)\)\s*\{?', r'for \1 in \2:', line)
    # while loop
    line = re.sub(r'while\s*\((.*?)\)\s*\{?', r'while \1:', line)
    # Remove closing brace
    line = line.replace("}", "")
    return line


def handle_misc(line: str) -> str:
    """Miscellaneous translations"""
    line = re.sub(r'!is\.na\((.*?)\)', r'~\1.isna()', line)
    line = re.sub(r'is\.na\((.*?)\)', r'\1.isna()', line)
    line = re.sub(r'unique\((.*?)\)', r'\1.drop_duplicates()', line)
    line = re.sub(r'rbind\((.*?)\)', r'pd.concat([\1])', line)
    line = re.sub(r'cbind\((.*?)\)', r'pd.concat([\1], axis=1)', line)
    line = re.sub(r'names\((.*?)\)', r'list(\1.columns)', line)
    line = re.sub(r'list\.files\((.*?)\)', r'os.listdir(\1)', line)
    line = re.sub(r'grep\((.*?),(.*?)\)', r'[x for x in \2 if re.search(\1, x)]', line)
    line = re.sub(r'%in%', ' in ', line)
    line = re.sub(r'%ni%', ' not in ', line)
    return line


# =========================
# Main Converter
# =========================

def convert_r_to_python(input_file: str, output_file: str):
    """Read an R script and convert it to Python"""
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        outfile.write("import pandas as pd\nimport numpy as np\nimport os\nimport re\nimport datetime as dt\n\n")
        
        indent_level = 0
        for line in infile:
            line = line.strip()
            if not line:
                continue
            
            original = line  # keep for debugging
            line = handle_assignment(line)
            line = handle_vectors(line)
            line = handle_dataframes(line)
            line = handle_merge(line)
            line = handle_functions(line)
            line = handle_controls(line)
            line = handle_misc(line)
            
            # Adjust indentation based on control flow
            if line.endswith(":"):
                outfile.write("    " * indent_level + line + "\n")
                indent_level += 1
            else:
                outfile.write("    " * indent_level + line + "\n")
    
    print(f"✅ Conversion complete. Output saved to {output_file}")


# =========================
# Example Usage
# =========================
if __name__ == "__main__":
    input_file = "demo_full.R"   # Place R script in same folder
    output_file = os.path.splitext(input_file)[0] + "_converted.py"
    convert_r_to_python(input_file, output_file)
