"""Normalize LMS driver codes to canonical format."""

RAW_CODES = [
    "10",
    "3",
    "5",
    "6",
    "7",
    "8",
    "9",
    "D29",
    "Dr01",
    "Dr03",
    "Dr04",
    "Dr05",
    "Dr06",
    "Dr07",
    "Dr08",
    "Dr09",
    "Dr100",
    "DR101",
    "DR103",
    "DR104",
    "Dr105",
    "Dr106",
    "DR107",
    "DR108",
    "DR109",
    "Dr11",
    "DR110",
    "Dr111",
    "DR113",
    "Dr114",
    "DR115",
    "DR116",
    "DR117",
    "Dr118",
    "DR119",
    "Dr12",
    "DR120",
    "DR121",
    "Dr122",
    "DR123",
    "DR124",
    "DR125",
    "DR126",
    "DR127",
    "Dr128",
    "Dr14",
    "DR15",
    "Dr16",
    "Dr17",
    "Dr18",
    "Dr19",
    "Dr20",
    "Dr21",
    "Dr22",
    "Dr24",
    "Dr25",
    "Dr26",
    "Dr27",
    "Dr28",
    "Dr29",
    "Dr30",
    "Dr31",
    "Dr32",
    "Dr33",
    "Dr34",
    "Dr35",
    "Dr36",
    "Dr37",
    "Dr38",
    "Dr39",
    "Dr40",
    "Dr41",
    "Dr42",
    "Dr43",
    "Dr44",
    "Dr45",
    "Dr47",
    "Dr48",
    "Dr49",
    "Dr50",
    "Dr51 ",
    "Dr52",
    "Dr53",
    "DR54",
    "Dr55",
    "Dr56",
    "Dr57",
    "Dr58",
    "Dr59",
    "Dr60",
    "Dr61",
    "Dr62",
    "Dr63",
    "Dr64",
    "Dr65",
    "Dr66",
    "Dr67",
    "Dr68",
    "Dr69",
    "Dr70",
    "Dr71",
    "Dr72",
    "Dr73",
    "Dr74",
    "Dr75",
    "Dr76",
    "Dr77",
    "Dr78",
    "Dr79",
    "Dr80",
    "DR81",
    "Dr82",
    "Dr83",
    "Dr84",
    "Dr85",
    "DR86",
    "Dr87",
    "Dr88",
    "Dr90",
    "Dr91",
    "Dr92",
    "Dr93",
    "Dr94",
    "Dr95",
    "Dr96",
    "Dr97",
    "Dr98",
    "Dr99",
    "H 04",
    "H02",
    "H03",
    "H04",
    "H06",
    "H07",
    "H08",
    "H09",
    "H10",
    "Of01",
    "Of02",
    "Of03",
    "OF04",
    "OF5",
]


def normalize_code(raw: str) -> str:
    value = raw.strip().upper().replace(" ", "")

    # Numeric only -> DR + 3-digit
    if value.isdigit():
        return f"DR{int(value):03d}"

    # D## -> DR###
    if value.startswith("D") and value[1:].isdigit():
        return f"DR{int(value[1:]):03d}"

    # DR## -> DR###
    if value.startswith("DR") and value[2:].isdigit():
        num = int(value[2:])
        return f"DR{num:03d}" if num < 1000 else f"DR{num}"

    # H## -> H## (2-digit)
    if value.startswith("H") and value[1:].isdigit():
        return f"H{int(value[1:]):02d}"

    # OF## -> OF## (2-digit)
    if value.startswith("OF") and value[2:].isdigit():
        return f"OF{int(value[2:]):02d}"

    return value


def main():
    print("Original -> Normalized")
    print("=" * 40)
    for code in RAW_CODES:
        print(f"{code.strip():<8} -> {normalize_code(code)}")


if __name__ == "__main__":
    main()
