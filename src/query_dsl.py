#!/usr/bin/env python3
"""
Query DSL (Domain Specific Language) for structured query representation
Converts natural language → structured plan → Cypher

This intermediate representation prevents schema hallucination and enables 
strict validation before Cypher generation.
"""

from typing import Dict, List, Optional, Union, Any, Literal
from dataclasses import dataclass, field
from enum import Enum
import json

class FilterOperator(Enum):
    """Supported filter operators"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_EMPTY = "not_empty"
    EXISTS = "exists"
    EXISTS_IF_TEMPORAL = "exists_if_temporal"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    IN_LIST = "in"
    REGEX_MATCH = "regex"

class TemporalOrder(Enum):
    """Temporal ordering options"""
    ASC = "asc"
    DESC = "desc"
    CHRONOLOGICAL = "chronological"  # alias for ASC
    REVERSE_CHRONOLOGICAL = "reverse_chronological"  # alias for DESC

class Direction(Enum):
    """Relationship direction"""
    OUT = "out"
    IN = "in"
    BOTH = "both"

@dataclass
class EntitySpec:
    """Specification for a graph entity (node)"""
    alias: str  # Variable name in query (e.g., "p", "e")
    label: str  # Node label (e.g., "Person", "Event")
    link: Optional[Dict[str, Any]] = None  # Property constraints for linking
    confidence: float = 1.0  # Confidence in entity linking (0-1)

@dataclass
class RelationSpec:
    """Specification for a graph relationship"""
    from_alias: str  # Source entity alias
    type: str  # Relationship type (e.g., "PARTICIPATED_IN")
    to_alias: str  # Target entity alias
    direction: Direction = Direction.OUT
    properties: Optional[Dict[str, Any]] = None  # Relationship properties

@dataclass
class FilterSpec:
    """Specification for a query filter/constraint"""
    on: str  # Property or expression to filter on (e.g., "e.date", "p.name")
    operator: FilterOperator
    value: Optional[Any] = None  # Filter value (if applicable)
    context: Optional[Dict[str, Any]] = None  # Additional context for complex filters

@dataclass
class TemporalSpec:
    """Specification for temporal operations"""
    order: TemporalOrder
    field: str  # Date field to sort by (e.g., "e.date")
    normalize: Optional[str] = None  # Date format to normalize (e.g., "Month DD, YYYY")
    extract_unique: bool = False  # Extract unique dates/times

@dataclass
class AggregationSpec:
    """Specification for aggregation operations"""
    function: str  # count, collect, sum, avg, etc.
    field: Optional[str] = None  # Field to aggregate
    distinct: bool = False  # Use DISTINCT
    alias: Optional[str] = None  # Result alias

@dataclass
class QueryDSL:
    """Main DSL structure for representing a structured query plan"""
    
    # Core query structure
    entities: List[EntitySpec] = field(default_factory=list)
    relations: List[RelationSpec] = field(default_factory=list)
    filters: List[FilterSpec] = field(default_factory=list)
    
    # Query modifiers
    temporal: Optional[TemporalSpec] = None
    aggregations: List[AggregationSpec] = field(default_factory=list)
    
    # Output specification
    select: List[str] = field(default_factory=list)  # Fields to return
    limit: Optional[int] = None
    offset: Optional[int] = None
    
    # Metadata
    intent: Optional[str] = None  # High-level intent description
    confidence: float = 1.0  # Overall confidence in the query plan
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "entities": [
                {
                    "alias": e.alias,
                    "label": e.label,
                    "link": e.link,
                    "confidence": e.confidence
                }
                for e in self.entities
            ],
            "relations": [
                {
                    "from": r.from_alias,
                    "type": r.type,
                    "to": r.to_alias,
                    "direction": r.direction.value,
                    "properties": r.properties
                }
                for r in self.relations
            ],
            "filters": [
                {
                    "on": f.on,
                    "op": f.operator.value,
                    "value": f.value,
                    "context": f.context
                }
                for f in self.filters
            ],
            "temporal": {
                "order": self.temporal.order.value,
                "field": self.temporal.field,
                "normalize": self.temporal.normalize,
                "extract_unique": self.temporal.extract_unique
            } if self.temporal else None,
            "aggregations": [
                {
                    "function": a.function,
                    "field": a.field,
                    "distinct": a.distinct,
                    "alias": a.alias
                }
                for a in self.aggregations
            ],
            "select": self.select,
            "limit": self.limit,
            "offset": self.offset,
            "intent": self.intent,
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueryDSL':
        """Create QueryDSL from dictionary"""
        dsl = cls()
        
        # Parse entities
        for e_data in data.get("entities", []):
            dsl.entities.append(EntitySpec(
                alias=e_data["alias"],
                label=e_data["label"],
                link=e_data.get("link"),
                confidence=e_data.get("confidence", 1.0)
            ))
        
        # Parse relations
        for r_data in data.get("relations", []):
            dsl.relations.append(RelationSpec(
                from_alias=r_data["from"],
                type=r_data["type"],
                to_alias=r_data["to"],
                direction=Direction(r_data.get("direction", "out")),
                properties=r_data.get("properties")
            ))
        
        # Parse filters
        for f_data in data.get("filters", []):
            dsl.filters.append(FilterSpec(
                on=f_data["on"],
                operator=FilterOperator(f_data["op"]),
                value=f_data.get("value"),
                context=f_data.get("context")
            ))
        
        # Parse temporal
        if data.get("temporal"):
            t_data = data["temporal"]
            dsl.temporal = TemporalSpec(
                order=TemporalOrder(t_data["order"]),
                field=t_data["field"],
                normalize=t_data.get("normalize"),
                extract_unique=t_data.get("extract_unique", False)
            )
        
        # Parse aggregations
        for a_data in data.get("aggregations", []):
            dsl.aggregations.append(AggregationSpec(
                function=a_data["function"],
                field=a_data.get("field"),
                distinct=a_data.get("distinct", False),
                alias=a_data.get("alias")
            ))
        
        # Parse output spec
        dsl.select = data.get("select", [])
        dsl.limit = data.get("limit")
        dsl.offset = data.get("offset")
        dsl.intent = data.get("intent")
        dsl.confidence = data.get("confidence", 1.0)
        
        return dsl
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'QueryDSL':
        """Create QueryDSL from JSON string"""
        return cls.from_dict(json.loads(json_str))

# Example DSL instances for common query patterns
def create_person_events_dsl(person_name: str, temporal_order: str = "desc", limit: int = None) -> QueryDSL:
    """Create DSL for person's events with temporal ordering"""
    return QueryDSL(
        entities=[
            EntitySpec(alias="p", label="Person", link={"name": person_name}),
            EntitySpec(alias="e", label="Event")
        ],
        relations=[
            RelationSpec(from_alias="p", type="PARTICIPATED_IN", to_alias="e")
        ],
        filters=[
            FilterSpec(on="e.date", operator=FilterOperator.NOT_EMPTY)
        ],
        temporal=TemporalSpec(
            order=TemporalOrder(temporal_order),
            field="e.date",
            normalize="Month DD, YYYY"
        ),
        select=["e.name", "e.location", "e.date"],
        limit=limit,
        intent=f"Find {person_name}'s events in {temporal_order} chronological order"
    )

