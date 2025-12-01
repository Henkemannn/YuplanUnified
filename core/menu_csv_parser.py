"""CSV menu parser for Admin Phase 8.

Expected CSV format (with header):
Year,Week,Weekday,Meal,Alt,Text

Example:
2025,49,Måndag,Lunch,Alt1,Köttbullar med potatis
2025,49,Måndag,Lunch,Alt2,Fiskgratäng
2025,49,Måndag,Lunch,Dessert,Glass
2025,49,Måndag,Kvällsmat,,Smörgåsar

Meal values: Lunch, Kvällsmat, Dessert (case-insensitive)
Alt values: Alt1, Alt2, or empty (defaults to main)
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import IO


@dataclass
class MenuCSVRow:
    """Single row from parsed CSV menu."""
    year: int
    week: int
    weekday: str  # Måndag, Tisdag, etc. or Mon, Tue, etc.
    meal: str  # Lunch, Kvällsmat, Dessert
    alt: str  # Alt1, Alt2, or empty
    text: str  # Dish name/description


class MenuCSVParseError(Exception):
    """Raised when CSV format is invalid."""
    pass


def parse_menu_csv(file_stream: IO[bytes]) -> list[MenuCSVRow]:
    """Parse uploaded CSV file into structured menu rows.
    
    Args:
        file_stream: Binary file stream from uploaded CSV
        
    Returns:
        List of MenuCSVRow objects
        
    Raises:
        MenuCSVParseError: If CSV format is invalid
    """
    try:
        # Read as text with UTF-8 encoding (handle BOM)
        text_stream = io.TextIOWrapper(file_stream, encoding='utf-8-sig')
        reader = csv.DictReader(text_stream)
        
        rows = []
        for idx, row in enumerate(reader, start=1):
            try:
                # Normalize keys (case-insensitive, strip whitespace)
                normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                
                # Extract fields with fallback column names
                year_str = normalized.get('year') or normalized.get('år') or ''
                week_str = normalized.get('week') or normalized.get('vecka') or normalized.get('uke') or ''
                weekday = normalized.get('weekday') or normalized.get('dag') or normalized.get('day') or ''
                meal = normalized.get('meal') or normalized.get('måltid') or normalized.get('maltid') or ''
                alt = normalized.get('alt') or normalized.get('variant') or ''
                text = normalized.get('text') or normalized.get('dish') or normalized.get('rett') or normalized.get('rätt') or ''
                
                # Validate required fields
                if not (year_str and week_str and weekday and meal and text):
                    # Skip empty rows
                    if not any([year_str, week_str, weekday, meal, text]):
                        continue
                    raise MenuCSVParseError(
                        f"Rad {idx}: Saknar obligatoriska fält (Year, Week, Weekday, Meal, Text)"
                    )
                
                # Convert year/week to int
                try:
                    year = int(year_str)
                    week = int(week_str)
                except ValueError:
                    raise MenuCSVParseError(
                        f"Rad {idx}: Year och Week måste vara heltal (year={year_str}, week={week_str})"
                    )
                
                # Validate week range
                if not (1 <= week <= 53):
                    raise MenuCSVParseError(f"Rad {idx}: Week måste vara mellan 1 och 53 (fick {week})")
                
                rows.append(MenuCSVRow(
                    year=year,
                    week=week,
                    weekday=weekday.capitalize(),
                    meal=meal.capitalize(),
                    alt=alt.capitalize() if alt else '',
                    text=text
                ))
                
            except MenuCSVParseError:
                raise
            except Exception as e:
                raise MenuCSVParseError(f"Rad {idx}: Kunde inte parsa ({e})")
        
        if not rows:
            raise MenuCSVParseError("CSV-filen är tom eller innehåller ingen giltig data")
        
        return rows
        
    except csv.Error as e:
        raise MenuCSVParseError(f"Ogiltigt CSV-format: {e}")
    except UnicodeDecodeError:
        raise MenuCSVParseError("Filkodning stöds inte. Använd UTF-8.")


def csv_rows_to_import_result(rows: list[MenuCSVRow]):
    """Convert CSV rows to MenuImportResult structure for MenuImportService.
    
    Maps CSV meal/alt combinations to menu model's day/meal/variant_type:
    - Lunch + Alt1 -> meal="Lunch", variant_type="alt1"
    - Lunch + Alt2 -> meal="Lunch", variant_type="alt2"
    - Lunch + Dessert or meal=Dessert -> meal="Lunch", variant_type="dessert"
    - Kvällsmat -> meal="Kväll", variant_type="main" or "kvall"
    """
    from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport
    from collections import defaultdict
    
    # Group by (year, week)
    by_week: dict[tuple[int, int], list[MenuCSVRow]] = defaultdict(list)
    for row in rows:
        by_week[(row.year, row.week)].append(row)
    
    weeks = []
    for (year, week), week_rows in sorted(by_week.items()):
        items = []
        for row in week_rows:
            # Map Swedish weekday names to English lowercase for menu model
            weekday_map = {
                'Måndag': 'monday', 'Mon': 'monday',
                'Tisdag': 'tuesday', 'Tue': 'tuesday',
                'Onsdag': 'wednesday', 'Wed': 'wednesday',
                'Torsdag': 'thursday', 'Thu': 'thursday',
                'Fredag': 'friday', 'Fri': 'friday',
                'Lördag': 'saturday', 'Sat': 'saturday',
                'Söndag': 'sunday', 'Sun': 'sunday',
            }
            day = weekday_map.get(row.weekday, row.weekday.lower())
            
            # Map meal to menu model structure
            meal_lower = row.meal.lower()
            if meal_lower in ['lunch', 'lunsj', 'lun']:
                meal = 'Lunch'
                # Determine variant based on Alt column
                if row.alt.lower() in ['alt1', '1', 'alternativ1']:
                    variant_type = 'alt1'
                elif row.alt.lower() in ['alt2', '2', 'alternativ2']:
                    variant_type = 'alt2'
                elif row.alt.lower() in ['dessert', 'efterrätt', 'desert']:
                    variant_type = 'dessert'
                elif meal_lower == 'dessert':
                    variant_type = 'dessert'
                else:
                    variant_type = 'alt1'  # Default to alt1 if no alt specified
            elif meal_lower in ['kvällsmat', 'kvallsmat', 'kväll', 'kvall', 'middag', 'dinner']:
                meal = 'Kväll'
                variant_type = 'kvall'
            elif meal_lower in ['dessert', 'efterrätt', 'desert']:
                meal = 'Lunch'
                variant_type = 'dessert'
            else:
                # Unknown meal type, default to Lunch/alt1
                meal = 'Lunch'
                variant_type = 'alt1'
            
            items.append(ImportedMenuItem(
                day=day,
                meal=meal,
                variant_type=variant_type,
                dish_name=row.text,
                category=None,
                source_labels=[f"CSV import {year}-W{week}"]
            ))
        
        weeks.append(WeekImport(year=year, week=week, items=items))
    
    return MenuImportResult(weeks=weeks, warnings=[], errors=[])
