"""Huawei FusionSolar PV generation Excel report parser and loader."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.csv_utils import clean_numeric_series, is_autumn_dst_date
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

        # Locate export column if present (e.g. 'Energía exportada (kWh)', 'Exported energy (kWh)')
        exp_col = None
        for col in df.columns:
            c_low = col.lower()
            if (
                ("exportada" in c_low or "exported" in c_low or "export" in c_low)
                and "pérdida" not in c_low
                and "perdida" not in c_low
            ):
                exp_col = col
                break

        # Locate import column if present (e.g. 'Importación (kWh)', 'Importacion (kWh)', 'Imported energy (kWh)')
        imp_col = None
        for col in df.columns:
            c_low = col.lower()
            if (
                "importación" in c_low
                or "importacion" in c_low
                or "imported" in c_low
                or "import" in c_low
            ):
                imp_col = col
                break

        # Drop rows where timestamp is NaN
        clean_df = df.dropna(subset=[ts_col]).copy()

        # Clean timestamps: remove ' DST' suffix and normalize whitespace
        timestamps = clean_df[ts_col].astype(str).str.replace(" DST", "", regex=False).str.strip()

        # Parse generation values
        gen_values = clean_numeric_series(clean_df[gen_col], fill_na=0.0)

        cons_values = clean_numeric_series(clean_df[cons_col]) if cons_col else None
        self_cons_values = (
            clean_numeric_series(clean_df[self_cons_col], fill_na=0.0) if self_cons_col else None
        )
        exp_values = clean_numeric_series(clean_df[exp_col], fill_na=0.0) if exp_col else None
        imp_values = clean_numeric_series(clean_df[imp_col], fill_na=0.0) if imp_col else None

        # Sanitize corrupted partial-outage telemetry hours where reported PV generation
        # is physically less than exported energy (inverter yield dropout mid-hour).
        if exp_values is not None:
            corrupted_mask = (gen_values + 1e-4) < exp_values
            if corrupted_mask.any():
                gen_values = gen_values.mask(corrupted_mask, 0.0)
                if cons_values is not None:
                    cons_values = cons_values.mask(corrupted_mask, float("nan"))
                if self_cons_values is not None:
                    self_cons_values = self_cons_values.mask(corrupted_mask, 0.0)

        data_dict: dict[str, object] = {
            "timestamp": timestamps,
            "generation_kwh": gen_values,
        }
        if cons_values is not None:
            data_dict["consumption_kwh"] = cons_values
        if self_cons_values is not None:
            data_dict["self_consumption_kwh"] = self_cons_values
        if exp_values is not None:
            data_dict["exported_energy_kwh"] = exp_values
        if imp_values is not None:
            data_dict["imported_energy_kwh"] = imp_values

        result_df = pd.DataFrame(data_dict)

        # Filter out header or invalid timestamp rows
        valid_mask = result_df["timestamp"].str.match(r"^\d{4}-\d{2}-\d{2}")
        result_df = result_df[valid_mask]

        return result_df

    @staticmethod
    def consolidate_autumn_dst(df: pd.DataFrame) -> pd.DataFrame:
        """Sum the repeated 02:00 interval on 25-hour European autumn DST days within a single file."""
        if df.empty or "timestamp" not in df.columns:
            return df

        ts_str = df["timestamp"].astype(str)
        is_oct_02 = ts_str.str.slice(5, 7).eq("10") & ts_str.str.endswith(" 02:00:00")
        if not is_oct_02.any():
            return df

        dates = ts_str.str.slice(0, 10)
        ts_counts = df.groupby("timestamp", sort=False)["generation_kwh"].transform("size")
        day_counts = (
            df.assign(_d=dates).groupby("_d", sort=False)["generation_kwh"].transform("size")
        )
        dst_dates = {str(d) for d in dates[is_oct_02].unique() if is_autumn_dst_date(str(d))}
        dst_mask = is_oct_02 & (ts_counts == 2) & (dates.isin(dst_dates) | (day_counts == 25))
        if not dst_mask.any():
            return df

        energy_cols = [
            col
            for col in (
                "generation_kwh",
                "consumption_kwh",
                "self_consumption_kwh",
                "exported_energy_kwh",
                "imported_energy_kwh",
            )
            if col in df.columns
        ]
        non_dst = df.loc[~dst_mask]
        dst_summed = (
            df.loc[dst_mask]
            .groupby("timestamp", as_index=False, sort=False)[energy_cols]
            .sum(min_count=1)
        )
        return pd.concat([non_dst, dst_summed], ignore_index=True)[df.columns]

    def load_all(self) -> pd.DataFrame:
        """Load, validate, and deduplicate all generation reports in the directory.

        Returns:
            DataFrame with columns ['timestamp', 'generation_kwh'] (and optionally
            'consumption_kwh', 'self_consumption_kwh', 'exported_energy_kwh', 'imported_energy_kwh'
            if present in the reports) sorted chronologically.
        """
        files = self.discover_files()
        dfs = [self.consolidate_autumn_dst(self.parse_file(f)) for f in files]

        combined = pd.concat(dfs, ignore_index=True)

        # Deduplicate timestamps across overlapping reports, keeping max values
        agg_rules: dict[str, str] = {"generation_kwh": "max"}
        if "consumption_kwh" in combined.columns:
            agg_rules["consumption_kwh"] = "max"
        if "self_consumption_kwh" in combined.columns:
            agg_rules["self_consumption_kwh"] = "max"
        if "exported_energy_kwh" in combined.columns:
            agg_rules["exported_energy_kwh"] = "max"
        if "imported_energy_kwh" in combined.columns:
            agg_rules["imported_energy_kwh"] = "max"

        combined = (
            combined.groupby("timestamp", as_index=False)
            .agg(agg_rules)
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        return combined
