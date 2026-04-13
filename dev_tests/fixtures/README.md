# Test fixtures

## `sample.apex` (optional but recommended)

Pipeline and extraction regression tests need a **real** RTI `.apex` file (SQLite). To run them locally or in CI:

1. Copy any valid `.apex` from your environment to:

   `dev_tests/fixtures/sample.apex`

2. Or set an absolute path:

   `SENTINEL_TEST_APEX=/path/to/project.apex`

If neither is present, those tests **skip** so `unittest discover` still passes (useful for CI without binary assets).
