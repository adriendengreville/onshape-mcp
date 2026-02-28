"""Loft feature builder for Onshape."""

from enum import Enum
from typing import Any, Dict, List, Optional


class LoftType(Enum):
    """Loft operation type."""

    NEW = "NEW"
    ADD = "ADD"
    REMOVE = "REMOVE"
    INTERSECT = "INTERSECT"


class LoftBuilder:
    """Builder for creating Onshape loft features.

    A loft connects 2+ sketch profiles on different planes into a smooth solid.
    Profiles are connected in the order they are added.
    """

    def __init__(
        self,
        name: str = "Loft",
        operation_type: LoftType = LoftType.NEW,
    ):
        """Initialize loft builder.

        Args:
            name: Name of the loft feature.
            operation_type: Type of loft operation.
        """
        self.name = name
        self.operation_type = operation_type
        self.profiles: List[str] = []
        self.guides: List[str] = []
        self.body_type = "SOLID"

    def add_profile(self, sketch_feature_id: str) -> "LoftBuilder":
        """Add a sketch region as a loft profile.

        Profiles are connected in the order they are added. Each profile
        should be a closed sketch on a separate plane.

        Args:
            sketch_feature_id: Feature ID of the sketch containing the profile.

        Returns:
            Self for chaining.
        """
        self.profiles.append(sketch_feature_id)
        return self

    def add_guide(self, sketch_feature_id: str) -> "LoftBuilder":
        """Add a guide curve to constrain the loft shape.

        Guide curves control how the loft transitions between profiles.

        Args:
            sketch_feature_id: Feature ID of the sketch containing the guide curve.

        Returns:
            Self for chaining.
        """
        self.guides.append(sketch_feature_id)
        return self

    def set_operation(self, operation_type: LoftType) -> "LoftBuilder":
        """Set the loft operation type.

        Args:
            operation_type: NEW, ADD, REMOVE, or INTERSECT.

        Returns:
            Self for chaining.
        """
        self.operation_type = operation_type
        return self

    def set_body_type(self, body_type: str) -> "LoftBuilder":
        """Set the body type (SOLID or SURFACE).

        Args:
            body_type: "SOLID" or "SURFACE".

        Returns:
            Self for chaining.
        """
        self.body_type = body_type
        return self

    def build(self) -> Dict[str, Any]:
        """Build the loft feature JSON.

        Returns:
            Feature definition for Onshape API.

        Raises:
            ValueError: If fewer than 2 profiles are provided.
        """
        if len(self.profiles) < 2:
            raise ValueError(
                f"Loft requires at least 2 profiles, got {len(self.profiles)}"
            )

        # Build profile array items
        profile_items = []
        for fid in self.profiles:
            profile_items.append(
                {
                    "btType": "BTMArrayParameterItem-1843",
                    "parameters": [
                        {
                            "btType": "BTMParameterQueryList-148",
                            "parameterId": "profileQuery",
                            "queries": [
                                {
                                    "btType": "BTMIndividualSketchRegionQuery-140",
                                    "featureId": fid,
                                    "filterInnerLoops": True,
                                    "queryStatement": None,
                                    "queryString": f'query = qSketchRegion(id + "{fid}", true);',
                                    "deterministicIds": [],
                                }
                            ],
                        }
                    ],
                }
            )

        parameters: List[Dict[str, Any]] = [
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
                "value": self.operation_type.value,
                "enumName": "NewBodyOperationType",
            },
        ]

        # Add guide curves if present
        if self.guides:
            guide_items = []
            for gid in self.guides:
                guide_items.append(
                    {
                        "btType": "BTMArrayParameterItem-1843",
                        "parameters": [
                            {
                                "btType": "BTMParameterQueryList-148",
                                "parameterId": "guideQuery",
                                "queries": [
                                    {
                                        "btType": "BTMIndividualQuery-138",
                                        "queryString": (
                                            f'query = qCreatedBy(makeId("{gid}"), '
                                            f"EntityType.EDGE);"
                                        ),
                                    }
                                ],
                            }
                        ],
                    }
                )

            parameters.append(
                {
                    "btType": "BTMParameterArray-2025",
                    "parameterId": "guideSubqueries",
                    "items": guide_items,
                }
            )

        return {
            "btType": "BTFeatureDefinitionCall-1406",
            "feature": {
                "btType": "BTMFeature-134",
                "featureType": "loft",
                "name": self.name,
                "suppressed": False,
                "parameters": parameters,
            },
        }