def create_location_list_dsl(person_name: str) -> QueryDSL:
    """Create DSL for chronological location list"""
    return QueryDSL(
        entities=[
            EntitySpec(alias="p", label="Person", link={"name": person_name}),
            EntitySpec(alias="e", label="Event")
        ],
        relations=[
            RelationSpec(from_alias="p", type="PARTICIPATED_IN", to_alias="e")
        ],
        filters=[
            FilterSpec(on="e.date", operator=FilterOperator.NOT_EMPTY),
            FilterSpec(on="e.location", operator=FilterOperator.EXISTS_IF_TEMPORAL, value=True)
        ],
        temporal=TemporalSpec(
            order=TemporalOrder.ASC,
            field="e.date",
            normalize="Month DD, YYYY"
        ),
        aggregations=[
            AggregationSpec(function="collect", field="e.location", distinct=True)
        ],
        select=["location"],
        intent=f"List {person_name}'s locations in chronological order"
    )

if __name__ == "__main__":
    # Test DSL creation and serialization
    dsl = create_person_events_dsl("Lucy Carter", "desc", 1)
    print("Example DSL:")
    print(dsl.to_json())
    
    # Test round-trip serialization
    dsl2 = QueryDSL.from_json(dsl.to_json())
    print(f"\nRound-trip test: {dsl.to_dict() == dsl2.to_dict()}") 