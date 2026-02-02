// Enhanced Report Export Utilities for Vue Frontend
// Provides CSV, Excel, PDF export with subtotals and group headers

export function exportToCSV(data, headers, filename = 'report.csv') {
  const csvContent = [
    headers.join(','),
    ...data.map(row => headers.map(h => {
      const value = row[h.key || h] || '';
      // Escape values with commas or quotes
      return typeof value === 'string' && (value.includes(',') || value.includes('"'))
        ? `"${value.replaceAll('"', '""')}"`
        : value;
    }).join(','))
  ].join('\n');

  downloadFile(csvContent, filename, 'text/csv;charset=utf-8;');
}

export function exportToExcel(data, headers, filename = 'report.xlsx', options = {}) {
  // This requires xlsx library: npm install xlsx
  try {
    const XLSX = require('xlsx');
    
    // Create workbook
    const wb = XLSX.utils.book_new();
    
    // Prepare data with headers
    const wsData = [
      headers.map(h => h.header || h),
      ...data.map(row => headers.map(h => row[h.key || h] || ''))
    ];
    
    // Add subtotals if grouped
    if (options.groupBy) {
      wsData.push(...calculateSubtotals(data, headers, options.groupBy));
    }
    
    // Add totals row
    if (options.totals) {
      const totalsRow = headers.map((h, idx) => {
        if (idx === 0) return 'TOTAL:';
        const key = h.key || h;
        const sum = data.reduce((acc, row) => {
          const val = Number.parseFloat(row[key]);
          return Number.isNaN(val) ? acc : acc + val;
        }, 0);
        return sum > 0 ? sum : '';
      });
      wsData.push(totalsRow);
    }
    
    // Create worksheet
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    
    // Style header row (if supported)
    const range = XLSX.utils.decode_range(ws['!ref']);
    for (let C = range.s.c; C <= range.e.c; ++C) {
      const address = XLSX.utils.encode_col(C) + "1";
      if (!ws[address]) continue;
      ws[address].s = {
        font: { bold: true, color: { rgb: "FFFFFF" } },
        fill: { fgColor: { rgb: "366092" } },
        alignment: { horizontal: "center", vertical: "center" }
      };
    }
    
    // Auto-fit columns
    const colWidths = headers.map((h, idx) => {
      const maxLen = Math.max(
        h.header?.length || 0,
        ...data.map(row => String(row[h.key || h] || '').length)
      );
      return { wch: Math.min(maxLen + 2, 50) };
    });
    ws['!cols'] = colWidths;
    
    XLSX.utils.book_append_sheet(wb, ws, options.sheetName || 'Report');
    
    // Generate buffer
    const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
    downloadFile(
      new Blob([wbout], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
      filename
    );
    
    return true;
  } catch (error) {
    console.error('Excel export failed:', error);
    alert('Excel export requires xlsx library: npm install xlsx');
    return false;
  }
}

export function exportToPDF(data, headers, filename = 'report.pdf', options = {}) {
  // This requires jspdf and jspdf-autotable: npm install jspdf jspdf-autotable
  try {
    const { jsPDF } = require('jspdf');
    require('jspdf-autotable');
    
    const doc = new jsPDF({
      orientation: options.orientation || 'landscape',
      unit: 'mm',
      format: 'letter'
    });
    
    // Title
    doc.setFontSize(16);
    doc.text(options.title || 'Report', 14, 15);
    
    // Timestamp
    doc.setFontSize(10);
    doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 22);
    
    // Prepare table data
    const tableData = data.map(row => 
      headers.map(h => row[h.key || h] || '')
    );
    
    // Add table
    doc.autoTable({
      startY: 28,
      head: [headers.map(h => h.header || h)],
      body: tableData,
      headStyles: {
        fillColor: [54, 96, 146],
        textColor: [255, 255, 255],
        fontStyle: 'bold'
      },
      alternateRowStyles: {
        fillColor: [242, 242, 242]
      },
      margin: { top: 28 }
    });
    
    // Add totals if requested
    if (options.totals) {
      const finalY = doc.lastAutoTable.finalY + 5;
      doc.setFontSize(10);
      doc.setFont(undefined, 'bold');
      
      headers.forEach((h, idx) => {
        const key = h.key || h;
        const sum = data.reduce((acc, row) => {
          const val = Number.parseFloat(row[key]);
          return Number.isNaN(val) ? acc : acc + val;
        }, 0);
        
        if (sum > 0) {
          doc.text(`${h.header || h}: $${sum.toFixed(2)}`, 14 + (idx * 40), finalY);
        }
      });
    }
    
    doc.save(filename);
    return true;
  } catch (error) {
    console.error('PDF export failed:', error);
    alert('PDF export requires jspdf and jspdf-autotable: npm install jspdf jspdf-autotable');
    return false;
  }
}

export function printReport(data, headers, title = 'Report') {
  const printWindow = window.open('', '_blank');
  if (!printWindow) {
    alert('Popup blocked. Please allow popups to print the report.');
    return;
  }

  const doc = printWindow.document;
  doc.title = title;
  doc.head.innerHTML = `
      <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; border-bottom: 2px solid #366092; padding-bottom: 10px; }
        .meta { color: #666; font-size: 12px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th { background-color: #366092; color: white; padding: 12px; text-align: left; font-weight: bold; }
        td { padding: 8px; border: 1px solid #ddd; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .total-row { background-color: #d9e9f7; font-weight: bold; }
        @media print {
          .no-print { display: none; }
        }
      </style>
  `;
  doc.body.innerHTML = `
      <h1>${title}</h1>
      <div class="meta">Generated: ${new Date().toLocaleString()}</div>
      <button class="no-print" onclick="window.print()">Print</button>
      <button class="no-print" onclick="window.close()">Close</button>
      <table>
        <thead>
          <tr>${headers.map(h => `<th>${h.header || h}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${data.map(row => `
            <tr>${headers.map(h => `<td>${row[h.key || h] || ''}</td>`).join('')}</tr>
          `).join('')}
          <tr class="total-row">
            <td><strong>TOTALS:</strong></td>
            ${headers.slice(1).map(h => {
              const key = h.key || h;
              const sum = data.reduce((acc, row) => {
                const val = Number.parseFloat(row[key]);
                return Number.isNaN(val) ? acc : acc + val;
              }, 0);
              return sum > 0 ? `<td><strong>$${sum.toFixed(2)}</strong></td>` : '<td></td>';
            }).join('')}
          </tr>
        </tbody>
      </table>
  `;
}

// Helper function to download files
function downloadFile(content, filename, mimeType = 'text/plain') {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Helper function to calculate subtotals by group
function calculateSubtotals(data, headers, groupByKey) {
  const groups = {};
  
  // Group data
  data.forEach(row => {
    const groupValue = row[groupByKey] || 'Ungrouped';
    if (!groups[groupValue]) {
      groups[groupValue] = [];
    }
    groups[groupValue].push(row);
  });
  
  // Calculate subtotals for each group
  const subtotalRows = [];
  Object.entries(groups).forEach(([groupName, groupRows]) => {
    const subtotalRow = headers.map((h, idx) => {
      if (idx === 0) return `${groupName} Subtotal:`;
      const key = h.key || h;
      const sum = groupRows.reduce((acc, row) => {
        const val = Number.parseFloat(row[key]);
        return Number.isNaN(val) ? acc : acc + val;
      }, 0);
      return sum > 0 ? sum : '';
    });
    subtotalRows.push(subtotalRow);
  });
  
  return subtotalRows;
}

export default {
  exportToCSV,
  exportToExcel,
  exportToPDF,
  printReport
};
