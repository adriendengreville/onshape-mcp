"""Sweep feature builder for Onshape."""

from enum import Enum
from typing import Any, Dict, List, Optional


class SweepType(Enum):
    """Sweep operation type."""

    NEW = "NEW"
    ADD = "ADD"
    REMOVE = "REMOVE"
    INTERSECT = "INTERSECT"


class SweepBuilder:
    """Builder for creating Onshape sweep features.

    A sweep extrudes a profile sketch along a path sketch to create
    tubes, curved shapes, and other path-following geometry.
    """

    def __init__(
        self,
        name: str = "Sweep",
        operation_type: SweepType = SweepType.NEW,
    ):
        """Initialize sweep builder.

        Args:
            name: Name of the sweep feature.
            operation_type: Type of sweep operation.
        """
        self.name = name
        self.operation_type = operation_type
        self.profile_sketch_id: Optional[str] = None
        self.path_sketch_id: Optional[str] = None
        self.body_type = "SOLID"
        self.keep_profile_orientation = False

    def set_profile(self, sketch_feature_id: str) -> "SweepBuilder":
        """Set the profile sketch (cross-section to sweep).

        Args:
            sketch_feature_id: Feature ID of the profile sketch
                              (must be a closed profile for solid sweeps).

        Returns:
            Self for chaining.
        """
        self.profile_sketch_id = sketch_feature_id
        return self

    def set_path(self, sketch_feature_id: str) -> "SweepBuilder":
        """Set the path sketch (curve to sweep along).

        Args:
            sketch_feature_id: Feature ID of the path sketch
                              (connected edges forming a continuous path).

        Returns:
            Self for chaining.
        """
        self.path_sketch_id = sketch_feature_id
        return self

    def set_operation(self, operation_type: SweepType) -> "SweepBuilder":
        """Set the sweep operation type.

        Args:
            operation_type: NEW, ADD, REMOVE, or INTERSECT.

        Returns:
            Self for chaining.
        """
        self.operation_type = operation_type
        return self

    def set_body_type(self, body_type: str) -> "SweepBuilder":
        """Set body type (SOLID or SURFACE).

        Args:
            body_type: "SOLID" or "SURFACE".

        Returns:
            Self for chaining.
        """
        self.body_type = body_type
        return self

    def set_keep_profile_orientation(self, keep: bool = True) -> "SweepBuilder":
        """Whether to keep the profile orientation constant along the path.

        Args:
            keep: True to maintain profile orientation.

        Returns:
            Self for chaining.
        """
        self.keep_profile_orientation = keep
        return self

    def build(self) -> Dict[str, Any]:
        """Build the sweep feature JSON.

        Returns:
            Feature definition for Onshape API.

        Raises:
            ValueError: If profile or path sketch is not set.
        """
        if not self.profile_sketch_id:
            raise ValueError("Profile sketch must be set before building sweep")
        if not self.path_sketch_id:
            raise ValueError("Path sketch must be set before building sweep")

        parameters: List[Dict[str, Any]] = [
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "profiles",
                "queries": [
                    {
                        "btType": "BTMIndividualSketchRegionQuery-140",
                        "featureId": self.profile_sketch_id,
                        "filterInnerLoops": False,
                    }
                ],
            },
            {
                "btType": "BTMParameterQueryList-148",
                "parameterId": "path",
                "queries": [
                    {
                        "btType": "BTMIndividualQuery-138",
                        "queryString": (
                            f'query = qCreatedBy(makeId("{self.path_sketch_id}"), '
                            f"EntityType.EDGE);"
                        ),
                    }
                ],
            },
            {
                "btType": "BTMParameterEnum-145",
                "parameterId": "bodyType",
                "value": self.body_type,
                "enumName": "ToolBodyType",
            },
            {
                "btType": "BTMParameterEnum-145",
                "parameterId": "operationType",
                "value": self.operation_type.value,
                "enumName": "NewBodyOperationType",
            },
        ]

        if self.keep_profile_orientation:
            parameters.append(
                {
                    "btType": "BTMParameterEnum-145",
                    "parameterId": "profileControl",
                    "value": "KEEP_ORIENTATION",
                    "enumName": "ProfileControlMode",
                }
            )

        return {
            "btType": "BTFeatureDefinitionCall-1406",
            "feature": {
                "btType": "BTMFeature-134",
                "featureType": "sweep",
                "name": self.name,
                "suppressed": False,
                "parameters": parameters,
            },
        }
