"""Construction plane builder for Onshape."""

from enum import Enum
from typing import Any, Dict, List, Optional


class PlaneType(Enum):
    """Construction plane creation types."""

    OFFSET = "OFFSET"
    LINE_ANGLE = "LINE_ANGLE"
    THREE_POINT = "THREE_POINT"
    PLANE_POINT = "PLANE_POINT"
    MID_PLANE = "MID_PLANE"
    CURVE_POINT = "CURVE_POINT"


# Standard plane deterministic IDs
STANDARD_PLANE_IDS = {
    "Front": "JCC",
    "Top": "JDC",
    "Right": "JEC",
}

# Standard plane feature names (used for queryString format)
STANDARD_PLANE_NAMES = {"JCC": "Front", "JDC": "Top", "JEC": "Right"}


def _make_plane_query(plane_ref: str) -> Dict[str, Any]:
    """Create the query object for referencing a plane.

    Uses queryString format (FeatureScript query) which is more reliable
    than deterministicIds for the cPlane feature.

    Args:
        plane_ref: Either a deterministic ID (JCC, JDC, JEC) for standard planes,
                  a standard plane name (Front, Top, Right),
                  or a construction plane feature ID.

    Returns:
        BTMIndividualQuery-138 dict with queryString.
    """
    # Resolve deterministic IDs to feature names
    feature_name = STANDARD_PLANE_NAMES.get(plane_ref)
    if feature_name is None:
        # Check if it's a standard plane name directly
        if plane_ref in STANDARD_PLANE_IDS:
            feature_name = plane_ref
        else:
            # It's a custom construction plane feature ID
            feature_name = plane_ref

    return {
        "btType": "BTMIndividualQuery-138",
        "queryString": f'query=qCreatedBy(makeId("{feature_name}"), EntityType.FACE);',
    }


class PlaneBuilder:
    """Builder for creating Onshape construction plane (cPlane) features.

    Construction planes enable sketching at arbitrary offsets and angles,
    which is essential for lofts and organic geometry.
    """

    def __init__(self, name: str = "Plane"):
        """Initialize plane builder.

        Args:
            name: Name of the construction plane feature.
        """
        self.name = name
        self.parameters: List[Dict[str, Any]] = []
        self._plane_type: Optional[PlaneType] = None

    def offset_from_plane(
        self,
        base_plane_id: str,
        offset_distance: float,
        flip: bool = False,
    ) -> "PlaneBuilder":
        """Create a plane offset from a standard or existing plane.

        Args:
            base_plane_id: Deterministic ID or feature name of the base plane
                          (e.g., "JCC"/"Front", "JDC"/"Top", "JEC"/"Right",
                           or a construction plane feature ID).
            offset_distance: Offset distance in inches.
            flip: Whether to offset in the opposite direction.

        Returns:
            Self for chaining.
        """
        self._plane_type = PlaneType.OFFSET

        self.parameters = [
            {
                "btType": "BTMParameterEnum-145",
                "parameterId": "cPlaneType",
                "value": "OFFSET",
                "enumName": "CPlaneType",
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "plane",
                "queries": [_make_plane_query(base_plane_id)],
            },
            {
                "btType": "BTMParameterQuantity-147",
                "parameterId": "offset",
                "expression": f"{offset_distance} in",
                "isInteger": False,
            },
            {
                "btType": "BTMParameterBoolean-144",
                "parameterId": "oppositeDirection",
                "value": flip,
            },
        ]

        return self

    def line_angle(
        self,
        line_ref: str,
        angle_degrees: float,
    ) -> "PlaneBuilder":
        """Create a plane through a line at a given angle.

        Args:
            line_ref: Reference to the edge/line (feature ID or deterministic ID).
            angle_degrees: Rotation angle in degrees.

        Returns:
            Self for chaining.
        """
        self._plane_type = PlaneType.LINE_ANGLE

        # Lines use EntityType.EDGE
        line_query = {
            "btType": "BTMIndividualQuery-138",
            "queryString": f'query=qCreatedBy(makeId("{line_ref}"), EntityType.EDGE);',
        }

        self.parameters = [
            {
                "btType": "BTMParameterEnum-145",
                "parameterId": "cPlaneType",
                "value": "LINE_ANGLE",
                "enumName": "CPlaneType",
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "line",
                "queries": [line_query],
            },
            {
                "btType": "BTMParameterQuantity-147",
                "parameterId": "angle",
                "expression": f"{angle_degrees} deg",
                "isInteger": False,
            },
        ]

        return self

    def three_point(
        self,
        point1_ref: str,
        point2_ref: str,
        point3_ref: str,
    ) -> "PlaneBuilder":
        """Create a plane through three points.

        Args:
            point1_ref: Reference to first point/vertex (feature ID).
            point2_ref: Reference to second point/vertex (feature ID).
            point3_ref: Reference to third point/vertex (feature ID).

        Returns:
            Self for chaining.
        """
        self._plane_type = PlaneType.THREE_POINT

        def _make_vertex_query(ref: str) -> Dict[str, Any]:
            return {
                "btType": "BTMIndividualQuery-138",
                "queryString": f'query=qCreatedBy(makeId("{ref}"), EntityType.VERTEX);',
            }

        self.parameters = [
            {
                "btType": "BTMParameterEnum-145",
                "parameterId": "cPlaneType",
                "value": "THREE_POINT",
                "enumName": "CPlaneType",
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "point1",
                "queries": [_make_vertex_query(point1_ref)],
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "point2",
                "queries": [_make_vertex_query(point2_ref)],
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "point3",
                "queries": [_make_vertex_query(point3_ref)],
            },
        ]

        return self

    def mid_plane(
        self,
        plane1_ref: str,
        plane2_ref: str,
    ) -> "PlaneBuilder":
        """Create a midplane between two planes or faces.

        Args:
            plane1_ref: Reference to first plane/face (deterministic ID, name, or feature ID).
            plane2_ref: Reference to second plane/face (deterministic ID, name, or feature ID).

        Returns:
            Self for chaining.
        """
        self._plane_type = PlaneType.MID_PLANE

        self.parameters = [
            {
                "btType": "BTMParameterEnum-145",
                "parameterId": "cPlaneType",
                "value": "MID_PLANE",
                "enumName": "CPlaneType",
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "tool1",
                "queries": [_make_plane_query(plane1_ref)],
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "tool2",
                "queries": [_make_plane_query(plane2_ref)],
            },
        ]

        return self

    def build(self) -> Dict[str, Any]:
        """Build the construction plane feature JSON.

        Returns:
            Feature definition for Onshape API.

        Raises:
            ValueError: If no plane type has been configured.
        """
        if self._plane_type is None:
            raise ValueError(
                "Plane type must be set before building. "
                "Call offset_from_plane(), three_point(), line_angle(), or mid_plane()."
            )

        return {
            "feature": {
                "btType": "BTMFeature-134",
                "featureType": "cPlane",
                "name": self.name,
                "suppressed": False,
                "parameters": self.parameters,
            },
        }
