"""Modelo del AFN (estados, transiciones ε, simulación y recorrido)."""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
