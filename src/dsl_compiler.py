#!/usr/bin/env python3
"""
DSL to Cypher Compiler with strict schema validation and whitelist enforcement

This compiler ensures that only valid schema elements are used and prevents
schema hallucination by enforcing whitelist constraints.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass
from query_dsl import (
    QueryDSL, EntitySpec, RelationSpec, FilterSpec, TemporalSpec, 
    AggregationSpec, FilterOperator, TemporalOrder, Direction
)
import re

@dataclass
class ValidationResult:
    """Result of schema validation"""
    is_valid: bool
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

@dataclass 
class SchemaWhitelist:
    """Whitelist of allowed schema elements"""
    labels: Set[str]
    relationships: Set[str]
    properties: Dict[str, Set[str]]  # label -> {property_names}
    
    @classmethod
    def from_property_keys_data(cls, property_keys_data: Dict) -> 'SchemaWhitelist':
        """Create whitelist from property keys data"""
        property_keys = property_keys_data.get('property_keys', {})
        
        # Extract labels (excluding special keys)
        labels = set(label for label in property_keys.keys() if not label.startswith('_'))
        
        # Extract relationships
        relationships = set()
        if '_relationships' in property_keys:
            relationships = set(property_keys['_relationships'].keys())
        
        # Extract properties per label
        properties = {}
        for label, props in property_keys.items():
            if not label.startswith('_'):
                properties[label] = set(props) if isinstance(props, list) else set()
        
        return cls(labels=labels, relationships=relationships, properties=properties)

class DSLCompiler:
    """Compiles QueryDSL to validated Cypher queries"""
    
    def __init__(self, schema_whitelist: SchemaWhitelist):
        self.schema = schema_whitelist
        
        # Date normalization template (fixing comma issue)
        self.month_conversion = """CASE 
    WHEN {field} CONTAINS 'January' THEN '01'
    WHEN {field} CONTAINS 'February' THEN '02'
    WHEN {field} CONTAINS 'March' THEN '03'
    WHEN {field} CONTAINS 'April' THEN '04'
    WHEN {field} CONTAINS 'May' THEN '05'
    WHEN {field} CONTAINS 'June' THEN '06'
    WHEN {field} CONTAINS 'July' THEN '07'
    WHEN {field} CONTAINS 'August' THEN '08'
    WHEN {field} CONTAINS 'September' THEN '09'
    WHEN {field} CONTAINS 'October' THEN '10'
    WHEN {field} CONTAINS 'November' THEN '11'
    WHEN {field} CONTAINS 'December' THEN '12'
    ELSE '00'
