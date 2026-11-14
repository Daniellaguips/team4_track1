# Team 4 — Track 1: AI Task Factory

Click-based task generation and validation prototype for the Innodata Hackathon.

## Contents

- `track1_freestyle/`: implementation, five generated tasks, development candidates, demo task, validation evidence, run logs, and resource records.
- `track1_submission/`: the supplied submission folder and ZIP snapshot. `TeamName` remains a placeholder in these original artifacts.
- `organizer/`: Track 1 instructions, harness, worked example, general event brief, and presentation template. Track 2 materials are excluded.

## Current status

The developer report states that all five tasks passed Harbor oracle/nop self-checks and the organizer submission validator reported zero errors and warnings. These historical results have not been rerun during this GitHub import.

The generator uses five predefined feature blueprints with parameterized variations. It does not independently discover new feature families. No model benchmark has run, so task difficulty and resolve@k are unproven. Validation used rootless Podman; Docker execution and a cache-free image build remain unverified.

See [implementation instructions](track1_freestyle/README.md), [variation strategy](track1_freestyle/VARIATION_WRITEUP.md), and `track1_freestyle/evidence/` for details. Paths referring to the original Erdos machine may need adapting locally. The downloaded virtual environment and nested Git metadata are excluded; recreate dependencies from the requirements files.

## Download integrity issue

The supplied `track1_submission/TeamName_Track1.zip` is not a valid ZIP in this local download (786,432 bytes), so it is retained only as the received artifact, not a verified submission archive. Recreate it from the submission folder or transfer the original again before submitting.
