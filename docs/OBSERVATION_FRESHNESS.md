# Observation and writer recovery
Agent work records are deduplicated by observation ID. Conflicting duplicates are rejected.
Malformed nonobjects are counted as rejected. Successful old observations become stale
after three hours by default, rather than healthy. Reports include freshness.
The state exporter uses an OS-held writer lock; a crashed process releases ownership.
The lock file deliberately remains on disk. Concurrent writers are rejected.
These states describe observations and process health, not settlement or economic finality.
Regression tests cover duplicate records, stale success, malformed JSON values, an active
concurrent writer and recovery after termination of the lock-holding test process.
