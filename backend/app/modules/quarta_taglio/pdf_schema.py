"""Additive PDF filename migration shared by startup and offline Alpha recovery."""
from sqlalchemy import inspect, text


PDF_TABLES = ("quarta_taglio_final_certificates", "quarta_taglio_certificate_pdf_versions")


def missing_pdf_filename_columns(connection):
    schema = connection.get_execution_options().get("schema_translate_map", {}).get(None)
    inspector = inspect(connection)
    missing = []
    for table in PDF_TABLES:
        if not inspector.has_table(table, schema=schema):
            raise ValueError("pdf_certificate_tables_required")
        if "pdf_file_name" not in {column["name"] for column in inspector.get_columns(table, schema=schema)}:
            missing.append(table)
    return missing


def ensure_pdf_filename_columns(connection):
    """Caller owns the transaction; no bootstrap, data rewrites or source reads."""
    missing = missing_pdf_filename_columns(connection)
    schema = connection.get_execution_options().get("schema_translate_map", {}).get(None)
    quote = connection.dialect.identifier_preparer
    for table in missing:
        qualified = quote.quote(table)
        if schema:
            qualified = quote.quote_schema(schema) + "." + qualified
        connection.execute(text(f"ALTER TABLE {qualified} ADD COLUMN pdf_file_name VARCHAR(255)"))
    return [table + ".pdf_file_name" for table in missing]
