#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Helper script to prepare Astro-Databank data for Solar Fire import.
# Copyright (C) 2025 [Your Name/Institution]

"""
This script automates the "Data Preparation" step described in the
supplementary material. It takes a raw, tab-delimited export from the
Astro-Databank (ADB) website and converts it into a Comma Quote Delimited (CQD)
text file suitable for import into the Solar Fire astrology software.

Key Operations:
1.  Parses raw lines to extract Name, Date, Time, and the Chart URL.
2.  Transforms names from 'Last, First' to 'First Last' format.
3.  Transforms dates from 'YYYY-MM-DD' to 'DD Month YYYY' format.
4.  Parses the complex Chart URL to extract:
    - Place, Country, Latitude, Longitude, and Time Zone Code.
5.  Implements the logic to convert the Time Zone Code into the required
    'Zone Abbreviation' ('...' or 'LMT') and 'Zone Time' (e.g., '05:00').
6.  Assembles the final record in the precise CQD format required by Solar Fire.
"""

import argparse
import csv
import os
import re
from datetime import datetime
import logging
import sys
from urllib.parse import urlparse, parse_qs

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# --- Helper Functions ---
def load_country_codes(filepath: str) -> dict:
    """Loads the country conversion table from a CSV file."""
    conversion_table = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader) # Skip header
            if header != ['Abbreviation', 'Country']:
                 logging.warning(f"Unexpected header in {filepath}. Expected 'Abbreviation,Country'.")
            for row in reader:
                if len(row) == 2:
                    abbreviation, country = row
                    conversion_table[abbreviation.strip()] = country.strip()
    except FileNotFoundError:
        logging.error(f"Country codes file not found at: {filepath}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading country codes file {filepath}: {e}")
        sys.exit(1)
    return conversion_table

def convert_hours_to_hhmm(decimal_hours: float) -> str:
    """Converts decimal hours to a HH:MM string, handling the sign."""
    sign = "" if decimal_hours >= 0 else "-"
    decimal_hours = abs(decimal_hours)
    
    hours = int(decimal_hours)
    minutes = round((decimal_hours * 60) % 60)
    
    return f"{sign}{hours:02d}:{minutes:02d}"

def parse_tz_code(tz_code: str) -> tuple[str, str]:
    """
    Converts a Time Zone Code into Zone Abbreviation and Zone Time.
    For 'm' type, it uses the longitude embedded in the TZC itself.
    """
    if not tz_code:
        raise ValueError("Time Zone Code is empty.")

    prefix = tz_code[0]
    
    if prefix == 'h': # Standard time zone, e.g., 'h5w'
        zone_abbr = "..."
        match = re.match(r"h(\d+)([we])(\d*)", tz_code.lower())
        if not match:
            raise ValueError(f"Invalid 'h' type TZC: {tz_code}")
        
        hours, direction, minutes = match.groups()
        minutes = int(minutes) if minutes else 0
        
        sign = "" if direction == 'w' else "-"
        zone_time = f"{sign}{int(hours):02d}:{minutes:02d}"
        
    elif prefix == 'm': # Local Mean Time
        zone_abbr = "LMT"
        match = re.match(r"m(\d+)([we])(\d*)", tz_code.lower())
        if not match:
            raise ValueError(f"Invalid 'm' type TZC: {tz_code}")

        degrees, direction, minutes = match.groups()
        decimal_degrees = float(degrees) + (float(minutes) / 60.0 if minutes else 0)
        
        if direction == 'e':
            decimal_degrees *= -1
            
        decimal_hours = decimal_degrees / 15.0
        zone_time = convert_hours_to_hhmm(decimal_hours)
        
    else:
        raise ValueError(f"Unknown TZC prefix '{prefix}' in code: {tz_code}")
        
    return zone_abbr, zone_time