END"""
    
    def validate_dsl(self, dsl: QueryDSL) -> ValidationResult:
        """Validate DSL against schema whitelist"""
        result = ValidationResult(is_valid=True)
        
        # Validate entities
        for entity in dsl.entities:
            if entity.label not in self.schema.labels:
                result.errors.append(f"Invalid label '{entity.label}'. Allowed: {self.schema.labels}")
                result.is_valid = False
            
            # Validate entity link properties
            if entity.link:
                label_props = self.schema.properties.get(entity.label, set())
                for prop in entity.link.keys():
                    if prop not in label_props:
                        result.errors.append(f"Invalid property '{prop}' for label '{entity.label}'. Allowed: {label_props}")
                        result.is_valid = False
        
        # Validate relationships
        for relation in dsl.relations:
            if relation.type not in self.schema.relationships:
                result.errors.append(f"Invalid relationship '{relation.type}'. Allowed: {self.schema.relationships}")
                result.is_valid = False
        
        # Validate filter properties
        for filter_spec in dsl.filters:
            # Extract label.property from filter.on (e.g., "e.date" -> "Event", "date")
            if '.' in filter_spec.on:
                alias, prop = filter_spec.on.split('.', 1)
                # Find entity by alias
                entity = next((e for e in dsl.entities if e.alias == alias), None)
                if entity:
                    label_props = self.schema.properties.get(entity.label, set())
                    if prop not in label_props:
                        result.errors.append(f"Invalid property '{prop}' for label '{entity.label}'. Allowed: {label_props}")
                        result.is_valid = False
        
        # Validate temporal field
        if dsl.temporal:
            if '.' in dsl.temporal.field:
                alias, prop = dsl.temporal.field.split('.', 1)
                entity = next((e for e in dsl.entities if e.alias == alias), None)
                if entity:
                    label_props = self.schema.properties.get(entity.label, set())
                    if prop not in label_props:
                        result.errors.append(f"Invalid temporal property '{prop}' for label '{entity.label}'. Allowed: {label_props}")
                        result.is_valid = False
        
        return result
    
    def _escape_cypher_value(self, value: Any) -> str:
        """Safely escape values for Cypher injection prevention"""
        if isinstance(value, str):
            # Escape single quotes and prevent injection
            return "'" + value.replace("'", "\\'") + "'"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return str(value).lower()
        elif value is None:
            return "null"
        else:
            return "'" + str(value).replace("'", "\\'") + "'"
    
    def _compile_match_clause(self, dsl: QueryDSL) -> str:
        """Compile MATCH clause from entities and relations"""
        if not dsl.entities:
            return ""
        
        # Build node patterns
        node_patterns = {}
        for entity in dsl.entities:
            pattern = f"({entity.alias}:{entity.label}"
            if entity.link:
                constraints = []
                for prop, value in entity.link.items():
                    constraints.append(f"{prop}: {self._escape_cypher_value(value)}")
                if constraints:
                    pattern += " {" + ", ".join(constraints) + "}"
            pattern += ")"
            node_patterns[entity.alias] = pattern
        
        # Build relationship patterns
        if not dsl.relations:
            # No relationships, just return nodes
            return "MATCH " + ", ".join(node_patterns.values())
        
        # Build connected pattern
        match_parts = []
        for relation in dsl.relations:
            from_node = node_patterns.get(relation.from_alias, f"({relation.from_alias})")
            to_node = node_patterns.get(relation.to_alias, f"({relation.to_alias})")
            
            if relation.direction == Direction.OUT:
                rel_pattern = f"-[:{relation.type}]->"
            elif relation.direction == Direction.IN:
                rel_pattern = f"<-[:{relation.type}]-"
            else:  # BOTH
                rel_pattern = f"-[:{relation.type}]-"
            
            pattern = f"{from_node}{rel_pattern}{to_node}"
            match_parts.append(pattern)
        
        return "MATCH " + ", ".join(match_parts)
    
    def _compile_where_clause(self, dsl: QueryDSL) -> str:
        """Compile WHERE clause from filters"""
        if not dsl.filters:
            return ""
        
        conditions = []
        for filter_spec in dsl.filters:
            field = filter_spec.on
            op = filter_spec.operator
            value = filter_spec.value
            
            if op == FilterOperator.NOT_EMPTY:
                conditions.append(f"{field} <> ''")
            elif op == FilterOperator.EXISTS:
                conditions.append(f"EXISTS({field})")
            elif op == FilterOperator.EXISTS_IF_TEMPORAL:
                if value:  # Only add if temporal context is true
                    conditions.append(f"{field} IS NOT NULL")
            elif op == FilterOperator.EQUALS:
                conditions.append(f"{field} = {self._escape_cypher_value(value)}")
            elif op == FilterOperator.NOT_EQUALS:
                conditions.append(f"{field} <> {self._escape_cypher_value(value)}")
            elif op == FilterOperator.CONTAINS:
                conditions.append(f"{field} CONTAINS {self._escape_cypher_value(value)}")
            elif op == FilterOperator.GREATER_THAN:
                conditions.append(f"{field} > {self._escape_cypher_value(value)}")
            elif op == FilterOperator.LESS_THAN:
                conditions.append(f"{field} < {self._escape_cypher_value(value)}")
            elif op == FilterOperator.IN_LIST:
                if isinstance(value, list):
                    escaped_values = [self._escape_cypher_value(v) for v in value]
                    conditions.append(f"{field} IN [{', '.join(escaped_values)}]")
            elif op == FilterOperator.REGEX_MATCH:
                conditions.append(f"{field} =~ {self._escape_cypher_value(value)}")
        
        if conditions:
            return "WHERE " + " AND ".join(conditions)
        return ""
    
    def _compile_temporal_with(self, dsl: QueryDSL) -> Tuple[str, List[str]]:
        """Compile temporal WITH clause and return (with_clause, additional_fields)"""
        if not dsl.temporal:
            return "", []
        
        field = dsl.temporal.field
        normalize = dsl.temporal.normalize
        
        if not normalize:
            return "", []
        
        # Generate date conversion logic for "Month DD, YYYY" format
        if normalize == "Month DD, YYYY":
            month_case = self.month_conversion.format(field=field)
            
            additional_fields = []
            if dsl.temporal.extract_unique:
                additional_fields.append(f"{field} as original_date")
            
            additional_str = ", " + ", ".join(additional_fields) if additional_fields else ""
            
            with_clause = f"""WITH {', '.join(f"{e.alias}" for e in dsl.entities)}{additional_str}, 
     {month_case} as month_num,
     split({field}, ' ')[1] as day,
     split({field}, ' ')[2] as year
