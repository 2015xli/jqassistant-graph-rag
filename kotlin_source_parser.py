import os
import logging
from typing import List, Dict, Any
from pathlib import Path

# Tree-sitter imports
try:
    from tree_sitter import Language, Parser
    import tree_sitter_kotlin
    KOTLIN_LANGUAGE = Language(tree_sitter_kotlin.language())
    _parser = Parser(KOTLIN_LANGUAGE)
except ImportError:
    logging.getLogger(__name__).warning("tree-sitter-kotlin not installed. Kotlin parsing will be disabled.")
    _parser = None

logger = logging.getLogger(__name__)

class KotlinSourceParser:
    """
    Parses Kotlin source files to extract metadata like package name and top-level types,
    including synthetic "Kt" classes for top-level functions/properties.
    """
    def __init__(self, project_path: str):
        if _parser is None:
            raise ImportError("tree-sitter-kotlin is required for Kotlin parsing but not installed.")
        self.project_path = Path(project_path).resolve()
        if not self.project_path.is_dir():
            raise ValueError(f"Project path '{project_path}' is not a valid directory.")
        logger.info(f"Initialized KotlinSourceParser for project: {self.project_path}")

    def _get_kotlin_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Parses a .kt file and returns a dictionary with package and top-level types (FQNs).
        Handles Kotlin's synthetic "Kt" class naming convention.
        """

        # jqAssistant has a leading / for all paths
        relative_path = '/' + str(file_path.relative_to(self.project_path))
        # TODO: Assuming the source files are under /path-to/src. Should be removed in the future
        if True: # User requested to keep this debug block
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
            has_top_level_members = False # Flag for synthetic Kt class

            # Iterate only through top-level children of the source_file
            for child in root.children:
                # 1. Find the Package Name
                if child.type == "package_header":
                    for node in child.children:
                        if node.type == "qualified_identifier":
                            package_name = node.text.decode("utf-8")
                            break
                
                # 2. Find Top-Level Classes, Objects, Interfaces, Annotations
                elif child.type in ["class_declaration", "object_declaration", "interface_declaration", "annotation_class"]:
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        found_types_with_kind.append((name_node.text.decode("utf-8"), child.type))
                
                # 3. Check for members that trigger a "FileKt" facade
                elif child.type in ["function_declaration", "property_declaration"]:
                    has_top_level_members = True

            # Build the full FQNs
            fqns = []
            prefix = f"{package_name}." if package_name else ""
            
            for type_name, kind in found_types_with_kind:
                # Kotlin doesn't have module_declaration in source files like Java
                fqns.append(f"{prefix}{type_name}")
                
            # Logic for Virtual "Kt" Class
            if has_top_level_members:
                base_name = os.path.splitext(file_path.name)[0]
                virtual_class_simple_name = f"{base_name.capitalize()}Kt"
                fqns.append(f"{prefix}{virtual_class_simple_name}")
            
            # Special handling for package FQN (Kotlin doesn't have package-info.java, but the package itself is a type)
            if package_name and package_name not in fqns:
                fqns.append(package_name)

            return {
                "path": relative_path,
                "package": package_name,
                "fqns": fqns
            }
        except Exception as e:
            logger.error(f"Error reading or processing Kotlin file {file_path}: {e}")
            return {
                "path": relative_path,
                "package": "",
                "fqns": [],
                "error": str(e)
            }

    def parse_project(self) -> List[Dict[str, Any]]:
        """
        Walks the project directory, parses all Kotlin files, and returns their metadata.
        """
        all_kotlin_metadata = []
        logger.info(f"Scanning project directory for Kotlin files: {self.project_path}")
        for root, _, files in os.walk(self.project_path):
            for file_name in files:
                if file_name.endswith(".kt"):
                    file_path = Path(root) / file_name
                    metadata = self._get_kotlin_file_metadata(file_path)
                    if metadata:
                        all_kotlin_metadata.append(metadata)
        logger.info(f"Finished scanning. Found metadata for {len(all_kotlin_metadata)} Kotlin files.")
        return all_kotlin_metadata
