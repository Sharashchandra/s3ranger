# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-01-18

### Added

- Copy and move functionality for files and folders within the same bucket or across different S3 buckets
- Interactive destination selection interface for copy/move operations

## [1.2.1] - 2025-12-28

### Added

- Configurable download directory via CLI (`--download-directory`) and config file (`download_directory`)
- Priority-based fallback for download directory: CLI → Config → `~/Downloads/` → Current working directory
- Warning notifications when download directory falls back to a different path

### Fixed

- Fixed crash when opening file picker in download modal if `~/Downloads/` doesn't exist

## [1.2.0] - 2025-12-22

### Changed

- Simplified credential handling: `--aws-access-key-id`, `--aws-secret-access-key`, and `--aws-session-token` are now only supported via CLI arguments (no longer supported in config file)
- Updated credential priority order for clarity and predictability

### Added

- Pagination for bucket list (250 buckets per page) and object list (25 objects per page)
- Infinite scroll: more items load automatically as you scroll down using mouse or arrow keys

## [1.1.0] - 2025-08-23

### Added

- Sorting functionality added for object_list - users can now sort objects by name, size, and modification date

## [1.0.0] - 2025-08-17

### Initial Release

- Terminal-based user interface for browsing and managing AWS S3 buckets and objects
- Browse S3 buckets and navigate through object hierarchies
- Upload, download, delete, and rename S3 objects
- Support for custom AWS endpoints
- Multiple UI themes (Dracula, GitHub Dark, Sepia, Solarized)
