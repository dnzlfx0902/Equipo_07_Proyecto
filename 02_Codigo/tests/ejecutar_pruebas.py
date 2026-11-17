"""Ejecuta los >=15 casos de prueba y genera la tabla P01..P15."""

import csv
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from rich.console import Console
from rich.table import Table
