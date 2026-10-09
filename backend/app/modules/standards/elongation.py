"""Elongation metadata. Numeric values and limits remain keyed by A%."""
from sqlalchemy import inspect, text


def basis(standard):
    return getattr(standard, "elongation_basis", None) if standard else None


def label(standard):
    value = basis(standard)
    return f"{value} (%)" if value else None


def ensure_schema(connection):
    schema = connection.get_execution_options().get("schema_translate_map", {}).get(None)
    inspector = inspect(connection)
    table = "normative_standards"
    if not inspector.has_table(table, schema=schema):
        raise ValueError("normative_standards_required")
    columns = {c["name"]: c for c in inspector.get_columns(table, schema=schema)}
    quote = connection.dialect.identifier_preparer
    qualified = (quote.quote_schema(schema) + "." if schema else "") + quote.quote(table)
    added = "elongation_basis" not in columns
    if added:
        connection.execute(text(f"ALTER TABLE {qualified} ADD COLUMN elongation_basis VARCHAR(16)"))
    # Some old LOCAL installations retain unmapped, required columns. Do not
    # drop columns or update historical values. Supply defaults for new inserts
    # only; current Alpha does not contain these columns.
    if connection.dialect.name == "postgresql":
        for name, default in (("regola_tipo", "'generale'"), ("is_active", "TRUE")):
            if name in columns and columns[name].get("default") is None:
                connection.execute(text(f"ALTER TABLE {qualified} ALTER COLUMN {quote.quote(name)} SET DEFAULT {default}"))
    return added
