"""Test T4 regex patterns against sample text"""
import re

sample_text = """14 22
4279.60 709.93
Payroll Account Number (15 characters) Province of employment Employee's CPP contributions (cid
:150) line 308 EI insurable earnings
NumØro de compte de retenues (15 caractŁres) Province d'emploi Cotisations de l'employØ au RPC 
(cid:150) ligne 308 Gains assurables d'AE
54 10 16 24
861556827RP0001 AB 189.25 4279.60
Social insurance number Exempt (cid:150) Exemption Employment Code Employee's QPP contributions
 (cid:150) line 308 CPP(cid:150)QPP pensionable earnings
NumØro d'assurance sociale CPP (cid:150) QPP EI PPIP Code d'emploi Cotisations de l'employØ au 
RRQ (cid:150) ligne 308 Gains ouvrant droit (cid:224) pension (cid:150) RPC(cid:150)RRQ
12 28 29 17 26
627 754 336 4279.60
RPC (cid:150) RRQ AE RPAP Employee's EI premiums (cid:150) line 312 Union dues (cid:150) line 2
12
Cotisations de l'employØ Æ l'AE (cid:150) ligne 312 Cotisations syndicales (cid:150) ligne 212 
Employee's name and address (cid:150) Nom et adresse de l'employØ
18 44
78.31"""

# Original pattern
pattern_14 = r"\b14\s+(\d{1,10}\.\d{2})"
matches = re.findall(pattern_14, sample_text)
print(f"Box 14 pattern matches: {matches}")

# The issue: box numbers and amounts are on DIFFERENT LINES
# Box 14 value is 4279.60, but it appears AFTER 14 on the next line

# Better pattern - look for 14 then grab next number
pattern_14_fixed = r"14[\s\S]{0,50}?(\d{1,10}\.\d{2})"
matches = re.findall(pattern_14_fixed, sample_text)
print(f"Box 14 (fixed) matches: {matches}")

# Test SIN pattern
sin_pattern = r"(\d{3}\s+\d{3}\s+\d{3})"
sin_matches = re.findall(sin_pattern, sample_text)
print(f"SIN matches: {sin_matches}")

# Better - the actual SIN format in the PDF (no spaces in extracted text)
sin_pattern2 = r"(\d{9})"
sin_matches2 = re.findall(sin_pattern2, sample_text)
print(f"SIN matches (no spaces): {sin_matches2}")
