import re

def check_latex_environments(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Strip comments to avoid checking commented-out blocks
    content_clean = re.sub(r'(?<!\\)%.*', '', content)
    
    begins = re.findall(r'\\begin\{([a-zA-Z*]+)\}', content_clean)
    ends = re.findall(r'\\end\{([a-zA-Z*]+)\}', content_clean)
    
    print(f"Total \\begin blocks: {len(begins)}")
    print(f"Total \\end blocks: {len(ends)}")
    
    # Track open environments in a stack
    stack = []
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        # Strip comments in this line
        line_clean = re.sub(r'(?<!\\)%.*', '', line)
        
        for match in re.finditer(r'\\begin\{([a-zA-Z*]+)\}', line_clean):
            env_name = match.group(1)
            stack.append((env_name, line_num))
            
        for match in re.finditer(r'\\end\{([a-zA-Z*]+)\}', line_clean):
            env_name = match.group(1)
            if not stack:
                print(f"[ERROR] Found \\end{{{env_name}}} at line {line_num} with no matching \\begin!")
            else:
                last_env, start_line = stack.pop()
                if last_env != env_name:
                    print(f"[ERROR] Mismatch: \\begin{{{last_env}}} at line {start_line} closed by \\end{{{env_name}}} at line {line_num}!")
                    
    # Remaining unclosed blocks
    if stack:
        print("\n[ERROR] Unclosed environments remaining:")
        for env_name, line_num in stack:
            print(f" - \\begin{{{env_name}}} at line {line_num} is never closed!")
    else:
        print("\n[OK] All \\begin and \\end environments are correctly matched!")

if __name__ == "__main__":
    check_latex_environments("ieee_journal_paper.tex")
