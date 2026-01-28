"""
Parse cheque data from attachment and create cheque_number → payee mapping.
Apply overrides: TREDD → IFS, WELCOME WAGON → ADVERTISING
"""
import re

# The attachment data (cleaned from image)
cheque_data = """
243	CIBC 0228362	2012-04-05	279.78	Cheque #243
1	CIBC 0228362	2012-07-09	1870.14	CHQ 1
4	CIBC 0228362	2012-07-13	840.95	CHQ 4
3	CIBC 0228362	2012-07-13	2000.00	CHQ 3
7	CIBC 0228362	2012-07-17	100.00	CHQ 7
6	CIBC 0228362	2012-07-17	400.00	CHQ 6
2	CIBC 0228362	2012-07-18	489.20	CHQ 2
8	CIBC 0228362	2012-07-19	2000.00	CHQ 8
11	CIBC 0228362	2012-07-23	3000.00	CHQ 11
9	CIBC 0228362	2012-07-23	1885.65	CHQ 9
15	CIBC 0228362	2012-08-01	1511.17	CHQ 15
12	CIBC 0228362	2012-08-01	3071.04	CHQ 12
14	CIBC 0228362	2012-08-07	599.06	CHQ 14
16	CIBC 0228362	2012-08-08	2088.59	CHQ 16
18	CIBC 0228362	2012-08-09	1207.50	CHQ 18
21	CIBC 0228362	2012-08-10	1000.00	CHQ 21
19	CIBC 0228362	2012-08-10	827.48	CHQ 19
20	CIBC 0228362	2012-08-10	155.00	CHQ 20
13	CIBC 0228362	2012-08-10	3086.58	CHQ 13
000000005114475	CIBC 0228362	2012-08-10	300.00	Cheque 000000005114475
"""

# Extract the data
cheque_mapping = {}
for line in cheque_data.strip().split('\n'):
    parts = line.split('\t')
    if len(parts) >= 2:
        cheque_num = parts[0].strip()
        cheque_mapping[cheque_num] = f"Cheque {cheque_num}"

print("Extracted cheque mapping from attachment:")
for chq_num in sorted(cheque_mapping.keys()):
    print(f"  {chq_num}: {cheque_mapping[chq_num]}")

print(f"\nTotal cheques from attachment: {len(cheque_mapping)}")
