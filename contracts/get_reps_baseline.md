# Tool Contract: `get_reps_baseline`

> **Mirrored contract.** The normative source lives in the okareo-mcp-dev repo
> (`specs/033-serve-reps-baseline/contracts/get_reps_baseline.md`); this copy ships with the
> plugin so the reps skills and server stay reviewable side-by-side. Update it by re-copying,
> not by editing here.

**Feature**: 033-serve-reps-baseline | **Status**: v1 (envelope is stable and additive-only from this version)

One MCP tool serving the REPS baseline (`reps/` tree of the latest tagged okareo-ai/okareo-tools GitHub Release). Read-only, tenant-invariant, idempotent between releases.

## Registration

- **Name**: `get_reps_baseline`
- **Title**: `Get REPS Baseline Material`
- **Annotations**: `readOnlyHint=true, destructiveHint=false, idempotentHint=true, openWorldHint=true`
- **Return type**: `str` (JSON), matching every other tool in this server.

## Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `pillar` | `string` | no | Filter discovery to one area: `R-reasoning`, `E-execution`, `P-performance`, `S-security`, `explore`, `profile`. Ignored when `path` is provided. |
| `path` | `string` | no | Tree-relative file path (as returned by discovery, e.g. `S-security/scenarios/verification-gate.jsonl`). Provide to fetch content; omit for discovery. |
| `version` | `string` | no | Release tag the caller wants (e.g. `v0.5.1`). v1 honors only the currently served tag; any other value → `version_not_available`. Present from day one so pinning later is a capability change, not a contract change. |

## Envelope invariants (all responses)

These fields appear on every success response and, where meaningful, on errors. **v1 fields are never removed or re-typed; future fields are additive.**

| Field | Type | Meaning |
|-------|------|---------|
| `tag` | `string` | Release tag the content was served from (provenance — record in reports). |
| `fetched_at` | `string` (ISO-8601 UTC) | When the serving snapshot was last confirmed against GitHub. |
| `stale` | `boolean` | `true` when the last refresh attempt failed and content may lag the newest release. |
| `stale_reason` | `string` | Present only when `stale=true` (e.g. `"github_unreachable"`). |
| `pin` | `boolean` | `true` when an operator pin (`OKAREO_REPS_PINNED_TAG`) selected the tag. |
| `mode` | `string` | `"discovery"` or `"fetch"`. |

## Discovery mode (`path` omitted)

```json
{
  "mode": "discovery",
  "tag": "v0.5.1",
  "fetched_at": "2026-07-25T17:00:00Z",
  "stale": false,
  "pin": false,
  "pillar": "S-security",
  "pillars": ["R-reasoning", "E-execution", "P-performance", "S-security", "explore", "profile"],
  "files": [
    {"path": "S-security/coverage.json", "size": 1834, "pillar": "S-security"},
    {"path": "S-security/scenarios/verification-gate.jsonl", "size": 9120, "pillar": "S-security"},
    {"path": "S-security/scenarios/verification-gate_meta.md", "size": 2044, "pillar": "S-security"}
  ],
  "count": 3
}
```

- `pillar` (echo) is `null` when no filter was given; `files` then covers the entire tree, including locations outside the six ids (e.g. `shared/...`, `README.md`).
- `files[].pillar` is `null` for such locations. `files[].oversize: true` (additive) marks entries whose content cannot be fetched.
- File lists change freely between releases — callers MUST NOT assume any path exists without discovering it.

## Fetch mode (`path` provided)

```json
{
  "mode": "fetch",
  "tag": "v0.5.1",
  "fetched_at": "2026-07-25T17:00:00Z",
  "stale": false,
  "pin": false,
  "path": "S-security/scenarios/verification-gate.jsonl",
  "size": 9120,
  "content": "{\"input\": ...}\n{\"input\": ...}\n"
}
```

- `content` is the exact UTF-8 text of the file as published in the tagged release (byte-identical once encoded).

## Errors

Errors are JSON with a closed v1 code set; `tag`/`stale` are included whenever a serving snapshot exists. Callers branch on `error.code`, never on message text.

| Code | When | Extra context fields |
|------|------|----------------------|
| `unknown_pillar` | `pillar` not in the recognized set | `valid_pillars` |
| `unknown_path` | `path` not in the served release's manifest (incl. traversal attempts) | `suggestion` (re-run discovery) |
| `version_not_available` | `version` differs from the served tag | `available_versions` (list; v1: the single served tag) |
| `baseline_unavailable` | No snapshot exists and the source is unreachable (or airgap mode) | `detail` |
| `file_not_servable` | Manifest entry exists but content can't be served (oversize / non-UTF-8) | `path` |
| `invalid_request` | Parameter shape errors not covered above | `detail` |

Example:

```json
{
  "error": {
    "code": "version_not_available",
    "message": "Version 'v0.4.0' is not available. This server currently serves v0.5.1.",
    "available_versions": ["v0.5.1"]
  },
  "tag": "v0.5.1",
  "stale": false
}
```

## Behavioral guarantees

1. **Latest-release semantics**: content comes from the newest tagged GitHub Release, picked up within `OKAREO_REPS_REFRESH_SECONDS` (default 900s; hard bound 3600s) with no deploy.
2. **Never main-branch**: only release tarballs are fetched; there is no code path that reads a branch.
3. **Fallback**: if GitHub is unreachable, the last snapshot is served with `stale: true`; with no snapshot, `baseline_unavailable`.
4. **Consistency**: a single response is always served from one atomic snapshot. Across responses, compare `tag` to detect a release rollover mid-workflow.
5. **Auth**: identical to other read-only tools — server-level verifier in HTTP mode, none in stdio. Content is tenant-invariant.
