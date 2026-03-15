"""
T2 Corporation Income Tax Return Generation Module

This module handles:
- Financial data extraction from ALMS database
- T2 schedule calculations
- PDF form filling
- Supporting document generation
"""

from .t2_data_extraction import T2DataExtractor

__all__ = ['T2DataExtractor']
