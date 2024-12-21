import os
import zipfile
from pathspec import PathSpec

def load_gitignore_patterns(gitignore_path=".gitignore"):
    """Carga los patrones del archivo .gitignore."""
    with open(gitignore_path, "r") as f:
        return PathSpec.from_lines("gitwildmatch", f.readlines())

def zip_directory(source_dir, output_file, gitignore_path=".gitignore"):
    """Crea un zip excluyendo archivos/carpetas del .gitignore."""
    if not os.path.exists(gitignore_path):
        print(f"El archivo {gitignore_path} no existe. Asegúrate de tenerlo en el directorio.")
        return

    # Cargar patrones del .gitignore
    spec = load_gitignore_patterns(gitignore_path)

    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            # Filtrar carpetas ignoradas
            dirs[:] = [d for d in dirs if not spec.match_file(os.path.relpath(os.path.join(root, d), source_dir))]
            
            for file in files:
                file_path = os.path.relpath(os.path.join(root, file), source_dir)
                if not spec.match_file(file_path):  # Excluir archivos ignorados
                    zipf.write(os.path.join(root, file), file_path)

    print(f"Archivo ZIP creado: {output_file}")

# Configuración
source_directory = "."  # Directorio actual
output_zip = "repositorio.zip"

zip_directory(source_directory, output_zip)