WITH {', '.join(f"{e.alias}" for e in dsl.entities)}{additional_str}, year + '-' + month_num + '-' + 
     CASE WHEN size(day) = 3 THEN substring(day, 0, 2) ELSE day END as sort_date"""
            
            return with_clause, additional_fields
        
        return "", []
    
    def _compile_aggregation_and_return(self, dsl: QueryDSL, with_temporal: bool = False) -> str:
        """Compile aggregation and RETURN clause"""
        if not dsl.aggregations and not dsl.temporal:
            # Simple return
            if dsl.select:
                return_fields = dsl.select
            else:
                return_fields = [f"{e.alias}" for e in dsl.entities]
            
            return_clause = "RETURN " + ", ".join(return_fields)
            
            if dsl.limit:
                return_clause += f" LIMIT {dsl.limit}"
            if dsl.offset:
                return_clause += f" OFFSET {dsl.offset}"
            
            return return_clause
        
        parts = []
        
        # Handle temporal ordering
        if dsl.temporal and with_temporal:
            order_direction = "ASC" if dsl.temporal.order in [TemporalOrder.ASC, TemporalOrder.CHRONOLOGICAL] else "DESC"
            parts.append(f"ORDER BY sort_date {order_direction}")
        
        # Handle aggregations
        if dsl.aggregations:
            agg_parts = []
            for agg in dsl.aggregations:
                if agg.function == "collect":
                    distinct_modifier = "DISTINCT " if agg.distinct else ""
                    field = agg.field or f"{dsl.entities[0].alias}"
                    agg_str = f"COLLECT({distinct_modifier}{field})"
                    if agg.alias:
                        agg_str += f" as {agg.alias}"
                    agg_parts.append(agg_str)
                elif agg.function == "count":
                    distinct_modifier = "DISTINCT " if agg.distinct else ""
                    field = agg.field or "*"
                    agg_str = f"COUNT({distinct_modifier}{field})"
                    if agg.alias:
                        agg_str += f" as {agg.alias}"
                    agg_parts.append(agg_str)
            
            if agg_parts:
                parts.append("WITH " + ", ".join(agg_parts))
                
                # Handle UNWIND for list results
                for agg in dsl.aggregations:
                    if agg.function == "collect":
                        collection_name = agg.alias or f"{agg.field.split('.')[-1]}s"
                        item_name = agg.field.split('.')[-1] if agg.field else "item"
                        parts.append(f"UNWIND {collection_name} as {item_name}")
                        parts.append(f"RETURN {item_name}")
                        break
        
        # Regular return if no aggregations
        if not dsl.aggregations:
            return_fields = dsl.select if dsl.select else [f"{e.alias}" for e in dsl.entities]
            return_clause = "RETURN " + ", ".join(return_fields)
            
            if dsl.temporal and with_temporal:
                order_direction = "ASC" if dsl.temporal.order in [TemporalOrder.ASC, TemporalOrder.CHRONOLOGICAL] else "DESC"
                return_clause += f" ORDER BY sort_date {order_direction}"
            
            if dsl.limit:
                return_clause += f" LIMIT {dsl.limit}"
            if dsl.offset:
                return_clause += f" OFFSET {dsl.offset}"
            
            parts.append(return_clause)
        
        return "\n".join(parts)
    
    def compile(self, dsl: QueryDSL) -> Tuple[str, ValidationResult]:
        """
        Compile DSL to Cypher query with validation
        
        Returns:
            Tuple[str, ValidationResult]: (cypher_query, validation_result)
        """
        # Validate DSL first
        validation = self.validate_dsl(dsl)
        if not validation.is_valid:
            return "", validation
        
        # Compile query parts
        parts = []
        
        # MATCH clause
        match_clause = self._compile_match_clause(dsl)
        if match_clause:
            parts.append(match_clause)
        
        # WHERE clause
        where_clause = self._compile_where_clause(dsl)
        if where_clause:
            parts.append(where_clause)
        
        # Temporal WITH clause
        temporal_with, additional_fields = self._compile_temporal_with(dsl)
        has_temporal_with = bool(temporal_with)
        if temporal_with:
            parts.append(temporal_with)
        
        # Aggregation and RETURN
        return_clause = self._compile_aggregation_and_return(dsl, has_temporal_with)
        if return_clause:
            parts.append(return_clause)
        
        cypher_query = "\n".join(parts)
        
        return cypher_query, validation

if __name__ == "__main__":
    # Test the compiler
    from query_dsl import create_person_events_dsl, create_location_list_dsl
    
    # Mock schema
    schema = SchemaWhitelist(
        labels={"Person", "Event", "Location"},
        relationships={"PARTICIPATED_IN", "OCCURRED_AT"},
        properties={
            "Person": {"name", "birthDate", "aka"},
            "Event": {"name", "date", "location", "description"},
            "Location": {"name", "country", "coordinates"}
        }
    )
    
    compiler = DSLCompiler(schema)
    
    # Test 1: Simple person events
    print("=== Test 1: Person Events ===")
    dsl1 = create_person_events_dsl("Lucy Carter", "desc", 1)
    query1, validation1 = compiler.compile(dsl1)
    print(f"Valid: {validation1.is_valid}")
    if validation1.errors:
        print(f"Errors: {validation1.errors}")
    print(f"Query:\n{query1}\n")
    
    # Test 2: Location list
    print("=== Test 2: Location List ===")
    dsl2 = create_location_list_dsl("Lucy Carter")
    query2, validation2 = compiler.compile(dsl2)
    print(f"Valid: {validation2.is_valid}")
    if validation2.errors:
        print(f"Errors: {validation2.errors}")
    print(f"Query:\n{query2}\n") 