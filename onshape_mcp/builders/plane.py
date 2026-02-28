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
            base_plane_id: Deterministic ID of the base plane
                          (e.g., "JCC" for Front, "JDC" for Top, "JEC" for Right,
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
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "deterministicIds": [base_plane_id],
                    }
                ],
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
        line_deterministic_id: str,
        angle_degrees: float,
    ) -> "PlaneBuilder":
        """Create a plane through a line at a given angle.

        Args:
            line_deterministic_id: Deterministic ID of the edge/line.
            angle_degrees: Rotation angle in degrees.

        Returns:
            Self for chaining.
        """
        self._plane_type = PlaneType.LINE_ANGLE

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
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "deterministicIds": [line_deterministic_id],
                    }
                ],
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
        point1_id: str,
        point2_id: str,
        point3_id: str,
    ) -> "PlaneBuilder":
        """Create a plane through three points.

        Args:
            point1_id: Deterministic ID of first point/vertex.
            point2_id: Deterministic ID of second point/vertex.
            point3_id: Deterministic ID of third point/vertex.

        Returns:
            Self for chaining.
        """
        self._plane_type = PlaneType.THREE_POINT

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
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "deterministicIds": [point1_id],
                    }
                ],
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "point2",
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "deterministicIds": [point2_id],
                    }
                ],
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "point3",
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "deterministicIds": [point3_id],
                    }
                ],
            },
        ]

        return self

    def mid_plane(
        self,
        plane1_id: str,
        plane2_id: str,
    ) -> "PlaneBuilder":
        """Create a midplane between two planes or faces.

        Args:
            plane1_id: Deterministic ID of first plane/face.
            plane2_id: Deterministic ID of second plane/face.

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
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "deterministicIds": [plane1_id],
                    }
                ],
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "tool2",
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "deterministicIds": [plane2_id],
                    }
                ],
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
            "btType": "BTFeatureDefinitionCall-1406",
            "feature": {
                "btType": "BTMFeature-134",
                "featureType": "cPlane",
                "name": self.name,
                "suppressed": False,
                "parameters": self.parameters,
            },
        }
