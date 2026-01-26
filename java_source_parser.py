import os
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
from neo4j_manager import Neo4jManager # New import

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
    def __init__(self, neo4j_manager: Neo4jManager): # Modified signature
        if _parser is None:
            raise ImportError("tree-sitter-java is required for Java parsing but not installed.")
        self.neo4j_manager = neo4j_manager # Store neo4j_manager
        logger.info("Initialized JavaSourceParser.")

    def _get_java_file_metadata(self, absolute_disk_path: Path, file_relative_path_in_graph: str) -> Dict[str, Any]:
        """
        Parses a .java file using tree-sitter and returns a dictionary with package and top-level types (FQNs).
        """
        try:
            with open(absolute_disk_path, "rb") as f: # Read as binary for tree-sitter
                content = f.read()

            tree = _parser.parse(content)
            root = tree.root_node

            package_name = ""
            found_types_with_kind = []

            for child in root.children:
                if child.type == "package_declaration":
                    for node in child.children:
                        if node.type == "scoped_identifier":
                            package_name = node.text.decode("utf-8")
                            break
                elif child.type in ["class_declaration", "interface_declaration", "enum_declaration", "annotation_type_declaration", "record_declaration"]:
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        found_types_with_kind.append((name_node.text.decode("utf-8"), child.type))
                elif child.type == "module_declaration":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        found_types_with_kind.append((name_node.text.decode("utf-8"), child.type))

            fqns = []
            prefix = f"{package_name}." if package_name else ""

            for type_name, kind in found_types_with_kind:
                if kind == "module_declaration":
                    fqns.append(type_name)
                else:
                    fqns.append(f"{prefix}{type_name}")

            if absolute_disk_path.name == "package-info.java" and package_name and package_name not in fqns:
                fqns.append(package_name)

            return {
                "path": file_relative_path_in_graph,
                "package": package_name,
                "fqns": fqns
            }
        except Exception as e:
            logger.error(f"Error reading or processing Java file {absolute_disk_path}: {e}")
            return {
                "path": file_relative_path_in_graph,
                "package": "",
                "fqns": [],
                "error": str(e)
            }

    def parse_project(self) -> List[Dict[str, Any]]: # Modified signature and logic
        """
        Queries Neo4j for Java source files, parses them, and returns their metadata.
        """
        query = """
        MATCH (a:Artifact:Directory)-[:CONTAINS]->(f:File)
        WHERE (NOT f:Directory) AND (f.fileName ENDS WITH '.java') 
        RETURN a.fileName AS artifactAbsolutePath, f.fileName AS fileRelativePath
        """
        java_files_in_graph = self.neo4j_manager.execute_read_query(query)

        files_to_parse_info = []
        for record in java_files_in_graph:
            artifact_abs_path = record["artifactAbsolutePath"]
            file_rel_path = record["fileRelativePath"]
            absolute_disk_path = Path(os.path.join(artifact_abs_path, file_rel_path.lstrip('/')))
            files_to_parse_info.append((absolute_disk_path, file_rel_path))

        all_java_metadata = []
        logger.info(f"Parsing {len(files_to_parse_info)} Java files from graph query.")
        for absolute_disk_path, file_relative_path_in_graph in files_to_parse_info:
            metadata = self._get_java_file_metadata(absolute_disk_path, file_relative_path_in_graph)
            if metadata:
                all_java_metadata.append(metadata)
        logger.info(f"Finished parsing. Found metadata for {len(all_java_metadata)} Java files.")
        return all_java_metadata
