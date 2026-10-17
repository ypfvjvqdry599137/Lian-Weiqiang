#!/usr/bin/env bash
set -euo pipefail

source_dir="${UPLOAD_FOLDER:-/srv/fresh-produce/uploads}"
backup_dir="${IMAGE_BACKUP_DIR:-/home/ubuntu/Lian-Weiqiang/backups/uploads}"

if [ ! -d "$source_dir" ]; then
    printf 'Upload directory does not exist: %s\n' "$source_dir" >&2
    exit 1
fi

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
archive="$backup_dir/uploads_$(date +%Y-%m-%d).tar.gz"
temporary="$(mktemp "$backup_dir/.uploads_XXXXXX")"
trap 'rm -f -- "$temporary"' EXIT

tar -czf "$temporary" -C "$source_dir" .
mv -f -- "$temporary" "$archive"
sha256sum "$archive" > "$archive.sha256"
printf 'Image backup created: %s\n' "$archive"
