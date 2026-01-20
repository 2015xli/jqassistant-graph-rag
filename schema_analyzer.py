import logging
from typing import List, Dict, Any, Optional
from neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)

class SchemaAnalyzer:
    """
    Provides methods to analyze and display the jQAssistant graph schema.
    """
    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
        logger.info("Initialized SchemaAnalyzer.")

    def list_node_labels_and_counts(self) -> List[Dict[str, Any]]:
        """Lists all node labels in the graph and their counts."""
        query = """
        CALL db.labels() YIELD label
        MATCH (n:$(label))
        RETURN label, count(n) AS count
        ORDER BY count DESC        """
        logger.info("Listing node labels and counts...")
        return self.neo4j_manager.execute_read_query(query)

    def list_relationship_types_and_counts(self) -> List[Dict[str, Any]]:
        """Lists all relationship types in the graph and their counts."""
        query = """
        CALL db.relationshipTypes() YIELD relationshipType
        MATCH ()-[r:$(relationshipType)]->()
        RETURN relationshipType, count(r) AS count
        ORDER BY count DESC        """
        logger.info("Listing relationship types and counts...")
        return self.neo4j_manager.execute_read_query(query)

    def inspect_node_properties(self, label: str, limit: int = 5) -> Dict[str, Any]:
        """Inspects properties of a given node label."""
        logger.info(f"Inspecting properties for label '{label}'...")
        # Get distinct keys
        keys_query = f"MATCH (n:{label}) RETURN DISTINCT keys(n) LIMIT 1"
        distinct_keys = self.neo4j_manager.execute_read_query(keys_query)
        
        # Get sample nodes
        sample_query = f"MATCH (n:{label}) RETURN n LIMIT {limit}"
        sample_nodes = self.neo4j_manager.execute_read_query(sample_query)

        return {"label": label, "distinct_keys": distinct_keys, "sample_nodes": sample_nodes}

    def inspect_relationships(self, rel_type: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Inspects relationships of a given type."""
        logger.info(f"Inspecting relationships of type '{rel_type}'...")
        query = f"MATCH (s)-[r:{rel_type}]->(t) RETURN labels(s) AS startLabels, s.fileName AS startFileName, type(r) AS relType, labels(t) AS endLabels, t.fileName AS endFileName LIMIT {limit}"
        return self.neo4j_manager.execute_read_query(query)

    def analyze_schema(self):
        """Executes all schema analysis queries and logs the results."""
        logger.info("\n--- Starting jQAssistant Schema Analysis ---")

        logger.info("\nNode Labels and Counts:")
        labels_counts = self.list_node_labels_and_counts()
        for item in labels_counts:
            logger.info(f"  - {item['label']}: {item['count']}")

        logger.info("\nRelationship Types and Counts:")
        rel_counts = self.list_relationship_types_and_counts()
        for item in rel_counts:
            logger.info(f"  - {item['relationshipType']}: {item['count']}")

        # Inspect properties for common labels
        common_labels = ['File', 'Directory', 'Package', 'Type', 'Type:Class', 'Type:Interface', 'Type:Enum', 'Method', 'Field', 'Artifact', 'Jar'] # Updated labels
        for label in common_labels:
            props_info = self.inspect_node_properties(label)
            if props_info['sample_nodes']:
                logger.info(f"\nProperties for {label}:")
                logger.info(f"  Distinct Keys: {props_info['distinct_keys']}")
                logger.info(f"  Sample Nodes: {props_info['sample_nodes']}")
            else:
                logger.info(f"\nNo nodes found for label: {label}")

        # Inspect common relationships
        common_rel_types = ['CONTAINS', 'DECLARES', 'EXTENDS', 'IMPLEMENTS', 'INVOKES'] # Updated rel types
        for rel_type in common_rel_types:
            rel_info = self.inspect_relationships(rel_type)
            if rel_info:
                logger.info(f"\nSample relationships for :{rel_type}:")
                for item in rel_info:
                    # Use 'fileName' for Artifact/Jar nodes, 'fileName' for File/Directory
                    start_id = item['startFileName'] if 'startFileName' in item else item.get('artifactName', 'N/A')
                    end_id = item['endFileName'] if 'endFileName' in item else item.get('artifactName', 'N/A')
                    logger.info(f"  - {item['startLabels']} {start_id} -[:{item['relType']}]-> {item['endLabels']} {end_id}")
            else:
                logger.info(f"\nNo relationships found for type: :{rel_type}:")

        # Specific inspection for Artifact/Jar relationships
        logger.info("\nSpecific Inspection for Artifact/Jar Nodes:")
        artifact_rel_query = """
        MATCH (a:Artifact)-[r]->(n)
        RETURN labels(a) AS startLabels, a.fileName AS artifactFileName, type(r) AS relType, labels(n) AS endLabels, n.fileName AS endFileName
        LIMIT 10
        """
        artifact_rels = self.neo4j_manager.execute_read_query(artifact_rel_query)
        if artifact_rels:
            for item in artifact_rels:
                logger.info(f"  - {item['startLabels']} {item['artifactFileName']} -[:{item['relType']}]-> {item['endLabels']} {item['endFileName']}")
        else:
            logger.info("  No Artifact relationships found.")


        logger.info("\n--- jQAssistant Schema Analysis Complete ---")
