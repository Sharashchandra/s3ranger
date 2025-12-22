# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-12-20

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
