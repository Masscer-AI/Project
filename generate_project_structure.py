import os

def generate_structure(root_dir, ignore_dirs=None):
    if ignore_dirs is None:
        ignore_dirs = ['venv', 'node_modules', '.git']
    
    structure = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter out ignored directories
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        
        level = dirpath.replace(root_dir, '').count(os.sep)
        indent = ' ' * 4 * (level)
        structure.append(f"{indent}├── {os.path.basename(dirpath)}/")
        
        subindent = ' ' * 4 * (level + 1)
        for f in filenames:
            structure.append(f"{subindent}├── {f}")
    
    return structure

def save_structure_to_file(structure, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in structure:
            f.write(line + '\n')

if __name__ == "__main__":
    root_directory = '.'  # Change this to your project's root directory if needed
    output_file = 'project_structure.txt'
    
    project_structure = generate_structure(root_directory)
    save_structure_to_file(project_structure, output_file)
    
    print(f"Project structure saved to {output_file}")
