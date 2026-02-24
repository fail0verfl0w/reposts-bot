## Changelog (Initial release v1.0.0 - 2026-02-24)

### Changed
- Refactored [`database.py`](m:/Projects/repost-bot/reposts-bot/database.py) to use a single persistent `aiosqlite` connection instead of opening/closing a connection in every function call.
- Kept existing public API function names/signatures (`init_db`, `find_url`, `store_url`, `find_image`, `store_image`, `cleanup_old_records`) to avoid breaking `bot.py`.
- Switched SQL usage to centralized query constants (`FIND_URL_SQL`, `STORE_URL_SQL`, `FIND_IMAGE_SQL`, etc.) for maintainability and consistent query plans.
- Updated URL lookup query to return only required columns (`channel_id`, `message_id`, `author_id`, `author_name`) instead of `SELECT *`.

### Added
- Connection initialization safeguards with async locks:
  - `_init_lock` for safe one-time init.
  - `_write_lock` to serialize writes/commits.
- SQLite runtime tuning pragmas:
  - `journal_mode=WAL`
  - `synchronous=NORMAL`
  - `temp_store=MEMORY`
  - `busy_timeout=5000`
- New helper functions:
  - `_get_db()` for lazy-safe access to the shared connection.
  - `close_db()` for graceful shutdown support.
- New constants for retention and config centralization:
  - `RETENTION_HOURS`
  - `RETENTION_MODIFIER`
  - `SQLITE_BUSY_TIMEOUT_MS`
- Additional/optimized indexes:
  - `idx_urls_lookup (guild_id, normalized_url, posted_at)`
  - `idx_urls_cleanup (posted_at)`
  - `idx_images_hash (guild_id, image_hash)`
  - `idx_images_lookup (guild_id, posted_at)`
  - `idx_images_cleanup (posted_at)`

### Performance Improvements
- `find_image()` now streams rows via `async for` cursor iteration instead of `fetchall()`, reducing memory pressure for large guild datasets.
- Replaced Hamming distance calculation from `bin(x).count("1")` to `(x).bit_count()` for faster image hash comparison.
- Added fast guard in `find_image()` for invalid hash input (`TypeError`/`ValueError` handling).

### Maintenance/Cleanup
- `cleanup_old_records()` now:
  - Uses shared connection and write lock.
  - Returns total deleted row count.
  - Runs `PRAGMA optimize;` after cleanup.
- Retention window is now centralized and reused in all relevant queries (`48 hours` by default).

### Validation
- Syntax/import check passed with:
  - `py -3 -m py_compile m:\Projects\repost-bot\reposts-bot\database.py`
  - `py -3 -m py_compile m:\Projects\repost-bot\reposts-bot\bot.py`

### Notes
- Recommended follow-up: call `await database.close_db()` during bot shutdown for clean connection teardown.