import os
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
from neo4j_manager import Neo4jManager # New import

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
    def __init__(self, neo4j_manager: Neo4jManager): # Modified signature
        if _parser is None:
            raise ImportError("tree-sitter-kotlin is required for Kotlin parsing but not installed.")
        self.neo4j_manager = neo4j_manager # Store neo4j_manager
        logger.info("Initialized KotlinSourceParser.")

    def _get_kotlin_file_metadata(self, absolute_disk_path: Path, file_relative_path_in_graph: str) -> Dict[str, Any]:
        """
        Parses a .kt file and returns a dictionary with package and top-level types (FQNs).
        Handles Kotlin's synthetic "Kt" class naming convention.
        """
        try:
            with open(absolute_disk_path, "rb") as f: # Read as binary for tree-sitter
                content = f.read()

            tree = _parser.parse(content)
            root = tree.root_node

            package_name = ""
            found_types_with_kind = []
            has_top_level_members = False

            for child in root.children:
                if child.type == "package_header":
                    for node in child.children:
                        if node.type == "qualified_identifier":
                            package_name = node.text.decode("utf-8")
                            break
                elif child.type in ["class_declaration", "object_declaration", "interface_declaration", "annotation_class"]:
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        found_types_with_kind.append((name_node.text.decode("utf-8"), child.type))
                elif child.type in ["function_declaration", "property_declaration"]:
                    has_top_level_members = True

            fqns = []
            prefix = f"{package_name}." if package_name else ""

            for type_name, kind in found_types_with_kind:
                fqns.append(f"{prefix}{type_name}")

            if has_top_level_members:
                base_name = os.path.splitext(absolute_disk_path.name)[0]
                virtual_class_simple_name = f"{base_name.capitalize()}Kt"
                fqns.append(f"{prefix}{virtual_class_simple_name}")

            if package_name and package_name not in fqns:
                fqns.append(package_name)

            return {
                "path": file_relative_path_in_graph,
                "package": package_name,
                "fqns": fqns
            }
        except Exception as e:
            logger.error(f"Error reading or processing Kotlin file {absolute_disk_path}: {e}")
            return {
                "path": file_relative_path_in_graph,
                "package": "",
                "fqns": [],
                "error": str(e)
            }

    def parse_project(self) -> List[Dict[str, Any]]: # Modified signature and logic
        """
        Queries Neo4j for Kotlin source files, parses them, and returns their metadata.
        """
        query = """
        MATCH (a:Artifact:Directory)-[:CONTAINS]->(f:File)
        WHERE (NOT f:Directory) AND (f.fileName ENDS WITH '.kt') 
        RETURN a.fileName AS artifactAbsolutePath, f.fileName AS fileRelativePath
        """
        kotlin_files_in_graph = self.neo4j_manager.execute_read_query(query)

        files_to_parse_info = []
        for record in kotlin_files_in_graph:
            artifact_abs_path = record["artifactAbsolutePath"]
            file_rel_path = record["fileRelativePath"]
            absolute_disk_path = Path(os.path.join(artifact_abs_path, file_rel_path.lstrip('/')))
            files_to_parse_info.append((absolute_disk_path, file_rel_path))

        all_kotlin_metadata = []
        logger.info(f"Parsing {len(files_to_parse_info)} Kotlin files from graph query.")
        for absolute_disk_path, file_relative_path_in_graph in files_to_parse_info:
            metadata = self._get_kotlin_file_metadata(absolute_disk_path, file_relative_path_in_graph)
            if metadata:
                all_kotlin_metadata.append(metadata)
        logger.info(f"Finished parsing. Found metadata for {len(all_kotlin_metadata)} Kotlin files.")
        return all_kotlin_metadata

