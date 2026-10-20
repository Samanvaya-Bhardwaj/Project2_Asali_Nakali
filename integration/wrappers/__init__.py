"""
Wrappers package for Polyglot Heterogeneous Information Integration.
"""
from .base_wrapper import BaseWrapper, SourceMetadata
from .nosql_wrapper import NoSqlDocumentWrapper
from .sql_wrapper import SqliteRelationalWrapper
from .rest_wrapper import RestApiMicroserviceWrapper

__all__ = [
    "BaseWrapper",
    "SourceMetadata",
    "NoSqlDocumentWrapper",
    "SqliteRelationalWrapper",
    "RestApiMicroserviceWrapper",
]
