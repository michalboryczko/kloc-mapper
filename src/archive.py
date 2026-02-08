"""Archive loader for .kloc files.

.kloc archives are ZIP files containing:
- index.scip: SCIP protobuf index (required)
- calls.json: Calls and values data (optional)
"""

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ArchiveError(Exception):
    """Raised when archive loading fails."""
    pass


@dataclass
class KlocArchive:
    """Loaded .kloc archive contents.

    Provides access to the extracted files.
    """
    scip_path: Path
    calls_data: Optional[dict]
    _temp_dir: Optional[tempfile.TemporaryDirectory]

    @classmethod
    def load(cls, archive_path: str | Path) -> "KlocArchive":
        """Load a .kloc archive.

        Args:
            archive_path: Path to the .kloc archive file.

        Returns:
            KlocArchive with extracted contents.

        Raises:
            ArchiveError: If the archive is invalid or missing required files.
            FileNotFoundError: If the archive file doesn't exist.
        """
        archive_path = Path(archive_path)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        # Verify it's a valid ZIP file
        if not zipfile.is_zipfile(archive_path):
            raise ArchiveError(f"Invalid archive format: {archive_path} is not a valid ZIP file")

        # Create temp directory for extraction
        temp_dir = tempfile.TemporaryDirectory(prefix="kloc_")
        temp_path = Path(temp_dir.name)

        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                # Check for required files
                names = zf.namelist()

                if "index.scip" not in names:
                    raise ArchiveError(f"Archive missing index.scip: {archive_path}")

                # Extract all files
                zf.extractall(temp_path)

            # Load calls.json if present
            calls_path = temp_path / "calls.json"
            calls_data = None
            if calls_path.exists():
                try:
                    with open(calls_path, "r") as f:
                        calls_data = json.load(f)
                except json.JSONDecodeError as e:
                    raise ArchiveError(f"Invalid calls.json: {e}")

            return cls(
                scip_path=temp_path / "index.scip",
                calls_data=calls_data,
                _temp_dir=temp_dir,
            )

        except Exception:
            # Clean up temp dir on error
            temp_dir.cleanup()
            raise

    @property
    def has_calls_data(self) -> bool:
        """Check if archive contains calls.json data."""
        return self.calls_data is not None

    def cleanup(self):
        """Clean up temporary files."""
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
