"""A made-up export in the shape of the Oct 27 DriveCentric file.

Built in code so no .csv or .xlsx is ever committed (R6). Every stock number,
price and count here is invented for the tests.
"""
import csv
import zipfile
from xml.sax.saxutils import escape

HEADERS = ["Vehicle", "Sold", "Delivered", "Trim", "Stock Number", "Pricing", "Msrp",
           "Mileage", "Leads", "Last lead", "Deals", "Age"]

ROWS = [
    # --- kept: KC stock -------------------------------------------------------------
    ["2026 Cadillac Escalade", "No", "No", "Sport Platinum", "C51234", "118990", "121000", "12", "4", "10/26/2026 14:02:11 -05:00", "0", "3"],
    ["2026 Cadillac LYRIQ", "No", "No", "Luxury 2", "C51240", "63990", "65000", "8", "1", "", "0", "40"],
    ["2025 Cadillac CT5", "No", "No", "Premium Luxury", "DC50111", "48500", "52000", "4,321", "2", "", "1", "60"],
    ["2023 Cadillac XT5", "No", "No", "Premium Luxury", "CP60123", "38995", "", "52,849", "3", "", "0", "7"],
    ["2022 Ford F-150", "No", "No", "Lariat", "C51199A", "41500", "", "30,050", "0", "", "2", "8"],
    ["2021 Chevrolet Silverado 1500", "No", "No", "LT", "T4321", "33900", "", "61,200", "0", "", "0", "95"],
    ["2024 Cadillac Escalade IQ", "No", "No", "Sport 1", "CT60222", "0", "", "9,960", "0", "", "0", ""],
    ["2020 BMW iX", "no", "No", "xDrive50", "P61234", "45000", "", "41,000", "0", "", "0", "20"],
    ["2019 Honda Accord", "No", "No", "EX-L", "CX60500", "21000", "", "88,049", "0", "", "0", "12"],
    ["2022 Cadillac XT4", "No", "No", "Sport", "CP60200", "29900", "", "33,333", "0", "", "0", "15"],
    # --- dropped: sold --------------------------------------------------------------
    ["2024 Cadillac XT6", "Yes", "Yes", "Sport", "C51300", "55000", "58000", "10", "9", "", "1", "20"],
    ["2021 Cadillac XT5", "YES", "No", "Luxury", "CP60300", "30000", "", "40,000", "1", "", "1", "30"],
    # --- dropped: Lawrence ----------------------------------------------------------
    ["2022 Kia Telluride", "No", "No", "SX", "L12345", "39000", "", "30,000", "0", "", "0", "10"],
    ["2021 Kia Sorento", "No", "No", "EX", "LT12345", "27000", "", "45,000", "0", "", "0", "10"],
    ["2020 Kia Soul", "No", "No", "S", "DLP1234", "15000", "", "60,000", "0", "", "0", "10"],
    # --- dropped: Topeka ------------------------------------------------------------
    ["2021 Chevrolet Tahoe", "No", "No", "LT", "F12345", "45000", "", "50,000", "0", "", "0", "10"],
    ["2019 GMC Sierra 1500", "No", "No", "SLT", "DFT1234", "35000", "", "70,000", "0", "", "0", "10"],
    ["2022 Kia K5", "No", "No", "GT-Line", "KF12345", "25000", "", "20,000", "0", "", "0", "10"],
    # --- dropped: Independence ------------------------------------------------------
    ["2020 Chevrolet Equinox", "No", "No", "LT", "106671A", "18000", "", "70,000", "0", "", "0", "10"],
    ["2021 Buick Enclave", "No", "No", "Essence", "BP12345", "31000", "", "42,000", "0", "", "0", "10"],
    ["2022 GMC Acadia", "No", "No", "SLE", "B1234", "29000", "", "35,000", "0", "", "0", "10"],
    ["2022 GMC Terrain", "No", "No", "SLE", "DB1234", "26000", "", "30,000", "0", "", "0", "10"],
    ["2021 Chevrolet Trax", "No", "No", "LS", "T12345", "17000", "", "44,000", "0", "", "0", "10"],
    ["2021 Chevrolet Blazer", "No", "No", "RS", "X12345", "30000", "", "39,000", "0", "", "0", "10"],
    ["2020 Chevrolet Malibu", "No", "No", "LT", "P12345", "16000", "", "66,000", "0", "", "0", "10"],
    ["2020 Buick Encore", "No", "No", "Preferred", "DX12345", "15500", "", "58,000", "0", "", "0", "10"],
    # --- dropped: in-transit / order codes and letter-only codes --------------------
    ["2026 Cadillac VISTIQ", "No", "No", "Sport", "GHJWPW*O", "0", "80000", "0", "0", "", "0", "0"],
    ["2026 Cadillac OPTIQ", "No", "No", "Luxury 1", "GKXTRB", "0", "55000", "0", "0", "", "0", "0"],
    ["2026 Cadillac CT4", "No", "No", "Sport", "", "0", "40000", "0", "0", "", "0", "0"],
]

FAR_STOCKS = {"L12345", "LT12345", "DLP1234", "F12345", "DFT1234", "KF12345", "106671A",
              "BP12345", "B1234", "DB1234", "T12345", "X12345", "P12345", "DX12345"}
SOLD_STOCKS = {"C51300", "CP60300"}
TRANSIT_STOCKS = {"GHJWPW*O", "GKXTRB", ""}
KEPT_STOCKS = {"C51234", "C51240", "DC50111", "CP60123", "C51199A", "T4321", "CT60222",
               "P61234", "CX60500", "CP60200"}


def write_csv(path, headers=HEADERS, rows=ROWS):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    return path


def write_xlsx(path, headers=HEADERS, rows=ROWS):
    """Smallest valid .xlsx: shared strings for text, inline numbers."""
    strings, index = [], {}

    def sid(text):
        if text not in index:
            index[text] = len(strings)
            strings.append(text)
        return index[text]

    def col(n):
        s = ""
        n += 1
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    sheet = []
    for r, row in enumerate([headers] + rows, 1):
        cells = []
        for c, val in enumerate(row):
            if val == "":
                continue
            ref = f"{col(c)}{r}"
            if r > 1 and val.isdigit():
                cells.append(f'<c r="{ref}"><v>{val}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="s"><v>{sid(val)}</v></c>')
        sheet.append(f'<row r="{r}">{"".join(cells)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet {ns}><sheetData>{"".join(sheet)}</sheetData></worksheet>')
        z.writestr("xl/sharedStrings.xml",
                   f'<sst {ns}>' + "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
                   + "</sst>")
    return path
