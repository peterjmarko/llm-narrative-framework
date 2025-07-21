import hashlib
import subprocess
import os

def get_git_commit_hash():
    """Returns the short git commit hash of the current repository."""
    try:
        # Assumes the script is run from the project root.
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"

def calculate_file_checksum(file_path):
    """Calculates the SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    if not os.path.exists(file_path):
        return "file_not_found"
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()