def process_adb_line(line: str, conversion_table: dict) -> list | None:
    """Processes a single raw line from the filtered ADB export."""
    try:
        # The input file is cleanly tab-delimited from the previous script.
        parts = line.strip().split('\t')
        if len(parts) < 7:
            logging.warning(f"Skipping line with insufficient columns: {line[:80]}...")
            return None

        # 1. Extract and clean data fields
        raw_name = parts[1]
        date_str = parts[3]
        time_str = parts[4]
        # The chart URL may or may not have parentheses depending on whitespace
        chart_url = parts[5].strip("()")

        # 2. Transform Name
        if ',' in raw_name:
            name_parts = raw_name.split(',', 1)
            last_name = name_parts[0].strip()
            first_name = name_parts[1].strip()
            full_name = f"{first_name} {last_name}"
        else:
            full_name = raw_name.strip() # Handle single names

        # 3. Transform Date
        formatted_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d %B %Y")
        
        # 4. Parse Chart URL for geographic data
        parsed_url = urlparse(chart_url)
        # Correct for non-standard semicolon separators in the query string
        corrected_query = parsed_url.query.replace(';', '&')
        query_params = parse_qs(corrected_query)
        
        nd1 = query_params.get('nd1', [''])[0]
        nd1_parts = nd1.split(',')

        # This is the direct implementation of the instructions, wrapped in a
        # try-except block to gracefully handle malformed URLs.
        try:
            tz_code = nd1_parts[-11]
            place = nd1_parts[-8]
            country_raw = nd1_parts[-7]
            longitude = nd1_parts[-6]
            latitude = nd1_parts[-5]

        except IndexError:
            logging.warning(f"Skipping line due to malformed URL (nd1 parameter is too short): {line[:80]}...")
            return None

        country = conversion_table.get(country_raw, country_raw)

        # Use the comprehensive conversion table for the country name.
        # Fall back to the original text if the abbreviation is not found.
        country = conversion_table.get(country_raw, country_raw)
        
        # 5. Convert Time Zone Code
        zone_abbr, zone_time = parse_tz_code(tz_code)

        # 6. Assemble final record
        # Format: Name, Date, Time, Zone Abbreviation, Zone Time, Place, Country, Latitude, Longitude
        return [
            full_name, formatted_date, time_str, zone_abbr, zone_time,
            place, country, latitude.upper(), longitude.upper()
        ]

    except (IndexError, ValueError) as e:
        logging.error(f"Failed to process line due to error: {e}. Line: {line[:80]}...")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}. Line: {line[:80]}...")
        return None


def main(input_file: str, output_file: str, country_codes_file: str):
    """
    Main function to read ADB data, process it, and write the SF import file.
    """
    logging.info(f"Loading country codes from: {country_codes_file}")
    country_conversion_table = load_country_codes(country_codes_file)

    logging.info(f"Reading raw ADB data from: {input_file}")
    logging.info(f"Will write Solar Fire import file to: {output_file}")
    
    processed_records = []
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            # The input file from filter_adb_candidates.py has no header
            for line in infile:
                if not line.strip():
                    continue
                record = process_adb_line(line, country_conversion_table)
                if record:
                    processed_records.append(record)
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}")
        sys.exit(1)

    if not processed_records:
        logging.error("No valid records were processed. Output file will not be created.")
        sys.exit(1)
        
    try:
        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile, quoting=csv.QUOTE_ALL)
            writer.writerows(processed_records)
        logging.info(f"Successfully wrote {len(processed_records)} records to {output_file}.")
    except IOError as e:
        logging.error(f"Failed to write to output file {output_file}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare Astro-Databank (ADB) export for Solar Fire import.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-i", "--input-file",
        default="data/adb_filtered_5000.txt",
        help="Path to the raw, tab-delimited file exported from ADB."
    )
    parser.add_argument(
        "-o", "--output-file",
        default="data/sources/sf_data_import.txt",
        help="Path to write the final CQD-formatted output file."
    )
    parser.add_argument(
        "-c", "--country-codes-file",
        default="data/country_codes.csv",
        help="Path to the country codes conversion CSV file."
    )
    args = parser.parse_args()
    
    main(args.input_file, args.output_file, args.country_codes_file)
