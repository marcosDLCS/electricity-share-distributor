"""Huawei FusionSolar PV generation Excel report parser and loader."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.schema import IngestionError, ParseError, ValidationError


class HuaweiGenerationLoader:
    """Discovers, validates, and normalizes Huawei FusionSolar generation Excel reports."""

    def __init__(self, generation_dir: Path | str) -> None:
        self.generation_dir = Path(generation_dir)

    def discover_files(self) -> list[Path]:
        """Find all Excel files (.xlsx, .xls) in the generation directory."""
        if not self.generation_dir.exists():
            raise IngestionError(f"Generation directory not found: {self.generation_dir}")

        files = sorted(
            [
                f
                for f in self.generation_dir.iterdir()
                if f.is_file()
                and f.suffix.lower() in (".xlsx", ".xls")
                and not f.name.startswith("~$")
                and not f.name.startswith(".")
            ]
        )
        if not files:
            raise IngestionError(
                f"No Excel files found in generation directory: {self.generation_dir}"
            )
        return files

    @classmethod
    def parse_file(cls, file_path: Path) -> pd.DataFrame:
        """Parse a single Huawei FusionSolar generation report into a normalized DataFrame."""
        try:
            # Huawei reports typically have title on row 0 and headers on row 1
            df = pd.read_excel(file_path, header=1)
        except Exception as err:
            raise ParseError(f"Failed to read Excel file {file_path.name}: {err}") from err

        if df.empty:
            raise ValidationError(f"Excel file {file_path.name} is empty.")

        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]

        # Locate timestamp column
        ts_col = None
        for col in df.columns:
            if "período estadístico" in col.lower() or "periodo estadistico" in col.lower():
                ts_col = col
                break
        if not ts_col:
            # Check first column as fallback
            ts_col = df.columns[0]

        # Locate PV generation column
        gen_col = None
        for col in df.columns:
            if "rendimiento fv" in col.lower():
                gen_col = col
                break
        if not gen_col:
            for col in df.columns:
                if "rendimiento del inversor" in col.lower():
                    gen_col = col
                    break
        if not gen_col:
            raise ValidationError(
                f"File {file_path.name} does not contain 'Rendimiento FV' or 'Rendimiento del inversor' column."
            )

        # Locate consumption column if present (e.g. 'Consumo (kWh)', 'Consumption (kWh)')
        cons_col = None
        for col in df.columns:
            c_low = col.lower()
            if (
                c_low.startswith("consumo")
                or "consumo (kwh)" in c_low
                or c_low.startswith("consumption")
            ):
                cons_col = col
                break

        # Locate self-consumption column if present (e.g. 'Autoconsumo (kWh)', 'Self-consumption (kWh)')
        self_cons_col = None
        for col in df.columns:
            c_low = col.lower()
            if "autoconsumo" in c_low or "self-consumption" in c_low or "self_consumption" in c_low:
                self_cons_col = col
                break

        # Drop rows where timestamp is NaN
        clean_df = df.dropna(subset=[ts_col]).copy()

        # Clean timestamps: remove ' DST' suffix and normalize whitespace
        timestamps = clean_df[ts_col].astype(str).str.replace(" DST", "", regex=False).str.strip()

        # Parse generation values
        gen_values = pd.to_numeric(clean_df[gen_col], errors="coerce").fillna(0.0)

        data_dict: dict[str, object] = {
            "timestamp": timestamps,
            "generation_kwh": gen_values,
        }
        if cons_col:
            cons_values = pd.to_numeric(
                clean_df[cons_col].astype(str).str.replace(",", "."), errors="coerce"
            )
            data_dict["consumption_kwh"] = cons_values
        if self_cons_col:
            self_cons_values = pd.to_numeric(
                clean_df[self_cons_col].astype(str).str.replace(",", "."), errors="coerce"
            ).fillna(0.0)
            data_dict["self_consumption_kwh"] = self_cons_values

        result_df = pd.DataFrame(data_dict)

        # Filter out header or invalid timestamp rows
        valid_mask = result_df["timestamp"].str.match(r"^\d{4}-\d{2}-\d{2}")
        result_df = result_df[valid_mask]

        return result_df

    def load_all(self) -> pd.DataFrame:
        """Load, validate, and deduplicate all generation reports in the directory.

        Returns:
            DataFrame with columns ['timestamp', 'generation_kwh'] (and optionally
            'consumption_kwh' and 'self_consumption_kwh' if present in the reports) sorted chronologically.
        """
        files = self.discover_files()
        dfs = []
        for f in files:
            dfs.append(self.parse_file(f))

        combined = pd.concat(dfs, ignore_index=True)

        # Deduplicate timestamps across overlapping reports, keeping max values
        agg_rules: dict[str, str] = {"generation_kwh": "max"}
        if "consumption_kwh" in combined.columns:
            agg_rules["consumption_kwh"] = "max"
        if "self_consumption_kwh" in combined.columns:
            agg_rules["self_consumption_kwh"] = "max"

        combined = (
            combined.groupby("timestamp", as_index=False)
            .agg(agg_rules)
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        return combined


# Generic alias for solar inverter generation loader
SolarGenerationLoader = HuaweiGenerationLoader
