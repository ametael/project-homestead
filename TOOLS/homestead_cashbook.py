from collections import defaultdict
import csv
from datetime import date
from decimal import Decimal
import io
import re
from xml.etree import ElementTree as xml
import zipfile

import homestead as core


FIELDS = ("date", "description", "category", "currency", "flow", "amount")
SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"


def number(value):
    core.require(re.fullmatch(r"\d{1,12}(?:\.\d{1,6})?", value.strip()),
                 "Amounts must be positive decimal numbers with at most six fractional places.")
    amount = Decimal(value.strip())
    core.require(amount > 0, "Amounts must be greater than zero.")
    core.require(len(amount.normalize().as_tuple().digits) <= 15, "An amount exceeds Excel's exact display precision.")
    return amount


def cell_text(text):
    return len(text) <= 1000 and all(ch.isprintable() for ch in text)


def load(text, columns, currency):
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    headers = reader.fieldnames
    core.require(headers and len(headers) == len(set(headers)) and len(headers) <= 64,
                 "The CSV must have unique headers.")
    required = set(FIELDS) - ({"currency"} if currency else set())
    core.require(all(columns[field] in headers for field in required),
                 "Map the required columns to headers in the CSV.")
    entries = []
    totals = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for row in reader:
        core.require(len(entries) < 10000 and None not in row and all(value is not None for value in row.values()),
                     "A row is incomplete or the file has over 10,000 transactions.")
        day = row[columns["date"]].strip()
        core.require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", day), "Dates must use YYYY-MM-DD.")
        date.fromisoformat(day)
        description = row[columns["description"]].strip()
        category = row[columns["category"]].strip()
        unit = (row.get(columns["currency"]) or currency or "").strip().upper()
        flow = row[columns["flow"]].strip().casefold()
        core.require(bool(description and category) and cell_text(description) and cell_text(category),
                     "Descriptions and categories must be short, single-line text.")
        core.require(re.fullmatch(r"[A-Z][A-Z0-9]{2,7}", unit), "Use a currency code such as USD or IDR.")
        core.require(flow in {"income", "expense"}, "Flow must be income or expense.")
        amount = number(row[columns["amount"]])
        totals[unit][flow == "expense"] += amount
        entries.append((day, description, category, unit, flow, amount))
    core.require(entries, "The cashbook has no transactions.")
    for amounts in totals.values():
        core.require(all(len(n.normalize().as_tuple().digits) <= 15 for n in (*amounts, amounts[0] - amounts[1])),
                     "A currency total exceeds Excel's exact display precision.")
    summary = [("Currency", "Income", "Expenses", "Net")]
    summary.extend((code, income, expense, income - expense) for code, (income, expense) in sorted(totals.items()))
    return summary, [("Date", "Description", "Category", "Currency", "Flow", "Amount"), *entries]


def document(namespace, name, **attributes):
    return xml.Element(name, {"xmlns": namespace, **attributes})


def emit(root):
    return xml.tostring(root, encoding="utf-8", xml_declaration=True)


def worksheet(rows, widths):
    ws = document(SHEET, "worksheet")
    columns = xml.SubElement(ws, "cols")
    for index, width in enumerate(widths, 1):
        xml.SubElement(columns, "col", min=str(index), max=str(index), width=str(width), customWidth="1")
    data = xml.SubElement(ws, "sheetData")
    for index, values in enumerate(rows, 1):
        row = xml.SubElement(data, "row", r=str(index))
        for letter, value in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", values, strict=False):
            attributes = {"r": f"{letter}{index}"}
            if isinstance(value, Decimal):
                cel = xml.SubElement(row, "c", attributes)
                xml.SubElement(cel, "v").text = format(value, "f")
            else:
                cel = xml.SubElement(row, "c", attributes, t="inlineStr")
                inline = xml.SubElement(cel, "is")
                xml.SubElement(inline, "t").text = value
    return emit(ws)


