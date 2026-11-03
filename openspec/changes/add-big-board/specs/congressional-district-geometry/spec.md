# Spec Delta

## Purpose

Provide map shapes for every 2026 House district and every state, keyed to baseline race keys and ready to draw, on the lines in use on November 3, 2026 wherever an enacted plan is available, and clearly flagged where they are not.

## ADDED Requirements

### Requirement: One shape per race

The district shapes SHALL contain exactly one shape per baseline House race, identified by its race key, and the state shapes one per state plus D.C., identified by postal code. Every Senate and governor race key SHALL resolve to its state's shape. Puerto Rico SHALL be excluded. D.C.'s delegate seat SHALL be kept as a shape with no race.

#### Scenario: Complete coverage
- **WHEN** the shapes are built
- **THEN** there are 435 district shapes whose keys equal the baseline House race keys, including `AK-AL` and `VT-AL`, plus a D.C. shape with no race and no Puerto Rico shape

### Requirement: States built from their districts

Each state shape SHALL be the union of that state's district shapes after simplification, so state and district borders coincide exactly. No separate state boundary source SHALL be used.

#### Scenario: Shared borders
- **WHEN** a state outline and its districts are drawn together
- **THEN** the state outline lies exactly on its outer district edges with no gaps or slivers

### Requirement: 2026 lines where enacted plans are available

Districts SHALL come from the Census 119th Congress cartographic boundaries, except that a state listed in the boundary vintage registry SHALL use its 2026 enacted plan when the source manifest has one. Each district SHALL record its boundary vintage: `current`, `plan_2026`, or `prior_boundaries`.

#### Scenario: Redrawn state with an enacted plan
- **WHEN** Texas is in the registry and the manifest has its 2025 enacted plan
- **THEN** Texas districts come from that plan and have vintage `plan_2026`

### Requirement: Redrawn states without a plan are flagged, not dropped

A registry state with no enacted plan in the manifest SHALL be built from its 119th Congress districts with vintage `prior_boundaries`, and the build SHALL list each such state in its output and report without failing.

#### Scenario: Plan not yet sourced
- **WHEN** Louisiana is in the registry and the manifest has no Louisiana plan
- **THEN** Louisiana's districts are drawn on 2024 lines with vintage `prior_boundaries`, and the build reports Louisiana as on prior lines

### Requirement: Recorded and verified sources

Each source file SHALL be recorded in a committed manifest with its URL, plan name, retrieval date, and SHA-256. A source whose hash differs from the manifest SHALL fail the build without replacing outputs. Rebuilding from unchanged sources SHALL produce byte-identical output.

#### Scenario: Changed source file
- **WHEN** a saved source file's hash differs from the manifest
- **THEN** the build fails naming the file and keeps previous outputs

### Requirement: Draw-ready output for the page

The output SHALL be one JSON document of SVG path strings already projected into a 960 by 600 frame, with Alaska and Hawaii placed below the lower 48. It SHALL include each state's bounding box and each district's center point for zooming and labels, and SHALL be at most 400 KB.

#### Scenario: Size and frame check
- **WHEN** the shapes are built
- **THEN** every path and center point lies within the 960 by 600 frame, and the build reports the output size and fails above 400 KB
