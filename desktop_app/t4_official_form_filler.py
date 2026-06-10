"""
T4 Official CRA Form Filler
Uses the official CRA T4 fillable PDF (t4-fill-25e.pdf) and fills it with
employee data
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject

    PYPDF_AVAILABLE = True
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
        from PyPDF2.generic import NameObject

        PYPDF_AVAILABLE = True
    except ImportError:
        PYPDF_AVAILABLE = False
        print(
            "Warning: pypdf/PyPDF2 not installed. Install with: pip install"
            "pypdf"
        )


class T4OfficialFormFiller:
    """Fill official CRA T4 form PDF with employee data"""

    # Fallback defaults used only when company_info table is unavailable
    EMPLOYER_NAME = "Arrow Limousine & Sedan Services Ltd"
    EMPLOYER_PAYROLL_ACCOUNT = "861556827RP0001"
    EMPLOYER_ADDRESS = "3-6841 52 Ave, Red Deer AB T4P 2Z1"
    TEMPLATE_FILENAMES = ("t4-fill-25e.pdf", "t4-fill-256.pdf")

    # Instance-level employer info cache (set via set_db or load_from_db)
    _employer_info_cache: dict | None = None

    @classmethod
    def load_employer_from_db(cls, db) -> None:
        """Populate employer info from the company_info table.
        Call once before generating T4s (e.g. in the T4 widget init).
        Falls back to hardcoded defaults on any error.
        """
        try:
            from db_error_handling import DatabaseContext
            with DatabaseContext(db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT field_name, field_value FROM company_info"
                )
                info = dict(cur.fetchall())
            name = info.get("legal_name") or cls.EMPLOYER_NAME
            account = info.get("payroll_account") or cls.EMPLOYER_PAYROLL_ACCOUNT
            addr_parts = [
                info.get("address_line1", ""),
                info.get("address_city", ""),
                info.get("address_province", ""),
                info.get("address_postal", ""),
            ]
            address = ", ".join(p for p in addr_parts if p).strip(", ")
            address = address or cls.EMPLOYER_ADDRESS
            cls._employer_info_cache = {
                "name": name,
                "payroll_account": account,
                "address": address,
            }
        except Exception as exc:
            logger.warning("company_info not available, using T4 defaults: %s", exc)
            cls._employer_info_cache = None

    @classmethod
    def _get_employer_name(cls) -> str:
        if cls._employer_info_cache:
            return cls._employer_info_cache["name"]
        return cls.EMPLOYER_NAME

    @classmethod
    def _get_employer_payroll_account(cls) -> str:
        if cls._employer_info_cache:
            return cls._employer_info_cache["payroll_account"]
        return cls.EMPLOYER_PAYROLL_ACCOUNT

    @classmethod
    def _get_employer_address(cls) -> str:
        if cls._employer_info_cache:
            return cls._employer_info_cache["address"]
        return cls.EMPLOYER_ADDRESS

    @staticmethod
    def _set_ei_checkbox_state(writer, checked: bool) -> None:
        """Force EI checkbox widget appearance state to match value."""
        on_state = NameObject("/1")
        off_state = NameObject("/Off")
        for page in writer.pages:
            annots = page.get("/Annots") or []
            for annot_ref in annots:
                annot = annot_ref.get_object()
                t = annot.get("/T")
                if str(t) == "Slip1EI[0]":
                    if checked:
                        annot.update(
                            {
                                NameObject("/V"): on_state,
                                NameObject("/AS"): on_state,
                            }
                        )
                    else:
                        annot.update(
                            {
                                NameObject("/V"): off_state,
                                NameObject("/AS"): off_state,
                            }
                        )

    @classmethod
    def _employer_display_name(cls) -> str:
        """Return employer label with address on second line for viewers that"
        "render one field block."""

        return f"{cls._get_employer_name()}\n{cls._get_employer_address()}"

    @staticmethod
    def _format_sin(raw_sin: str) -> str:
        """Return a normalized SIN (NNN NNN NNN) when at least 9 digits are"
        "present."""

        digits = "".join(ch for ch in (raw_sin or "") if ch.isdigit())
        if len(digits) >= 9:
            nine = digits[:9]
            return f"{nine[0:3]} {nine[3:6]} {nine[6:9]}"
        return (raw_sin or "").strip()

    @staticmethod
    def _format_address_block(emp_data: dict) -> str:
        """Build a compact multi-line address without dangling"
        "commas/spaces."""

        line1 = (emp_data.get("address") or "").strip()
        city = (emp_data.get("city") or "").strip()
        province = (emp_data.get("province") or "").strip()
        postal = (emp_data.get("postal_code") or "").strip()

        locality_parts = [p for p in [city, province, postal] if p]
        line2 = ""
        if city and (province or postal):
            suffix = " ".join([p for p in [province, postal] if p])
            line2 = f"{city}, {suffix}".strip()
        elif locality_parts:
            line2 = " ".join(locality_parts)

        if line1 and line2:
            return f"{line1}\n{line2}"
        if line1:
            return line1
        return line2

    @classmethod
    def _resolve_template_path(cls, template_path: str = None) -> Path:
        """Resolve the CRA template from explicit, local, packaged, or"
        "archived locations."""
        import sys

        candidates = []
        if template_path:
            candidates.append(Path(template_path))

        module_dir = Path(__file__).resolve().parent
        search_roots = []
        current = module_dir
        for _ in range(5):
            search_roots.append(current)
            current = current.parent

        # When running as a PyInstaller frozen app, __file__ is inside the
        # _MEIXXXXX temp directory.  Walk up from the actual .exe location
        # as well so relative paths like template/ are found correctly.
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            current = exe_dir
            for _ in range(4):
                if current not in search_roots:
                    search_roots.append(current)
                current = current.parent

        for root in search_roots:
            for filename in cls.TEMPLATE_FILENAMES:
                candidates.append(root / filename)
                candidates.append(root / "template" / filename)
                candidates.append(
                    root / "archive" / "archive_20260418" / filename
                )

        seen = set()
        for candidate in candidates:
            resolved = candidate.expanduser()
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            if resolved.exists():
                return resolved

        searched = "\n".join(str(path) for path in candidates)
        fix_hint = (
            "\n\nFIX: Run install.bat from the Dropbox limo_deploy folder"
            " (not update\\INSTALL_ARROW_LIMO.bat) to copy the template/"
            " folder to Y:\\limo\\template\\."
        )
        raise FileNotFoundError(
            "CRA T4 template not found. Checked:\n" + searched + fix_hint
        )

    def __init__(self, template_path: str = None) -> None:
        """
        Initialize with CRA template path

        Args:
            template_path: Optional explicit path to the CRA fillable PDF
            template
        """
        if not PYPDF_AVAILABLE:
            raise ImportError(
                "pypdf or PyPDF2 required. Install with: pip install pypdf"
            )

        self.template_path = self._resolve_template_path(template_path)

    def list_form_fields(self) -> object:
        """List all fillable fields in the CRA T4 PDF for mapping"""
        reader = PdfReader(str(self.template_path))

        if "/AcroForm" in reader.trailer["/Root"]:
            fields = reader.get_fields()
            if fields:
                print(
                    f"\nFound {len(fields)} fillable fields in"
                    f"{self.template_path.name}:\n"
                )
                for field_name, field_obj in fields.items():
                    field_type = field_obj.get("/FT", "Unknown")
                    print(f"  {field_name:<40} ({field_type})")
                return list(fields.keys())
            else:
                print("No form fields found (PDF may not be fillable)")
                return []
        else:
            print("PDF does not contain an AcroForm (not fillable)")
            return []

    def fill_t4_form(
        self,
        employee_data: dict,
        t4_data: dict,
        tax_year: int,
        output_path: str,
        format_type: str = "employee",
    ) -> object:
        """
        Fill the official CRA T4 form with employee/tax data

        Args:
            employee_data: dict with keys: full_name, sin, address, city,
            province, postal_code
            t4_data: dict with keys: box14, box16, box18, box22, box24, box26,
            box44, box52, etc.
            tax_year: Tax year (e.g., 2025)
            output_path: Where to save the filled PDF
            format_type: 'employee' (2 copies same employee) or
                'employer' (2 different employees)

        Returns:
            str: Path to the saved PDF, or None if failed
        """
        try:
            reader = PdfReader(str(self.template_path))
            writer = PdfWriter()

            # Clone the reader to writer (preserves AcroForm)
            writer.clone_reader_document_root(reader)

            # Build field mapping for one employee
            def build_field_mapping(
                slip_prefix: str, emp_data: dict, t4_vals: dict, year: int
            ) -> object:
                """Build field mapping for a specific slip (Slip1 or Slip2)"""
                # Use first_name/last_name if provided, otherwise split
                # full_name
                if emp_data.get("first_name") and emp_data.get("last_name"):
                    first_name = emp_data.get("first_name", "").upper()
                    last_name = emp_data.get("last_name", "").upper()
                else:
                    # Fallback: split full_name
                    full = emp_data.get("full_name", "")
                    parts = full.split()
                    first_name = parts[0].upper() if parts else ""
                    last_name = (
                        " ".join(parts[1:]).upper() if len(parts) > 1 else ""
                    )

                # Warn if SIN is missing
                sin = emp_data.get("sin", "")
                if not sin or len(sin.replace(" ", "").replace("-", "")) < 9:
                    print(
                        f"  WARNING: Employee '{first_name} {last_name}' has"
                        f"missing or invalid SIN!"
                    )

                formatted_sin = self._format_sin(sin)
                addr_block = self._format_address_block(emp_data)
                is_ei_exempt = float(t4_vals.get("box29", 0) or 0) > 0
                ei_checkbox_value = "/1" if is_ei_exempt else "/Off"
                raw_box29 = str(t4_vals.get("box29_code", "") or "").strip()
                box29_value = (
                    raw_box29
                    if raw_box29
                    in {"11", "12", "13", "14", "15", "16", "17", "18"}
                    else ""
                )

                b = f"form1[0].Page1[0].{slip_prefix}[0]"

                return {
                    f"{b}.EmployersName[0]": self._employer_display_name(),
                    f"{b}.EmployersName[0].Slip1EmployersName[0]": (
                        self._employer_display_name()
                    ),
                    f"{b}.Year[0].Slip1Year[0]": str(year),
                    f"{b}.EmployersAccount[0].Slip1Box54[0]": (
                        self._get_employer_payroll_account()
                    ),
                    f"{b}.Box55[0]": "",
                    f"{b}.Box55[0].Slip1Box55[0]": "",
                    f"{b}.Box12[0].Slip1Box12[0]": formatted_sin,
                    f"{b}.Box10[0].Slip1Box10[0]": emp_data.get(
                        "province", "AB"
                    )
                    or "AB",
                    f"{b}.Box14[0].Slip1Box14[0]": (
                        f"{float(t4_vals.get('box14', 0)):.2f}"
                    ),
                    f"{b}.Box22[0].Slip1Box22[0]": (
                        f"{float(t4_vals.get('box22', 0)):.2f}"
                    ),
                    f"{b}.Box16[0].Slip1Box16[0]": (
                        f"{float(t4_vals.get('box16', 0)):.2f}"
                    ),
                    f"{b}.Box18[0].Slip1Box18[0]": (
                        f"{float(t4_vals.get('box18', 0)):.2f}"
                    ),
                    f"{b}.Box24[0].Slip1Box24[0]": (
                        f"{float(t4_vals.get('box24', 0)):.2f}"
                    ),
                    f"{b}.Box26[0].Slip1Box26[0]": (
                        f"{float(t4_vals.get('box26', 0)):.2f}"
                    ),
                    f"{b}.Employee[0].LastName[0].Slip1LastName[0]": last_name,
                    f"{b}.Employee[0].FirstName[0].Slip1FirstName[0]": (
                        first_name
                    ),
                    f"{b}.Employee[0].Slip1Address[0]": addr_block,
                    f"{b}.Box45[0].DropDownList[0]": emp_data.get(
                        "province", "AB"
                    )
                    or "AB",
                    f"{b}.Box44[0].Slip1Box44[0]": (
                        f"{float(t4_vals.get('box44', 0)):.2f}"
                        if t4_vals.get("box44", 0) > 0
                        else ""
                    ),
                    f"{b}.Box52[0].Slip1Box52[0]": (
                        f"{float(t4_vals.get('box52', 0)):.2f}"
                        if t4_vals.get("box52", 0) > 0
                        else ""
                    ),
                    f"{b}.Box29[0].Slip1Box29[0]": box29_value,
                    f"{b}.Box28[0].EI_CheckBox[0]": ei_checkbox_value,
                    f"{b}.Box28[0].EI_CheckBox[0].Slip1EI[0]": (
                        ei_checkbox_value
                    ),
                }

            # Fill Slip1 (always filled)
            field_mapping = build_field_mapping(
                "Slip1", employee_data, t4_data, tax_year
            )

            # For employee version: fill Slip2 with same employee data (2
            # copies)
            if format_type == "employee":
                field_mapping.update(
                    build_field_mapping(
                        "Slip2", employee_data, t4_data, tax_year
                    )
                )

            if hasattr(writer, "set_need_appearances_writer"):
                writer.set_need_appearances_writer()

            # Update form fields on first page
            writer.update_page_form_field_values(
                writer.pages[0], field_mapping
            )
            self._set_ei_checkbox_state(
                writer, float(t4_data.get("box29", 0) or 0) > 0
            )

            # Write output PDF
            with open(output_path, "wb") as output_file:
                writer.write(output_file)

            print(
                f"SUCCESS: T4 form filled ({format_type} format):"
                f"{output_path}"
            )
            return output_path

        except Exception as e:
            logger.exception("ERROR filling T4 form: %s", e)
            return None

    def fill_t4_employer_format(
        self,
        employee1_data: dict,
        t4_data1: dict,
        employee2_data: dict,
        t4_data2: dict,
        tax_year: int,
        output_path: str,
    ) -> object:
        """
        Fill employer format T4 (2 different employees on one page)

        Args:
            employee1_data: First employee dict
            t4_data1: First employee T4 data
            employee2_data: Second employee dict (can be None for single
            employee)
            t4_data2: Second employee T4 data (can be None)
            tax_year: Tax year
            output_path: Output PDF path

        Returns:
            str: Path to saved PDF, or None if failed
        """
        try:
            reader = PdfReader(str(self.template_path))
            writer = PdfWriter()
            writer.clone_reader_document_root(reader)

            # Helper function from fill_t4_form
            def build_field_mapping(
                slip_prefix: str, emp_data: dict, t4_vals: dict, year: int
            ) -> object:
                if emp_data.get("first_name") and emp_data.get("last_name"):
                    first_name = emp_data.get("first_name", "").upper()
                    last_name = emp_data.get("last_name", "").upper()
                else:
                    full = emp_data.get("full_name", "")
                    parts = full.split()
                    first_name = parts[0].upper() if parts else ""
                    last_name = (
                        " ".join(parts[1:]).upper() if len(parts) > 1 else ""
                    )

                sin = emp_data.get("sin", "")
                formatted_sin = self._format_sin(sin)
                addr_block = self._format_address_block(emp_data)
                is_ei_exempt = float(t4_vals.get("box29", 0) or 0) > 0
                ei_checkbox_value = "/1" if is_ei_exempt else "/Off"
                raw_box29 = str(t4_vals.get("box29_code", "") or "").strip()
                box29_value = (
                    raw_box29
                    if raw_box29
                    in {"11", "12", "13", "14", "15", "16", "17", "18"}
                    else ""
                )

                b = f"form1[0].Page1[0].{slip_prefix}[0]"

                return {
                    f"{b}.EmployersName[0]": self._employer_display_name(),
                    f"{b}.EmployersName[0].Slip1EmployersName[0]": (
                        self._employer_display_name()
                    ),
                    f"{b}.Year[0].Slip1Year[0]": str(year),
                    f"{b}.EmployersAccount[0].Slip1Box54[0]": (
                        self._get_employer_payroll_account()
                    ),
                    f"{b}.Box55[0]": "",
                    f"{b}.Box55[0].Slip1Box55[0]": "",
                    f"{b}.Box12[0].Slip1Box12[0]": formatted_sin,
                    f"{b}.Box10[0].Slip1Box10[0]": emp_data.get(
                        "province", "AB"
                    )
                    or "AB",
                    f"{b}.Box14[0].Slip1Box14[0]": (
                        f"{float(t4_vals.get('box14', 0)):.2f}"
                    ),
                    f"{b}.Box22[0].Slip1Box22[0]": (
                        f"{float(t4_vals.get('box22', 0)):.2f}"
                    ),
                    f"{b}.Box16[0].Slip1Box16[0]": (
                        f"{float(t4_vals.get('box16', 0)):.2f}"
                    ),
                    f"{b}.Box18[0].Slip1Box18[0]": (
                        f"{float(t4_vals.get('box18', 0)):.2f}"
                    ),
                    f"{b}.Box24[0].Slip1Box24[0]": (
                        f"{float(t4_vals.get('box24', 0)):.2f}"
                    ),
                    f"{b}.Box26[0].Slip1Box26[0]": (
                        f"{float(t4_vals.get('box26', 0)):.2f}"
                    ),
                    f"{b}.Employee[0].LastName[0].Slip1LastName[0]": last_name,
                    f"{b}.Employee[0].FirstName[0].Slip1FirstName[0]": (
                        first_name
                    ),
                    f"{b}.Employee[0].Slip1Address[0]": addr_block,
                    f"{b}.Box45[0].DropDownList[0]": emp_data.get(
                        "province", "AB"
                    )
                    or "AB",
                    f"{b}.Box44[0].Slip1Box44[0]": (
                        f"{float(t4_vals.get('box44', 0)):.2f}"
                        if t4_vals.get("box44", 0) > 0
                        else ""
                    ),
                    f"{b}.Box52[0].Slip1Box52[0]": (
                        f"{float(t4_vals.get('box52', 0)):.2f}"
                        if t4_vals.get("box52", 0) > 0
                        else ""
                    ),
                    f"{b}.Box29[0].Slip1Box29[0]": box29_value,
                    f"{b}.Box28[0].EI_CheckBox[0]": ei_checkbox_value,
                    f"{b}.Box28[0].EI_CheckBox[0].Slip1EI[0]": (
                        ei_checkbox_value
                    ),
                }

            # Fill employee 1 (Slip1)
            field_mapping = build_field_mapping(
                "Slip1", employee1_data, t4_data1, tax_year
            )

            if employee2_data and t4_data2:
                slip2_mapping = build_field_mapping(
                    "Slip2", employee2_data, t4_data2, tax_year
                )
                field_mapping.update(slip2_mapping)

            if hasattr(writer, "set_need_appearances_writer"):
                writer.set_need_appearances_writer()

            writer.update_page_form_field_values(
                writer.pages[0], field_mapping
            )
            self._set_ei_checkbox_state(
                writer,
                any(
                    float(v.get("box29", 0) or 0) > 0
                    for v in [t4_data1, (t4_data2 or {})]
                ),
            )

            with open(output_path, "wb") as output_file:
                writer.write(output_file)

            print(f"SUCCESS: T4 employer format filled: {output_path}")
            return output_path

        except Exception as e:
            logger.exception("ERROR filling T4 employer format: %s", e)
            return None


def main() -> None:
    """Example usage and field listing"""
    import sys

    filler = T4OfficialFormFiller()

    if "--list-fields" in sys.argv:
        # List all fields in the CRA form
        filler.list_form_fields()
    else:
        # Example: Fill a test T4
        employee = {
            "full_name": "John Doe",
            "sin": "123 456 789",
            "address": "123 Main St",
            "city": "Calgary",
            "province": "AB",
            "postal_code": "T2P 1K3",
        }

        t4_data = {
            "box14": 45000.00,  # Employment Income
            "box16": 2748.90,  # CPP
            "box18": 889.54,  # EI
            "box22": 8100.00,  # Income Tax
            "box24": 45000.00,  # EI Insurable
            "box26": 45000.00,  # CPP Pensionable
            "box44": 0.00,  # Union Dues
            "box52": 0.00,  # Pension Adjustment
        }

        output = r"L:\limo\T4_2025_Test_Official.pdf"
        filler.fill_t4_form(employee, t4_data, 2025, output)


if __name__ == "__main__":
    main()
