import os
import logging
from typing import List, Dict, Any
from pathlib import Path
import javalang # Assuming javalang is installed

logger = logging.getLogger(__name__)

class JavaSourceParser:
    """
    Parses Java source files to extract metadata like package name and top-level classes.
    """
    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        if not self.project_path.is_dir():
            raise ValueError(f"Project path '{project_path}' is not a valid directory.")
        logger.info(f"Initialized JavaSourceParser for project: {self.project_path}")

    def _get_java_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Parses a .java file and returns a dictionary with package and top-level classes.
        This is based on the user's provided code.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            filename = file_path.name
            is_special_type = filename in ["package-info.java", "module-info.java"]
            
            package_name = ""
            top_level_classes = []
            fqns = [] # Fully Qualified Names

            if not is_special_type: # javalang might struggle with module-info.java
                try:
                    tree = javalang.parse.parse(content)
                    
                    # Extract Package Name
                    if tree.package:
                        package_name = tree.package.name
                        
                    # Extract Top-Level Classes (Name only, no package string)
                    for t in tree.types:
                        if isinstance(t, (javalang.tree.ClassDeclaration, javalang.tree.InterfaceDeclaration, javalang.tree.EnumDeclaration)):
                            top_level_classes.append(t.name)
                            fqns.append(f"{package_name}.{t.name}" if package_name else t.name)
                    
                except javalang.parser.JavaSyntaxError as e:
                    logger.warning(f"Syntax error in {file_path}: {e}. Skipping detailed parsing.")
                except Exception as e:
                    logger.warning(f"Unexpected error parsing {file_path}: {e}. Skipping detailed parsing.")
            
            #jqAssistant has a leading "/" for all paths
            relative_path = '/' + str(file_path.relative_to(self.project_path))
            # TODO: Assuming the source files are under /path-to/src. Should be removed in the future
            if False:
                if "/src" in relative_path:
                    relative_path = relative_path.split("/src", 1)[1]

            return {
                "path": relative_path, 
                "package": package_name,
                "fqns": fqns,
                "is_special_type": is_special_type
            }
        except Exception as e:
            logger.error(f"Error reading or processing file {file_path}: {e}")
            return {
                "path": str(file_path.relative_to(self.project_path)),
                "package": "",
                "fqns": [],
                "is_special_type": False,
                "error": str(e)
            }

    def parse_project(self) -> List[Dict[str, Any]]:
        """
        Walks the project directory, parses all Java files, and returns their metadata.
        """
        all_java_metadata = []
        logger.info(f"Scanning project directory: {self.project_path}")
        for root, _, files in os.walk(self.project_path):
            for file_name in files:
                if file_name.endswith(".java"):
                    file_path = Path(root) / file_name
                    metadata = self._get_java_file_metadata(file_path)
                    if True: 
                        if file_name == "QuarkReportPanel.java":
                            logger.info(f"Metadata for {file_name}:\n {metadata}")
                    if metadata:
                        all_java_metadata.append(metadata)
        logger.info(f"Finished scanning. Found metadata for {len(all_java_metadata)} Java files.")
        return all_java_metadata
