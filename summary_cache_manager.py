import logging
import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class SummaryCacheManager:
    """
    Manages the persistence and integrity of the summary cache on disk.
    """
    def __init__(self, project_path: str):
        self.cache_dir = Path(project_path) / ".cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        self.cache_file = self.cache_dir / "summary_cache.json"
        self.tmp_cache_file = self.cache_dir / "summary_cache.json.tmp"
        self.bak1_file = self.cache_dir / "summary_cache.json.bak.1"
        self.bak2_file = self.cache_dir / "summary_cache.json.bak.2"

        self.cache: Dict[str, Dict[str, Any]] = {}
        self.runtime_status: Dict[str, Dict[str, Any]] = {}
        logger.info(f"Initialized SummaryCacheManager at {self.cache_dir}")

    def load(self):
        """Loads the cache from disk into memory."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"Successfully loaded cache from {self.cache_file} with {len(self.cache)} entries.")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load cache file {self.cache_file}: {e}. Starting with an empty cache.")
                self.cache = {}
        else:
            logger.warning(f"Cache file not found at {self.cache_file}. Starting with an empty cache.")
            self.cache = {}

    def save(self):
        """
        Saves the in-memory cache to disk using a safe, multi-stage promotion process.
        """
        logger.info("Starting cache save process...")
        try:
            with open(self.tmp_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
            
            self._promote_tmp_cache()
            logger.info("Cache save process completed successfully.")
        except IOError as e:
            logger.error(f"Failed to write to temporary cache file {self.tmp_cache_file}: {e}")

    def _promote_tmp_cache(self):
        """
        Promotes the temporary cache file to the main cache file, rotating backups.
        """
        # Sanity check to prevent overwriting a good cache with a bad one
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    old_cache_size = len(json.load(f))
                
                new_cache_size = len(self.cache)

                # Don't overwrite a large cache with a tiny one unless the old one was also tiny
                if new_cache_size < old_cache_size * 0.95 and old_cache_size > 100:
                    logger.critical(
                        f"Sanity check failed! New cache ({new_cache_size} items) is significantly smaller "
                        f"than the old one ({old_cache_size} items). Aborting promotion to prevent data loss. "
                        f"The new cache is available at {self.tmp_cache_file} for inspection."
                    )
                    return
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not perform sanity check on old cache file: {e}. Proceeding with promotion.")

        self._rotate_backups()
        shutil.move(self.tmp_cache_file, self.cache_file)
        logger.info(f"Promoted temporary cache to {self.cache_file}.")

    def _rotate_backups(self):
        """Manages a 2-level rolling backup system."""
        if self.bak2_file.exists():
            os.remove(self.bak2_file)
        if self.bak1_file.exists():
            shutil.move(self.bak1_file, self.bak2_file)
        if self.cache_file.exists():
            shutil.move(self.cache_file, self.bak1_file)
        logger.info("Rotated cache backups.")

    # --- Public API for Cache Interaction ---

    def get_node_cache(self, node_id: str) -> Dict[str, Any]:
        return self.cache.get(node_id, {})

    def update_node_cache(self, node_id: str, data: Dict[str, Any]):
        if node_id not in self.cache:
            self.cache[node_id] = {}
        self.cache[node_id].update(data)

    def set_runtime_status(self, node_id: str, status: str):
        if node_id not in self.runtime_status:
            self.runtime_status[node_id] = {}
        
        if status == 'regenerated':
            self.runtime_status[node_id]['changed'] = True
        # 'visited' can be added here if pruning is needed later

    def was_dependency_changed(self, dependency_ids: List[str]) -> bool:
        """Checks if any dependency node had its summary regenerated during this run."""
        for dep_id in dependency_ids:
            if self.runtime_status.get(dep_id, {}).get('changed', False):
                return True
        return False
