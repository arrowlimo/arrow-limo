from datetime import date
from modern_backend.app.tax.t2_data_extraction import T2DataExtractor

ext = T2DataExtractor({'dbname':'almsdata','user':'postgres','password':'ArrowLimousine','host':'localhost'})
p = ext.extract_complete_financial_package(2025, date(2025,12,31))
print('by_gl_code rows:', len(p['deductibility']['by_gl_code']))
print('audit warnings:', len(p['deductibility']['audit_warnings']))
print('total_book_expense:', p['deductibility']['total_book_expense'])
print('total_deductible_expenses:', p['deductibility']['total_deductible_expenses'])
print('total_add_back:', p['deductibility']['total_add_back'])
