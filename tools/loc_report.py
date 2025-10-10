import json
import re
import subprocess

# Collect tracked files
files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()

# Helper to read file safely
def read_lines(fp: str):
    try:
        with open(fp, encoding="utf-8", errors="ignore") as f:
            return f.readlines()
    except Exception:
        return []

py_files = [f for f in files if f.endswith(".py")]

categories = {
    "core_py": [f for f in py_files if f.startswith("core/")],
    "modules_py": [f for f in py_files if f.startswith("modules/")],
    "tests_py": [f for f in py_files if f.startswith("tests/")],
    "tools_py": [f for f in py_files if f.startswith("tools/")],
    "workflows_yml": [f for f in files if f.startswith(".github/workflows/")],
    "html_templates": [f for f in files if f.startswith("templates/") or f.endswith(".html")],
    "docs_md": [f for f in files if (f.startswith("docs/") or f.endswith(".md")) and not f.startswith(".github/")],
}

# Count function
comment_re = re.compile(r"^\s*(#|$)")

report = {}
for key, flist in categories.items():
    total = 0
    code = 0
    for fp in flist:
        lines = read_lines(fp)
        total += len(lines)
        if fp.endswith(".py"):
            code += sum(1 for line in lines if not comment_re.match(line))
        else:
            code += sum(1 for line in lines if line.strip())
    report[key] = {
        "files": len(flist),
        "lines_total": total,
        "lines_code_est": code
    }

# Totals
all_total = 0
all_code = 0
for fp in files:
    lines = read_lines(fp)
    all_total += len(lines)
    if fp.endswith(".py"):
        all_code += sum(1 for line in lines if not comment_re.match(line))
    else:
        all_code += sum(1 for line in lines if line.strip())

report["summary"] = {
    "tracked_files": len(files),
    "total_lines": all_total,
    "estimated_code_lines": all_code,
    "python_files": len(py_files),
    "python_total_lines": sum(len(read_lines(f)) for f in py_files)
}

print(json.dumps(report, indent=2))
