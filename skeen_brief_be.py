import os
import re
import sys

def main():
    src_dir = os.path.join(os.getcwd(), 'src')
    summary_lines = ["# Skeen Backend Status Summary\n"]
    
    summary_lines.append("## API Routes")
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    routes = re.findall(r'@(?:app|router)\.(?:get|post|put|delete|patch)\([^\)]+\)', content)
                    if routes:
                        rel_path = os.path.relpath(path, src_dir)
                        summary_lines.append(f"### {rel_path}")
                        for r in routes:
                            summary_lines.append(f"- {r}")

    summary_lines.append("\n## Domain Entities")
    for root, dirs, files in os.walk(src_dir):
        if 'domain' in root:
            for file in files:
                if file.endswith('.py'):
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        classes = re.findall(r'class\s+([^:\(]+).*?:', content)
                        if classes:
                            rel_path = os.path.relpath(path, src_dir)
                            summary_lines.append(f"### {rel_path}")
                            for c in classes:
                                summary_lines.append(f"- {c.strip()}")
    
    # write to /tmp or current folder
    out_path = os.path.join(os.environ.get('TEMP', '/tmp'), 'skeen_summary.txt')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary_lines))
    print(f"Summary generated at {out_path}")
    print('\n'.join(summary_lines))

if __name__ == "__main__":
    main()
