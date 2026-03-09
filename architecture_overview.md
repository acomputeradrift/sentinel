# Architecture Overview

## System Summary
<<<EXAMPLE OPTIONS:
1. Unidirectional pipeline from capture → analysis → presentation.
2. Diagnostics-in, explanations-out, no control loop.
3. Layered system with strict trust boundaries.
>>>

## Trust Boundaries
<<<EXAMPLE OPTIONS:
1. All incoming diagnostics are untrusted.
2. Uploaded files are authoritative but untrusted.
3. Output must never reinterpret or mutate source data.
>>>

## Forbidden Patterns
<<<EXAMPLE OPTIONS:
1. Bidirectional control paths.
2. Silent normalization of data.
3. Hidden state affecting output.
>>>

---
