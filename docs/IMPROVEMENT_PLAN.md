# Onshape MCP Improvement Plan — Arbitrary Shape Modeling

## Problem Statement

The current MCP server only supports axis-aligned rectangular extrusions, circles, arcs, and basic lines on 3 standard planes. This limits geometry to Minecraft-style blocky assemblies. The goal is to enable agents to create **organic, low-poly mesh-like models** — such as a faceted polygonal cat — entirely through parametric Onshape features.

### Root Causes

| Gap | Why it blocks organic shapes |
|-----|------------------------------|
| No spline/interpolated curves | Can't create smooth or arbitrary 2D profiles |
| Only 3 sketch planes (Front/Top/Right) | Can't sketch at angles — all geometry is axis-aligned |
| No loft | Can't smoothly connect profiles across sections |
| No sweep | Can't extrude along a curved path |
| Polygon builder exists but not exposed as MCP tool | Agent can't create triangular/pentagonal profiles |
| No sketch-on-face | Can't reference existing geometry for progressive refinement |
| No polyline (multi-segment path) tool | Agent must call `create_sketch_line` N times for each edge |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Tool Layer (server.py)                 │
│  @app.list_tools() / @app.call_tool()                          │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────────┐│
│  │sketch tools  │ │feature tools │ │ NEW: loft, sweep, cPlane ││
│  └──────┬──────┘ └──────┬───────┘ └─────────────┬─────────────┘│
├─────────┼───────────────┼───────────────────────┼──────────────┤
│         ▼               ▼                       ▼              │
│              Builder Layer (builders/*.py)                      │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────────┐│
│  │SketchBuilder│ │ExtrudeBuilder│ │ NEW: LoftBuilder,         ││
│  │+ spline     │ │              │ │ SweepBuilder, PlaneBuilder││
│  │+ polyline   │ │              │ │                           ││
│  └──────┬──────┘ └──────┬───────┘ └─────────────┬─────────────┘│
├─────────┼───────────────┼───────────────────────┼──────────────┤
│         ▼               ▼                       ▼              │
│            API Layer (api/*.py — OnshapeClient)                 │
│  POST /api/v9/partstudios/.../features                         │
│  POST /api/v8/partstudios/.../featurescript                    │
└────────────────────────────────────────────────────────────────┘
```

All new features follow the **same pattern** as existing ones:
1. **Builder class** — constructs the `BTFeatureDefinitionCall-1406` JSON payload
2. **MCP tool definition** — schema + handler in `server.py`
3. **Tests** — unit tests for the builder

---

## Phase 1 — Quick Wins: Sketch Primitives (expose existing + add new)

These extend `SketchBuilder` and expose new MCP tools. Low risk, high value.

### 1.1 Expose `create_sketch_polygon` MCP tool

**Status**: Builder method `add_polygon()` already exists ([sketch.py line 594](onshape_mcp/builders/sketch.py#L594)), just not wired as an MCP tool.

**Tool definition**:
```python
Tool(
    name="create_sketch_polygon",
    description="Create a regular polygon sketch (triangle, hexagon, etc.)",
    inputSchema={
        "documentId": str, "workspaceId": str, "elementId": str,
        "name": str,
        "plane": {"enum": ["Front", "Top", "Right"]},
        "center": [x, y],     # inches
        "sides": int,          # >= 3
        "radius": float,       # circumscribed radius, inches
    }
)
```

**Files**: `server.py` (add tool + handler)

### 1.2 Add `create_sketch_polyline` — arbitrary closed/open polyline

A polyline is the most important missing primitive for low-poly modeling. The agent provides an ordered list of 2D vertices; the builder creates N line segments connecting them.

**Builder method** `SketchBuilder.add_polyline()`:
```python
def add_polyline(
    self, 
    points: List[Tuple[float, float]],   # [(x1,y1), (x2,y2), ...]  in inches
    closed: bool = True,                  # close the loop?
    is_construction: bool = False,
) -> "SketchBuilder":
```
Internally calls `add_line()` for each consecutive pair (and wraps back to start if `closed=True`). Adds `COINCIDENT` constraints between consecutive endpoints to ensure a connected profile.

**Tool definition**:
```python
Tool(
    name="create_sketch_polyline",
    description="Create a polyline (connected line segments) from an ordered list of points. Use closed=true for filled profiles.",
    inputSchema={
        "documentId": str, "workspaceId": str, "elementId": str,
        "name": str,
        "plane": {"enum": ["Front", "Top", "Right"]},
        "points": [[x1,y1], [x2,y2], ...],  # array of [x,y] in inches
        "closed": bool,   # default true
    }
)
```

**Files**: `builders/sketch.py` (add method), `server.py` (add tool + handler)

### 1.3 Add `create_sketch_spline` — interpolated spline curve

Uses `BTCurveGeometryInterpolatedSpline-116` to create a smooth curve through fit points.

**Builder method** `SketchBuilder.add_spline()`:
```python
def add_spline(
    self,
    points: List[Tuple[float, float]],         # fit points in inches
    is_periodic: bool = False,                  # closed spline?
    start_derivative: Optional[Tuple[float, float]] = None,
    end_derivative: Optional[Tuple[float, float]] = None,
    is_construction: bool = False,
) -> "SketchBuilder":
```
Builds a `BTMSketchCurveSegment-155` with geometry:
```json
{
  "btType": "BTCurveGeometryInterpolatedSpline-116",
  "isPeriodic": false,
  "interpolationPoints": [x1_m, y1_m, x2_m, y2_m, ...],
  "startDerivativeX": ..., "startDerivativeY": ...,
  "endDerivativeX": ..., "endDerivativeY": ...
}
```

**Tool definition**:
```python
Tool(
    name="create_sketch_spline",
    description="Create a smooth spline curve through a series of fit points",
    inputSchema={
        "documentId": str, "workspaceId": str, "elementId": str,
        "name": str,
        "plane": {"enum": ["Front", "Top", "Right"]},
        "points": [[x1,y1], [x2,y2], ...],
        "isPeriodic": bool,
        "startDerivative": [dx, dy],  # optional
        "endDerivative": [dx, dy],    # optional
    }
)
```

**Files**: `builders/sketch.py`, `server.py`

### 1.4 Add `create_sketch_bspline` — B-spline with control points

Uses `BTCurveGeometrySpline-118` for precise NURBS curves.

**Builder method** `SketchBuilder.add_bspline()`:
```python
def add_bspline(
    self,
    control_points: List[Tuple[float, float]],  # control points in inches
    degree: int = 3,
    is_periodic: bool = False,
    is_rational: bool = False,
    knots: Optional[List[float]] = None,         # auto-generated if None
    weights: Optional[List[float]] = None,        # for rational B-splines
    is_construction: bool = False,
) -> "SketchBuilder":
```

**Files**: `builders/sketch.py`, `server.py`

---

## Phase 2 — Construction Planes (unlock arbitrary angles)

This is the **most critical phase** for organic geometry. Without custom planes, all features are locked to axis-aligned orientations.

### 2.1 Add `create_construction_plane` — offset plane

Uses `featureType: "cPlane"` with `CPlaneType.OFFSET`.

**Builder class** `PlaneBuilder` in new file `builders/plane.py`:
```python
class PlaneType(Enum):
    OFFSET = "OFFSET"
    LINE_ANGLE = "LINE_ANGLE"
    THREE_POINT = "THREE_POINT"
    PLANE_POINT = "PLANE_POINT"
    MID_PLANE = "MID_PLANE"

class PlaneBuilder:
    def __init__(self, name: str = "Plane"):
        self.name = name
        self.parameters = []

    def offset_from_plane(
        self,
        base_plane_id: str,     # "JCC", "JDC", "JEC" or feature-created plane
        offset_distance: float,  # inches, converted to expression
        flip: bool = False,
    ) -> "PlaneBuilder": ...

    def through_three_points(
        self,
        point1_query: str,
        point2_query: str,
        point3_query: str,
    ) -> "PlaneBuilder": ...

    def line_angle(
        self,
        line_query: str,
        angle_degrees: float,
    ) -> "PlaneBuilder": ...

    def build(self) -> Dict[str, Any]:
        return {
            "feature": {
                "btType": "BTMFeature-134",
                "featureType": "cPlane",
                "name": self.name,
                "parameters": self.parameters,
            },
            "btType": "BTFeatureDefinitionCall-1406",
        }
```

**Tool definition**:
```python
Tool(
    name="create_construction_plane",
    description="Create a construction plane (offset from existing plane, through three points, or at angle to line)",
    inputSchema={
        "documentId": str, "workspaceId": str, "elementId": str,
        "name": str,
        "type": {"enum": ["offset", "three_point", "line_angle"]},
        # For offset:
        "basePlane": str,       # "Front"/"Top"/"Right" or plane feature ID
        "offsetDistance": float, # inches
        "flip": bool,
        # For three_point: point queries
        # For line_angle: line query + angle
    }
)
```

### 2.2 Extend `SketchBuilder` to support custom planes

Modify `SketchBuilder.__init__()` and `build()` to accept either:
- A standard plane name → resolved to `"JCC"` / `"JDC"` / `"JEC"`
- A custom plane feature ID → referenced via `deterministicIds`

This is already partially implemented via `plane_id` parameter — just needs wiring in the MCP tool handlers to accept a `planFeatureId` parameter as an alternative to `plane`.

### 2.3 Add `get_feature_id` helper tool

After creating a construction plane (or any feature), the agent needs its deterministic ID to reference it as a sketch plane. Expose a tool that:
1. Lists features via `GET .../features`
2. Finds the feature by name
3. Returns its `featureId` and any deterministic IDs

This is partially covered by `get_features` but needs a focused helper.

---

## Phase 3 — Loft (connect cross-section profiles)

Loft is the critical 3D operation for organic shapes. It smoothly connects 2+ sketch profiles on different planes into a solid.

### 3.1 Add `create_loft` tool

**Builder class** `LoftBuilder` in new file `builders/loft.py`:
```python
class LoftBuilder:
    def __init__(self, name: str = "Loft"):
        self.name = name
        self.profiles: List[str] = []  # sketch feature IDs
        self.operation_type = "NEW"
        self.body_type = "SOLID"

    def add_profile(self, sketch_feature_id: str) -> "LoftBuilder":
        """Add a sketch region as a loft profile (order matters)."""
        self.profiles.append(sketch_feature_id)
        return self

    def set_operation(self, op: str) -> "LoftBuilder":
        """NEW, ADD, REMOVE, INTERSECT"""
        self.operation_type = op
        return self

    def build(self) -> Dict[str, Any]:
        profile_items = []
        for fid in self.profiles:
            profile_items.append({
                "btType": "BTMArrayParameterItem-1843",
                "parameters": [{
                    "btType": "BTMParameterQueryList-148",
                    "parameterId": "profileQuery",
                    "queries": [{
                        "btType": "BTMIndividualSketchRegionQuery-140",
                        "featureId": fid,
                        "filterInnerLoops": False,
                    }],
                }],
            })

        return {
            "feature": {
                "btType": "BTMFeature-134",
                "featureType": "loft",
                "name": self.name,
                "parameters": [
                    {
                        "btType": "BTMParameterEnum-145",
                        "parameterId": "bodyType",
                        "value": self.body_type,
                        "enumName": "ToolBodyType",
                    },
                    {
                        "btType": "BTMParameterArray-2025",
                        "parameterId": "profileSubqueries",
                        "items": profile_items,
                    },
                    {
                        "btType": "BTMParameterEnum-145",
                        "parameterId": "operationType",
                        "value": self.operation_type,
                        "enumName": "NewBodyOperationType",
                    },
                ],
            },
            "btType": "BTFeatureDefinitionCall-1406",
        }
```

**Tool definition**:
```python
Tool(
    name="create_loft",
    description="Create a loft between 2+ sketch profiles on different planes. Profiles are connected in order to form a smooth solid.",
    inputSchema={
        "documentId": str, "workspaceId": str, "elementId": str,
        "name": str,
        "profileSketchIds": [str, str, ...],  # ordered list of sketch feature IDs
        "operationType": {"enum": ["NEW", "ADD", "REMOVE", "INTERSECT"]},
    }
)
```

### 3.2 Add guide curves support (optional, Phase 3b)

Loft guide curves constrain the shape between profiles. Would use sketch edges as guides.

---

## Phase 4 — Sweep (extrude along a path)

### 4.1 Add `create_sweep` tool

**Builder class** `SweepBuilder` in new file `builders/sweep.py`:
```python
class SweepBuilder:
    def __init__(self, name: str = "Sweep"):
        self.name = name
        self.profile_sketch_id: Optional[str] = None
        self.path_sketch_id: Optional[str] = None
        self.operation_type = "NEW"

    def set_profile(self, sketch_feature_id: str) -> "SweepBuilder":
        self.profile_sketch_id = sketch_feature_id
        return self

    def set_path(self, sketch_feature_id: str) -> "SweepBuilder":
        self.path_sketch_id = sketch_feature_id
        return self

    def build(self) -> Dict[str, Any]:
        return {
            "feature": {
                "btType": "BTMFeature-134",
                "featureType": "sweep",
                "name": self.name,
                "parameters": [
                    {
                        "btType": "BTMParameterQueryList-148",
                        "parameterId": "profiles",
                        "queries": [{
                            "btType": "BTMIndividualSketchRegionQuery-140",
                            "featureId": self.profile_sketch_id,
                            "filterInnerLoops": False,
                        }],
                    },
                    {
                        "btType": "BTMParameterQueryList-148",
                        "parameterId": "path",
                        "queries": [{
                            "btType": "BTMIndividualQuery-138",
                            "queryString": f'query = qCreatedBy(makeId("{self.path_sketch_id}"), EntityType.EDGE);',
                        }],
                    },
                    {
                        "btType": "BTMParameterEnum-145",
                        "parameterId": "bodyType",
                        "value": "SOLID",
                        "enumName": "ToolBodyType",
                    },
                    {
                        "btType": "BTMParameterEnum-145",
                        "parameterId": "operationType",
                        "value": self.operation_type,
                        "enumName": "NewBodyOperationType",
                    },
                ],
            },
            "btType": "BTFeatureDefinitionCall-1406",
        }
```

---

## Phase 5 — Sketch on Face (progressive refinement)

### 5.1 Research & implement face query resolution

When an agent creates an extrude, it produces faces. To sketch on those faces, we need their deterministic IDs. Two approaches:

**Approach A — FeatureScript query** (preferred):
```python
async def get_face_ids(self, doc_id, ws_id, elem_id, feature_id):
    """Return deterministic IDs for faces created by a feature."""
    script = f'''
    function(context is Context, queries is map) {{
        var faces = evaluateQuery(context, 
            qCreatedBy(makeId("{feature_id}"), EntityType.FACE));
        return faces;
    }}
    '''
    result = await self.client.post(
        f"/api/v8/partstudios/d/{doc_id}/w/{ws_id}/e/{elem_id}/featurescript",
        data={"script": script}
    )
    # Extract deterministic IDs from transient queries
    return [extract_det_id(face) for face in result]
```

**Approach B — Body details endpoint**:
```
GET /api/v9/partstudios/d/{did}/w/{wid}/e/{eid}/bodydetails
```
Returns face/edge topology with IDs.

### 5.2 Extend sketch plane parameter

Allow `sketchPlane` to reference a face deterministic ID instead of only `"JCC"` / `"JDC"` / `"JEC"`.

---

## Phase 6 — Composite High-Level Tools (agent ergonomics)

### 6.1 `create_lofted_shape` — all-in-one

A convenience tool that:
1. Creates N offset construction planes
2. Creates a sketch with a polyline profile on each plane
3. Lofts all profiles together

This dramatically reduces the number of MCP calls for an agent building organic geometry.

```python
Tool(
    name="create_lofted_shape",
    description="Create a solid by lofting through cross-section profiles at specified offsets along an axis. Each profile is a closed polyline. Ideal for organic/tapered shapes.",
    inputSchema={
        "documentId": str, "workspaceId": str, "elementId": str,
        "name": str,
        "axis": {"enum": ["X", "Y", "Z"]},
        "sections": [
            {
                "offset": float,        # distance along axis, in inches
                "points": [[x,y], ...]  # 2D profile vertices on the cross-section plane
            },
            ...
        ],
        "operationType": {"enum": ["NEW", "ADD", "REMOVE", "INTERSECT"]},
    }
)
```

**Why this matters**: To model a low-poly cat head, an agent would define 5-8 cross-sections at different Y-heights, each with a different polygon outline. One tool call replaces ~20 individual calls.

### 6.2 `create_sketch_multi` — batch multiple sketch entities

Allow creating multiple sketch entities (lines, arcs, splines, polylines) in a single sketch/tool call:

```python
Tool(
    name="create_sketch_multi",
    description="Create a sketch with multiple entities (lines, polylines, arcs, splines, circles) in one call",
    inputSchema={
        "documentId": str, "workspaceId": str, "elementId": str,
        "name": str,
        "plane": str,
        "entities": [
            {"type": "polyline", "points": [...], "closed": true},
            {"type": "circle", "center": [x,y], "radius": r},
            {"type": "spline", "points": [...], "isPeriodic": false},
            {"type": "line", "start": [x,y], "end": [x,y]},
        ]
    }
)
```

---

## Implementation Priority & Difficulty

| # | Feature | Impact | Difficulty | Dependencies |
|---|---------|--------|------------|--------------|
| 1.1 | `create_sketch_polygon` | Medium | **Trivial** | None — builder exists |
| 1.2 | `create_sketch_polyline` | **High** | Easy | None |
| 1.3 | `create_sketch_spline` | High | Medium | Needs testing of `BTCurveGeometryInterpolatedSpline-116` payload |
| 2.1 | `create_construction_plane` | **Critical** | Medium | Needs testing of `cPlane` feature payload |
| 2.2 | Custom plane sketch support | **Critical** | Easy | 2.1 |
| 3.1 | `create_loft` | **Critical** | Medium-Hard | 2.1 + loft payload verification |
| 4.1 | `create_sweep` | High | Medium | Similar to loft |
| 5.1 | Sketch on face | High | Hard | FeatureScript face query research |
| 6.1 | `create_lofted_shape` | **Very High** | Medium | 1.2 + 2.1 + 3.1 |
| 6.2 | `create_sketch_multi` | Medium | Easy | 1.2 + 1.3 |
| 1.4 | `create_sketch_bspline` | Medium | Medium | Needs knot vector validation |

### Recommended implementation order:

```
1.1 → 1.2 → 2.1 → 2.2 → 3.1 → 6.1 → 1.3 → 4.1 → 5.1 → 6.2 → 1.4
 ▲     ▲      ▲            ▲      ▲
 │     │      │            │      └── This is the "wow" moment: one-call organic shapes
 │     │      │            └── Loft connects profiles into smooth 3D solid
 │     │      └── Unlocks non-axis-aligned geometry
 │     └── Arbitrary closed profiles for loft sections
 └── Free win (already built)
```

---

## How a Low-Poly Cat Would Be Modeled

With the improvements above, here's how an agent would create a low-poly cat body:

### Strategy: Section Lofting

```
Side view:          Cross-sections (front view at each Y):
                    
    ╱╲  ears         Y=4": △ small triangle (ear tip)
   ╱  ╲             Y=3.5": ⬡ pentagon (head top)
  │    │ head        Y=3": ⬡ wider hexagon (head mid - eyes)
  │    │             Y=2.5": ⬡ hexagon (chin)
   ╲  ╱              Y=2": □ narrow rect (neck)
    ││  neck         Y=1": ⬡ wide hexagon (torso)
   ╱  ╲              Y=0.5": ⬡ hexagon (belly)
  │    │ body        Y=0": ⬡ smaller hexagon (base)
  └────┘
```

### Pseudocode using the new tools:

```python
# 1. Create document
doc = create_document(name="Low Poly Cat")

# 2. Body — lofted shape from cross-sections
create_lofted_shape(
    name="Cat Body",
    axis="Y",  # vertical
    sections=[
        {"offset": 0.0,  "points": hexagon(cx=0, cy=0, r=0.8)},   # base
        {"offset": 0.5,  "points": hexagon(cx=0, cy=0, r=1.2)},   # belly
        {"offset": 1.5,  "points": hexagon(cx=0, cy=0, r=1.0)},   # chest
        {"offset": 2.0,  "points": quad(cx=0, cy=0, w=0.5, h=0.5)}, # neck
    ],
    operationType="NEW"
)

# 3. Head — separate lofted shape
create_lofted_shape(
    name="Cat Head",
    axis="Y",
    sections=[
        {"offset": 2.0,  "points": pentagon(cx=0, cy=0, r=0.6)},  # neck junction
        {"offset": 2.5,  "points": hexagon(cx=0, cy=0, r=1.0)},   # chin
        {"offset": 3.0,  "points": octagon(cx=0, cy=0.1, r=1.1)}, # mid-face
        {"offset": 3.5,  "points": pentagon(cx=0, cy=0.2, r=0.9)}, # forehead
    ],
    operationType="ADD"
)

# 4. Ears — small triangular lofts
for ear_x in [-0.5, 0.5]:
    create_lofted_shape(
        name=f"Ear {'Left' if ear_x < 0 else 'Right'}",
        axis="Y",
        sections=[
            {"offset": 3.3, "points": triangle(cx=ear_x, cy=0.3, r=0.3)},
            {"offset": 4.0, "points": triangle(cx=ear_x, cy=0.4, r=0.05)}, # tip
        ],
        operationType="ADD"
    )

# 5. Tail — sweep a small polygon along a spline path
create_sketch_spline(name="Tail Path", plane="Right", 
    points=[[0, 0], [-0.5, -0.3], [-1.2, 0.2], [-1.5, 0.5]])
create_sketch_polygon(name="Tail Profile", plane="Front",
    center=[0, 0], sides=6, radius=0.15)
create_sweep(name="Tail", profileSketchId="...", pathSketchId="...")

# 6. Legs — extruded polygons
for pos in [(-0.4, -0.5), (0.4, -0.5), (-0.4, 0.4), (0.4, 0.4)]:
    create_sketch_polygon(name="Leg", plane="Top",
        center=pos, sides=6, radius=0.2)
    create_extrude(name="Leg", depth=1.0, operationType="ADD")

# 7. Apply facet-style chamfers to all edges
create_chamfer(edges="all_edges", distance=0.05)
```

The result: a recognizable **low-poly faceted cat** built entirely from parametric Onshape features, with section-lofted body, triangular ears, swept tail, and hexagonal legs — far beyond the current "rectangular prism" limitation.

---

## Technical Risks & Mitigations

| Risk | Probability | Mitigation |
|------|-------------|------------|
| Loft payload format wrong | Medium | Create a loft manually in Onshape UI, then GET features to capture exact JSON. Compare with our builder output. |
| cPlane parameter IDs wrong | Medium | Same approach: create offset plane in UI, capture JSON. |
| Spline `interpolationPoints` format unclear | Low | Test with simple 3-point spline first. The flat array format `[x1,y1,x2,y2,...]` is documented in the OpenAPI schema. |
| Cross-sketch region references don't resolve | Medium | Verify with FeatureScript `qSketchRegion()` queries. May need to also try `queryString`-based references. |
| Sketch on face requires opaque `qCompressed` queries | High | Use FeatureScript `evaluateQuery(qCreatedBy(...))` to discover face IDs. If that fails, use body details endpoint. |
| Performance — too many features for complex models | Low | The composite `create_lofted_shape` tool batches operations. Agents should minimize feature count by using lofts over individual extrudes. |

### API Payload Discovery Strategy

For any new feature type, the safest approach before coding:
1. Open Onshape UI → create the feature manually
2. Call `GET /api/v9/partstudios/d/{did}/w/{wid}/e/{eid}/features`
3. Inspect the JSON response for exact `parameterId`, `btType`, and `enumName` values
4. Build the Python builder to replicate that exact payload

---

## Testing Strategy

### Unit Tests (per builder)
- Each builder gets `test_<builder>_build()` verifying JSON structure
- Constraint and entity ID uniqueness tests
- Edge cases: degenerate polygons, zero-length lines, etc.

### Integration Tests (against Onshape API)
- Marked with `@pytest.mark.integration`
- Create a dedicated test document
- Verify feature creation + bounding box matches expectations
- Cleanup: delete test document after

### Visual Verification
- Extend `fetch_onshape_image.py` to support multi-angle rendering
- Agent uses PDCA loop from the skill to self-verify

---

## File Changes Summary

| File | Change |
|------|--------|
| `onshape_mcp/builders/sketch.py` | Add `add_polyline()`, `add_spline()`, `add_bspline()` methods |
| `onshape_mcp/builders/plane.py` | **New file** — `PlaneBuilder` class |
| `onshape_mcp/builders/loft.py` | **New file** — `LoftBuilder` class |
| `onshape_mcp/builders/sweep.py` | **New file** — `SweepBuilder` class |
| `onshape_mcp/builders/__init__.py` | Export new builders |
| `onshape_mcp/server.py` | Add ~8 new tool definitions + handlers |
| `onshape_mcp/api/partstudio.py` | Add `get_face_ids()` method for sketch-on-face |
| `tests/test_sketch_builder.py` | Tests for new sketch methods |
| `tests/test_plane_builder.py` | **New** — tests for PlaneBuilder |
| `tests/test_loft_builder.py` | **New** — tests for LoftBuilder |
| `tests/test_sweep_builder.py` | **New** — tests for SweepBuilder |
| `tests/test_server_new_tools.py` | **New** — integration tests for new tools |
