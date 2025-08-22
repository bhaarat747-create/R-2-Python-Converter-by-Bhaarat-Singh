import re
import pandas as pd

def r_to_python(r_code):
    # Pre-process to put braces and 'else' on separate lines
    r_code = r_code.replace('} else if', '}\nelse if')
    r_code = r_code.replace('} else', '}\nelse')
    r_code = r_code.replace('{', '{\n')
    r_code = r_code.replace('}', '}\n')
    lines = r_code.split('\n')
    
    py_lines = []
    indent_level = 0
    indent_str = '    '  # four spaces for indentation
    
    for raw_line in lines:
        if not raw_line.strip():
            continue
        stripped = raw_line.strip()
        close_count = raw_line.count('}')
        
        # If a line starts with '}', we reduce indent before processing content
        if stripped.startswith('}'):
            indent_level -= close_count
            indent_level = max(indent_level, 0)
            continue
        
        # If a line ends with '}', reduce indent after writing the line
        reduce_after = stripped.endswith('}')
        
        # Remove any braces and trim whitespace
        line = raw_line.replace('{', '').replace('}', '').strip()
        if not line:
            continue
        
        # Handle 'else if' and 'else' specially
        if line.startswith('else if'):
            m = re.match(r'else if\s*\((.*)\)', line)
            if m:
                condition = m.group(1)
                line = f'elif {condition}:'
        elif line.startswith('else'):
            line = 'else:'
        else:
            # Replace assignment operators
            line = re.sub(r'<-', '=', line)
            line = re.sub(r'->', '=', line)
            # Replace $ with Python dict-like access (and dots in names to underscores)
            def replace_dollar(match):
                df, col = match.group(1), match.group(2)
                col_py = col.replace('.', '_')
                return f'{df}["{col_py}"]'
            line = re.sub(r'(\w+)\$([\w\.]+)', replace_dollar, line)
            # Replace c(...) with Python list [...]
            def replace_c(match):
                items = [x.strip() for x in match.group(1).split(',')]
                return "[" + ", ".join(items) + "]"
            line = re.sub(r'c\(([^)]*)\)', replace_c, line)
            # Data frame subsetting patterns (all rows, select columns)
            line = re.sub(r'(\w+)\s*=\s*(\w+)\s*\[\s*,\s*\[', r'\1 = \2[[', line)
            line = re.sub(r'(\w+)\s*\[\s*,\s*\[', r'\1[[', line)
            # unique() to pandas unique
            line = re.sub(r'unique\(', r'pd.unique(', line)
            # rbind/cbind to pandas.concat
            def replace_rbind(match):
                args = [arg.strip() for arg in match.group(1).split(',')]
                return f'pd.concat([{", ".join(args)}], ignore_index=True)'
            line = re.sub(r'rbind\(([^\)]*)\)', replace_rbind, line)
            def replace_cbind(match):
                args = [arg.strip() for arg in match.group(1).split(',')]
                return f'pd.concat([{", ".join(args)}], axis=1)'
            line = re.sub(r'cbind\(([^\)]*)\)', replace_cbind, line)
            # data.frame(...) to pd.DataFrame({...})
            def replace_df(match):
                content = match.group(1)
                items = [item.strip() for item in content.split(',')]
                dict_items = []
                for item in items:
                    if '=' in item:
                        k, v = [p.strip() for p in item.split('=', 1)]
                        dict_items.append(f"'{k}': {v}")
                    else:
                        dict_items.append(item)
                return f"pd.DataFrame({{{', '.join(dict_items)}}})"
            line = re.sub(r'data\.frame\(([^\)]*)\)', replace_df, line)
            # Logical operators
            line = re.sub(r'&&', ' and ', line)
            line = re.sub(r'\|\|', ' or ', line)
            # Negation '!' to 'not ' (careful not to break '!=')
            line = re.sub(r'!=(?!=)', '!=', line)  # no change, but to be safe
            line = re.sub(r'!(?!=)', 'not ', line)
            # If, for, and while loops
            m_if = re.match(r'if\s*\((.*)\)', line)
            if m_if:
                cond = m_if.group(1)
                line = f'if {cond}:'
            m_for = re.match(r'for\s*\(\s*(\w+)\s+in\s+([^\)]+)\)', line)
            if m_for:
                var, expr = m_for.group(1), m_for.group(2)
                # Convert R's a:b to range(a, b+1)
                expr = re.sub(r'(\d+)\s*:\s*(\d+)', 
                              lambda m: f'range({m.group(1)}, {int(m.group(2))+1})', expr)
                line = f'for {var} in {expr}:'
            m_while = re.match(r'while\s*\((.*)\)', line)
            if m_while:
                cond = m_while.group(1)
                line = f'while {cond}:'
            # cat() -> print()
            line = re.sub(r'(?<!\w)cat\(', 'print(', line)
            # Constants TRUE/FALSE/NA
            line = re.sub(r'\bTRUE\b', 'True', line)
            line = re.sub(r'\bFALSE\b', 'False', line)
            line = re.sub(r'\bNA\b', 'None', line)
            # Remove trailing semicolon
            line = line.rstrip(';')
            # Convert lone a:b to range(a, b+1)
            line = re.sub(r'(\d+)\s*:\s*(\d+)', r'range(\1, \2+1)', line)
        
        # Add the (possibly indented) Python line to output
        indent_str_line = indent_str * indent_level
        py_lines.append(indent_str_line + line)
        # If the line ends with ':', increase indentation for the next line
        if line.endswith(':'):
            indent_level += 1
        # After writing the line, if we flagged a closing '}', reduce indent
        if reduce_after:
            indent_level -= close_count
            indent_level = max(indent_level, 0)
    
    return '\n'.join(py_lines)

# Example usage:
r_code = '''
df <- data.frame(id=1:3, x=c("a","b","c"))
df2 <- data.frame(id=4:5, x=c("d","e"))
out <- rbind(df, df2)
if(nrow(out) > 3) {
    cat("Large data frame")
} else {
    cat("Small")
}
'''
print(r_to_python(r_code))
