#!/usr/bin/env bash

# Clean common generated files from a Git repository.
# Safe targets only: caches, build artifacts, logs, OS/editor junk.

set -u
set -o pipefail

DRY_RUN=false
VERBOSE=false

FILES_DELETED=0
DIRS_DELETED=0
ERRORS=0

print_usage() {
  cat <<EOF
Usage: ./scripts/clean_repo.sh [options]

Options:
  --dry-run     Show what would be deleted without deleting anything
  --verbose     Print every deleted path
  -h, --help    Show this help message
EOF
}

log_info() {
  echo "INFO: $*"
}

log_success() {
  echo "SUCCESS: $*"
}

log_warn() {
  echo "WARNING: $*"
}

log_error() {
  echo "ERROR: $*" >&2
}

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=true
      ;;
    --verbose)
      VERBOSE=true
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      log_error "Unknown option: $arg"
      print_usage
      exit 1
      ;;
  esac
done

delete_file() {
  local path="$1"

  if [[ ! -f "$path" ]]; then
    return 0
  fi

  if [[ "$VERBOSE" == true || "$DRY_RUN" == true ]]; then
    echo "FILE: $path"
  fi

  if [[ "$DRY_RUN" == false ]]; then
    if rm -f "$path"; then
      FILES_DELETED=$((FILES_DELETED + 1))
    else
      log_error "Failed to delete file: $path"
      ERRORS=$((ERRORS + 1))
    fi
  else
    FILES_DELETED=$((FILES_DELETED + 1))
  fi
}

delete_dir() {
  local path="$1"

  if [[ ! -d "$path" ]]; then
    return 0
  fi

  if [[ "$VERBOSE" == true || "$DRY_RUN" == true ]]; then
    echo "DIR:  $path"
  fi

  if [[ "$DRY_RUN" == false ]]; then
    if rm -rf "$path"; then
      DIRS_DELETED=$((DIRS_DELETED + 1))
    else
      log_error "Failed to delete directory: $path"
      ERRORS=$((ERRORS + 1))
    fi
  else
    DIRS_DELETED=$((DIRS_DELETED + 1))
  fi
}

delete_matching_files() {
  local pattern="$1"

  while IFS= read -r -d '' file; do
    delete_file "$file"
  done < <(find . -type f -name "$pattern" -print0 2>/dev/null)
}

delete_matching_dirs() {
  local pattern="$1"

  while IFS= read -r -d '' dir; do
    delete_dir "$dir"
  done < <(find . -type d -name "$pattern" -prune -print0 2>/dev/null)
}

delete_known_dir() {
  local dir="$1"

  if [[ -d "$dir" ]]; then
    delete_dir "$dir"
  fi
}

delete_known_file() {
  local file="$1"

  if [[ -f "$file" ]]; then
    delete_file "$file"
  fi
}

log_info "Starting repository cleanup..."

if [[ "$DRY_RUN" == true ]]; then
  log_warn "Dry-run mode is enabled. Nothing will be deleted."
fi

if ! command -v git >/dev/null 2>&1; then
  log_error "git is not installed or not available in PATH."
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  log_error "This script must be run inside a Git repository."
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -z "$REPO_ROOT" || ! -d "$REPO_ROOT" ]]; then
  log_error "Could not determine repository root."
  exit 1
fi

cd "$REPO_ROOT" || {
  log_error "Could not change directory to repository root: $REPO_ROOT"
  exit 1
}

log_info "Repository root: $REPO_ROOT"

log_info "Cleaning Python caches..."
delete_matching_dirs "__pycache__"
delete_matching_files "*.pyc"
delete_matching_files "*.pyo"
delete_matching_files "*.pyd"

log_info "Cleaning Python tool caches..."
delete_known_dir ".pytest_cache"
delete_known_dir ".mypy_cache"
delete_known_dir ".ruff_cache"
delete_known_dir ".tox"
delete_known_dir ".nox"
delete_known_file ".coverage"
delete_matching_files ".coverage.*"
delete_known_dir "htmlcov"

log_info "Cleaning build artifacts..."
delete_known_dir "build"
delete_known_dir "dist"
delete_known_dir "site"
delete_known_dir ".eggs"
delete_matching_dirs "*.egg-info"

log_info "Cleaning Node/frontend caches..."
delete_known_dir ".next"
delete_known_dir ".nuxt"
delete_known_dir ".vite"
delete_known_dir "coverage"

log_info "Cleaning OS and editor junk..."
delete_matching_files ".DS_Store"
delete_matching_files "Thumbs.db"
delete_matching_files "desktop.ini"
delete_matching_files "*~"
delete_matching_files "*.swp"
delete_matching_files "*.swo"

log_info "Cleaning log files..."
delete_matching_files "*.log"

echo
echo "Cleanup summary"
echo "---------------"
echo "Files matched/deleted:       $FILES_DELETED"
echo "Directories matched/deleted: $DIRS_DELETED"
echo "Errors:                      $ERRORS"

if [[ "$DRY_RUN" == true ]]; then
  log_success "Dry-run completed. No files were actually deleted."
elif [[ "$ERRORS" -eq 0 ]]; then
  log_success "Repository cleanup completed successfully."
else
  log_warn "Repository cleanup completed with $ERRORS error(s)."
  exit 1
fi