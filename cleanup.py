import tokenize
import io
import os
import re

def remove_comments_and_clean_whitespace(source):
    """
    Safely removes # comments and collapses multiple blank lines.
    """
    try:
        io_obj = io.StringIO(source)
        out = ""
        last_lineno = 1
        last_col = 0
        
        tokens = tokenize.generate_tokens(io_obj.readline)
        
        for tok in tokens:
            token_type = tok.type
            token_string = tok.string
            start_line, start_col = tok.start
            end_line, end_col = tok.end
            
            if token_type == tokenize.COMMENT:
                continue
                
            if start_line > last_lineno:
                out += "\n" * (start_line - last_lineno)
                last_col = 0
                
            out += " " * (start_col - last_col)
            out += token_string
            
            last_lineno = end_line
            last_col = end_col
        
        # Post-process: Remove lines with only whitespace and collapse multiple blank lines
        lines = out.splitlines()
        cleaned_lines = []
        for line in lines:
            line_content = line.rstrip()
            if line_content or (not cleaned_lines or cleaned_lines[-1] != ""):
                cleaned_lines.append(line_content)
        
        # Trim multiple blank lines at the start and end
        result = "\n".join(cleaned_lines).strip()
        
        # Ensure only one blank line maximum anywhere
        result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)
        
        return result + "\n"
    except Exception as e:
        print(f"Tokenization error: {e}")
        return source

def process_directory(directory="."):
    for root, dirs, files in os.walk(directory):
        if ".git" in dirs:
            dirs.remove(".git")
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        for file in files:
            if file.endswith(".py") and file != "cleanup.py":
                file_path = os.path.join(root, file)
                print(f"Processing {file_path}...")
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                cleaned = remove_comments_and_clean_whitespace(content)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned)

if __name__ == "__main__":
    process_directory()
