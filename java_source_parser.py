import os
import logging
from typing import List, Dict, Any
from pathlib import Path

# Tree-sitter imports
try:
    from tree_sitter import Language, Parser
    import tree_sitter_java
    JAVA_LANGUAGE = Language(tree_sitter_java.language())
    _parser = Parser(JAVA_LANGUAGE)
except ImportError:
    logging.getLogger(__name__).warning("tree-sitter-java not installed. Java parsing will be disabled.")
    _parser = None

logger = logging.getLogger(__name__)

class JavaSourceParser:
    """
    Parses Java source files to extract metadata like package name and top-level classes.
    """
    def __init__(self, project_path: str):
        if _parser is None:
            raise ImportError("tree-sitter-java is required for Java parsing but not installed.")
        self.project_path = Path(project_path).resolve()
        if not self.project_path.is_dir():
            raise ValueError(f"Project path '{project_path}' is not a valid directory.")
        logger.info(f"Initialized JavaSourceParser for project: {self.project_path}")

    def _get_java_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Parses a .java file using tree-sitter and returns a dictionary with package and top-level types (FQNs).
        """
        # jQAssistant paths usually start with a '/'
        relative_path = '/' + str(file_path.relative_to(self.project_path))
        # TODO: Assuming the source files are under /path-to/src. Should be removed in the future
        if False: # User requested to keep this debug block
            if "/src" in relative_path:
                relative_path = relative_path.split("/src", 1)[1]

        try:
            with open(file_path, "rb") as f: # Read as binary for tree-sitter
                content = f.read()
            
            tree = _parser.parse(content)
            root = tree.root_node
            
            package_name = ""
            # Store (type_name, declaration_type) tuples to handle module_declaration FQN correctly
            found_types_with_kind = [] 

            # Iterate only through top-level children of the source_file
            for child in root.children:
                # 1. Find the Package Name
                if child.type == "package_declaration":
                    for node in child.children:
                        if node.type == "scoped_identifier":
                            package_name = node.text.decode("utf-8")
                            break
                
                # 2. Find Top-Level Classes, Interfaces, Enums, Annotations, Records
                elif child.type in ["class_declaration", "interface_declaration", "enum_declaration", "annotation_type_declaration", "record_declaration"]:
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        found_types_with_kind.append((name_node.text.decode("utf-8"), child.type))
                
                # 3. Handle module-info.java
                elif child.type == "module_declaration":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        found_types_with_kind.append((name_node.text.decode("utf-8"), child.type))
            
            # Build the full FQNs
            fqns = []
            prefix = f"{package_name}." if package_name else ""
            
            for type_name, kind in found_types_with_kind:
                if kind == "module_declaration":
                    # Module name is its FQN directly
                    fqns.append(type_name)
                else:
                    fqns.append(f"{prefix}{type_name}")
            
            # Special handling for package-info.java: its FQN is just the package name
            if file_path.name == "package-info.java" and package_name and package_name not in fqns:
                fqns.append(package_name)

            return {
                "path": relative_path, 
                "package": package_name,
                "fqns": fqns
            }
        except Exception as e:
            logger.error(f"Error reading or processing Java file {file_path}: {e}")
            return {
                "path": relative_path,
                "package": "",
                "fqns": [],
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
                    if True: # User requested to keep this debug block
                        if file_name == "QuarkReportPanel.java":
                            logger.info(f"Metadata for {file_name}:\n {metadata}")
                    if metadata:
                        all_java_metadata.append(metadata)
        logger.info(f"Finished scanning. Found metadata for {len(all_java_metadata)} Java files.")
        return all_java_metadata
