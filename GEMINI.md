# Workspace Rules & Guidelines

## Git & Version Control Guidelines

1. **No Automatic Git Commits**:
   - NEVER run `git commit` or `git push` on your own initiative.
   - Any git commit MUST be explicitly requested or confirmed by the user.

2. **Pre-Commit Verification**:
   - Before proposing or executing a commit, always run `git status` to inspect all modified, staged, and untracked files.
   - Check untracked files carefully to ensure no temporary files, debug scripts, build artifacts, compiled binaries, or large files (e.g., images, caches) are being accidentally committed.
   - When asking for confirmation, present:
     - The exact list of files to be committed.
     - Highlight any net-new or untracked files.
     - The proposed commit message.
   - Wait for the user's explicit approval before proceeding.

3. **Granular Staging**:
   - NEVER use indiscriminate staging commands like `git add .`, `git add -A`, or `git add *`.
   - Always stage files selectively and explicitly by path (e.g., `git add path/to/file.py`).

## Project Cleanliness

- Keep the project root clean: no temporary `test_*`, `patch_*`, or scratch files in the root folder.
- Temporary or exploratory test scripts must be placed in `tests/scratch/` or equivalent test subdirectories.
