"""
Schema ingestion channel: OpenAPI / GraphQL / SQL DDL → knowledge nodes.
Dry-run pass first to detect conflicts before committing.
"""
from __future__ import annotations

import uuid
from typing import Any

import yaml

from ..channels.base import TrainingChannel
from ...models.enums import EdgeType, Layer, SourceType
from ...services.write_pipeline import NodeWritePipeline


class SchemaIngestionChannel(TrainingChannel):
    async def run(
        self,
        content: str,
        schema_type: str,  # openapi | graphql | sql
    ) -> dict:
        pipeline = NodeWritePipeline(
            self._conn,
            self._intellion_id,
            self._session_id,
            source_type=SourceType.SCHEMA,
        )

        if schema_type == "openapi":
            return await self._ingest_openapi(pipeline, content)
        elif schema_type == "graphql":
            return await self._ingest_graphql(pipeline, content)
        elif schema_type == "sql":
            return await self._ingest_sql(pipeline, content)
        else:
            raise ValueError(f"Unknown schema_type: {schema_type}")

    async def _ingest_openapi(self, pipeline: NodeWritePipeline, content: str) -> dict:
        try:
            spec = yaml.safe_load(content)
        except Exception:
            return {"error": "Failed to parse OpenAPI spec"}

        paths = spec.get("paths", {})
        nodes_written = 0

        for path, methods in paths.items():
            # Structural node for the path
            await pipeline.ingest_fact(
                semantic_id=f"path_{path.replace('/', '_').strip('_')}",
                semantic_definition=f"API endpoint path: {path}",
                layer=Layer.STRUCTURAL,
                page_path=path,
            )
            nodes_written += 1

            for method, operation in methods.items():
                if not isinstance(operation, dict):
                    continue
                summary = operation.get("summary", f"{method.upper()} {path}")
                semantic_id = f"api_{method.upper()}_{path.replace('/', '_').strip('_')}"

                # Behavioral node for the operation
                await pipeline.ingest_fact(
                    semantic_id=semantic_id,
                    semantic_definition=f"{method.upper()} {path}: {summary}",
                    layer=Layer.BEHAVIORAL,
                    page_path=path,
                )
                nodes_written += 1

        return {"endpoints_processed": len(paths), "nodes_written": nodes_written}

    async def _ingest_graphql(self, pipeline: NodeWritePipeline, content: str) -> dict:
        try:
            from graphql import build_schema, GraphQLObjectType, GraphQLField
            schema = build_schema(content)
        except Exception as e:
            return {"error": f"Failed to parse GraphQL schema: {e}"}

        nodes_written = 0
        query_type = schema.query_type
        mutation_type = schema.mutation_type

        for op_type, type_obj in [("query", query_type), ("mutation", mutation_type)]:
            if not type_obj:
                continue
            for field_name, field in type_obj.fields.items():
                desc = field.description or f"GraphQL {op_type}: {field_name}"
                await pipeline.ingest_fact(
                    semantic_id=f"gql_{op_type}_{field_name}",
                    semantic_definition=f"GraphQL {op_type} {field_name}: {desc}",
                    layer=Layer.BEHAVIORAL,
                )
                nodes_written += 1

        return {"nodes_written": nodes_written}

    async def _ingest_sql(self, pipeline: NodeWritePipeline, content: str) -> dict:
        try:
            import sqlglot
            statements = sqlglot.parse(content)
        except Exception as e:
            return {"error": f"Failed to parse SQL: {e}"}

        nodes_written = 0
        for stmt in statements:
            if stmt is None:
                continue
            stmt_type = type(stmt).__name__
            if "Create" in stmt_type and hasattr(stmt, "this"):
                table_name = str(stmt.this)
                await pipeline.ingest_fact(
                    semantic_id=f"table_{table_name}",
                    semantic_definition=f"Database table: {table_name}",
                    layer=Layer.STRUCTURAL,
                )
                nodes_written += 1

        return {"nodes_written": nodes_written}
