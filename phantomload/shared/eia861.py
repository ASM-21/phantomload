"""Loaders for the EIA-861 context files, 2016 to 2018.

The demand response schedule is one page of Form EIA-861. The same utilities
report their peak load, their meters, their direct load control customers, their
time-varying rate enrolment and their customer counts on other pages of the same
form, in the same year. Those pages are what the demand response figures can be
checked against without any outside source. See tools/build_eia861_context.py
for provenance and DATA.md section 8 for what each file holds.

Every loader returns numbers as floats with NaN where the source printed ".",
never zero, and utility numbers as strings so they join to the demand response
panel's keys.
"""

from __future__ import annotations

import functools
import pathlib

import pandas as pd

DATA = pathlib.Path(__file__).resolve().parents[2] / "data"

# Form EIA-861 instructions, Schedule 6 Part B, identical in the form approved
# through 3/31/2020 (reporting years 2017 to 2019) and the current form approved
# through 7/31/2029. Quoted, not paraphrased, because what the numerator measures
# decides what every ratio built on it means.
POTENTIAL_DEFINITION = (
    "Potential peak demand savings refers to the total demand savings that could "
    "occur at the time of the system peak hour assuming all demand response is called."
)
ACTUAL_DEFINITION = (
    "Actual peak demand savings is demand reduction actually achieved by demand "
    "response activities and is measured at the time of the company's annual "
    "system peak hour."
)
PEAK_DEFINITION = (
    "the maximum hourly summer load (for the months of June through September) "
    "based on net energy for the system"
)
INSTRUCTIONS_SOURCE = (
    "Form EIA-861 Instructions, Schedule 6 Part B (Demand Response Programs) and "
    "Schedule 2 Part A line 6; OMB No. 1905-0129, approvals expiring 3/31/2020 and "
    "7/31/2029, as archived in catalyst-cooperative/pudl, "
    "docs/data_sources/eia861/"
)

_ID = {"utility_number": str, "state": str, "ba_code": str}


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name, dtype=_ID, keep_default_na=False, na_values=[""])


@functools.lru_cache(maxsize=1)
def _peaks() -> pd.DataFrame:
    df = _read("eia861_peaks_2016_2018.csv")
    df["annual_peak_mw"] = df[["summer_peak_mw", "winter_peak_mw"]].max(axis=1)
    df["peak_season"] = (df.winter_peak_mw > df.summer_peak_mw).map(
        {True: "winter", False: "summer"}
    )
    return df


def peaks() -> pd.DataFrame:
    """One row per utility per year: summer, winter and annual peak, MW."""
    return _peaks().copy()


@functools.lru_cache(maxsize=1)
def _meters() -> pd.DataFrame:
    return _read("eia861_meters_2016_2018.csv")


def meters() -> pd.DataFrame:
    """AMI meters, all meters and customers with direct load control."""
    return _meters().copy()


@functools.lru_cache(maxsize=1)
def _dynamic_pricing() -> pd.DataFrame:
    return _read("eia861_dynamic_pricing_2017_2018.csv")


def dynamic_pricing() -> pd.DataFrame:
    """Customers enrolled in time-varying rates, 2017 and 2018."""
    return _dynamic_pricing().copy()


@functools.lru_cache(maxsize=1)
def _customers() -> pd.DataFrame:
    return _read("eia861_customers_2016_2018.csv")


def customers(retail_only: bool = True) -> pd.DataFrame:
    """Customer counts by class. Part B rows are energy-only sales by retail
    marketers whose customers are also counted by the delivery utility in part
    C, so they are dropped unless asked for. Texas is the exception the
    instructions name: its retail providers report bundled sales in part D and
    its delivery utilities report no customers, so each customer is counted
    once either way."""
    df = _customers().copy()
    return df[df.part != "B"] if retail_only else df


@functools.lru_cache(maxsize=1)
def _short_form() -> pd.DataFrame:
    return _read("eia861_short_form_2016_2018.csv")


def short_form() -> pd.DataFrame:
    """Utilities filing the abbreviated Form EIA-861S."""
    return _short_form().copy()


@functools.lru_cache(maxsize=1)
def _dr_class() -> pd.DataFrame:
    return _read("eia861_dr_utility_class_2016_2018.csv")


def demand_response_by_class() -> pd.DataFrame:
    """The demand response schedule by customer class, from the same release."""
    return _dr_class().copy()


def retail_choice_states() -> frozenset:
    """States where some customers buy energy from a supplier other than the
    utility that delivers it, read from the filings rather than assumed:
    energy-only sales (part B), delivery-only sales (part C), or bundled sales
    by energy service providers (part D), which the instructions say is
    typically Texas alone."""
    df = customers(retail_only=False)
    return frozenset(df[df.part.isin(["B", "C", "D"])].state.dropna().unique())