def workbook(summary, entries):
    content = document(CONTENT, "Types")
    xml.SubElement(content, "Default", Extension="rels",
                   ContentType="application/vnd.openxmlformats-package.relationships+xml")
    xml.SubElement(content, "Default", Extension="xml", ContentType="application/xml")
    xml.SubElement(content, "Override", PartName="/xl/workbook.xml",
                   ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    package = document(PACKAGE_REL, "Relationships")
    xml.SubElement(package, "Relationship", Id="rId1",
                   Type=REL + "/officeDocument", Target="xl/workbook.xml")
    book = document(SHEET, "workbook", **{"xmlns:r": REL})
    sheets = xml.SubElement(book, "sheets")
    sheet_links = document(PACKAGE_REL, "Relationships")
    files = {}
    for index, (name, rows, widths) in enumerate(
            (("Summary", summary, (17, 20, 20, 20)), ("Transactions", entries, (15, 46, 28, 14, 15, 20))), 1):
        key = f"worksheets/sheet{index}.xml"
        rid = f"rId{index}"
        xml.SubElement(sheets, "sheet", {"name": name, "sheetId": str(index), "r:id": rid})
        xml.SubElement(sheet_links, "Relationship", Id=rid, Type=REL + "/worksheet", Target=key)
        xml.SubElement(content, "Override", PartName=f"/xl/{key}",
                       ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
        files["xl/" + key] = worksheet(rows, widths)
    files.update({"[Content_Types].xml": emit(content), "_rels/.rels": emit(package),
                  "xl/workbook.xml": emit(book), "xl/_rels/workbook.xml.rels": emit(sheet_links)})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def csv_export(entries):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(FIELDS)
    for entry in entries[1:]:
        row = [("'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value)
               for value in entry]
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8-sig")


def output_path(raw, suffix):
    path = core.clean_relative(raw)
    core.require(len(path.parts) > 1 and path.parts[0].upper() in {"MEMORY", "PROJECTS"}
                 and path.suffix.lower() == suffix, f"Choose a {suffix} file within MEMORY or PROJECTS.")
    return path


def install_exports(home, outputs):
    with home.lock():
        targets = [(home.path(path.as_posix()), data) for path, data in outputs]
        core.require(all(not target.exists() and target.parent.is_dir() for target, _ in targets),
                     "Each output must be a new file in an existing folder.")
        stages = []
        installed = []
        try:
            for target, data in targets:
                staged = target.with_name("cashbook-" + core.uuid.uuid4().hex + ".tmp")
                with staged.open("xb") as output:
                    stages.append((staged, target))
                    output.write(data)
            for staged, target in stages:
                try:
                    core.no_replace(staged, target)
                except (OSError, core.SafetyError) as error:
                    paths = ", ".join(path.relative_to(home.root).as_posix() for path in installed)
                    if paths:
                        raise core.SafetyError("Export interrupted. Completed outputs: " + paths) from error
                    raise
                installed.append(target)
        finally:
            for staged, _ in stages:
                if staged.exists():
                    staged.unlink()


def export(home, source, destination, purpose, mapping=None, currency=None, csv_out=None):
    columns = dict(zip(FIELDS, FIELDS, strict=True))
    for pair in mapping or []:
        field, separator, header = pair.partition("=")
        core.require(separator and field in FIELDS and header, "Use repeatable --column field=CSV-header options.")
        columns[field] = header
    core.require(len(set(columns.values())) == len(columns), "Use a different input column for each field.")
    path = output_path(destination, ".xlsx")
    csv_path = output_path(csv_out, ".csv") if csv_out else None
    data, sha = core.guardian_bytes(home, source, purpose, core.TEXT_LIMIT)
    try:
        summary, entries = load(data.decode("utf-8-sig"), columns, currency)
    except csv.Error as error:
        raise core.SafetyError("The source CSV could not be parsed.") from error
    content = workbook(summary, entries)
    outputs = [(path, content)]
    result = {"path": path.as_posix(), "input_sha256": sha, "transactions": len(entries) - 1,
              "currencies": len(summary) - 1, "sha256": core.digest(content)}
    if csv_path:
        csv_bytes = csv_export(entries)
        outputs.append((csv_path, csv_bytes))
        result.update(csv_path=csv_path.as_posix(), csv_sha256=core.digest(csv_bytes))
    install_exports(home, outputs)
    return result
