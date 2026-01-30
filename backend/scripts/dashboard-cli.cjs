#!/usr/bin/env node
// Strict DB-backed CLI dashboard (no fake data)
// Queries common tables and prints key metrics and simple charts.

const { Pool } = require('pg');

// Auto-connect using environment variables for PowerShell compatibility
const cfg = {
  user: process.env.PGUSER || 'postgres',
  host: process.env.PGHOST || 'localhost',
  database: process.env.PGDATABASE || 'almsdata',
  password: process.env.PGPASSWORD || '***REDACTED***',
  port: Number(process.env.PGPORT || 5432),
  connectionTimeoutMillis: 3000,
  idleTimeoutMillis: 10000,
};

// If running in PowerShell, ensure environment variables are loaded
if (!process.env.PGUSER && process.env.USERNAME) {
  process.env.PGUSER = 'postgres';
}
if (!process.env.PGPASSWORD) {
  process.env.PGPASSWORD = '***REDACTED***';
}
if (!process.env.PGHOST) {
  process.env.PGHOST = 'localhost';
}
if (!process.env.PGDATABASE) {
  process.env.PGDATABASE = 'almsdata';
}
if (!process.env.PGPORT) {
  process.env.PGPORT = '5432';
}

const pool = new Pool(cfg);

const now = new Date();

function pad(s, n) { s = String(s); return s.length >= n ? s : s + ' '.repeat(n - s.length); }
function lpad(s, n) { s = String(s); return s.length >= n ? s : ' '.repeat(n - s.length) + s; }
function fmtNum(n) { return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Number(n||0)); }
function fmtMoney(n) { return new Intl.NumberFormat('en-US', { style:'currency', currency:'CAD', maximumFractionDigits: 0 }).format(Number(n||0)); }

async function tableExists(schema, table) {
  const r = await pool.query(
    `SELECT 1 FROM information_schema.tables WHERE table_schema = $1 AND table_name = $2`,
    [schema, table]
  );
  return r.rowCount > 0;
}

async function findFirstExistingTable(candidates) {
  for (const name of candidates) {
    const [schema, table] = name.includes('.') ? name.split('.') : ['public', name];
    try { if (await tableExists(schema, table)) return { schema, table, fq: `${schema}.${table}` }; } catch (_) {}
  }
  return null;
}

async function getCountFromTable(fq, where = 'TRUE') {
  const r = await pool.query(`SELECT COUNT(*)::int as c FROM ${fq} WHERE ${where}`);
  return r.rows[0]?.c || 0;
}

async function getDateColumn(fq, candidates) {
  const [schema, table] = fq.split('.');
  const r = await pool.query(
    `SELECT column_name FROM information_schema.columns WHERE table_schema=$1 AND table_name=$2`,
    [schema, table]
  );
  const cols = r.rows.map(x => x.column_name.toLowerCase());
  for (const c of candidates) if (cols.includes(c)) return c;
  return null;
}

async function getAmountColumn(fq, candidates) {
  const [schema, table] = fq.split('.');
  const r = await pool.query(
    `SELECT column_name FROM information_schema.columns WHERE table_schema=$1 AND table_name=$2`,
    [schema, table]
  );
  const cols = r.rows.map(x => x.column_name.toLowerCase());
  for (const c of candidates) if (cols.includes(c)) return c;
  return null;
}

function monthsBack(n) {
  const arr = [];
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  for (let i= n-1; i>=0; i--) {
    const dt = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth()-i, 1));
    arr.push({ key: dt.toISOString().slice(0,7), label: dt.toLocaleString('en-US', { month:'short', year:'2-digit' }) });
  }
  return arr;
}

function drawBarChart(pairs, width=40, fmt=fmtNum) {
  const maxVal = Math.max(1, ...pairs.map(p=>p.value));
  const lines = pairs.map(p => {
    const bar = '█'.repeat(Math.round((p.value / maxVal) * width));
    return `${pad(p.label, 6)} | ${bar} ${lpad(fmt(p.value), 8)}`;
  });
  return lines.join('\n');
}

// Simple sparkline for arrays of numbers
const SPARKS = ['▁','▂','▃','▄','▅','▆','▇','█'];
function sparkline(arr) {
  if (!arr || arr.length === 0) return '';
  const min = Math.min(...arr);
  const max = Math.max(...arr);
  const span = Math.max(1, max - min);
  return arr.map(v => {
    const idx = Math.min(7, Math.max(0, Math.round(((v - min) / span) * 7)));
    return SPARKS[idx];
  }).join('');
}

// Fuzzy date parsing: supports "jan 28", "28 january", "today", "tomorrow"
const MONTHS = ['january','february','march','april','may','june','july','august','september','october','november','december'];
function normalizeToken(s) { return String(s||'').toLowerCase().replace(/[^a-z]/g,''); }
function guessMonth(token) {
  const t = normalizeToken(token);
  if (!t) return null;
  // try exact start-with
  let idx = MONTHS.findIndex(m => m.startsWith(t.slice(0,3)));
  if (idx >= 0) return idx;
  // try contains
  idx = MONTHS.findIndex(m => m.includes(t));
  return idx >= 0 ? idx : null;
}
function parseFuzzyDate(s, ref = new Date()) {
  if (!s) return new Date(ref);
  const t = normalizeToken(s);
  if (t === 'today') return new Date(ref);
  if (t === 'tomorrow') { const d = new Date(ref); d.setDate(d.getDate()+1); return d; }
  if (t === 'yesterday') { const d = new Date(ref); d.setDate(d.getDate()-1); return d; }
  // patterns: jan 28, 28 jan, 28 january, january 28
  const parts = s.split(/\s+/).map(x=>x.trim()).filter(Boolean);
  let day = null, month = null, year = ref.getFullYear();
  for (const p of parts) {
    const num = Number(p.replace(/[^0-9]/g,''));
    if (num && num >= 1 && num <= 31 && day === null) { day = num; continue; }
    const m = guessMonth(p);
    if (m !== null && month === null) { month = m; continue; }
    if (!isNaN(Number(p)) && String(p).length === 4) { year = Number(p); }
  }
  if (month === null && day === null) return new Date(ref);
  if (month === null) month = ref.getMonth();
  if (day === null) day = 1;
  const d = new Date(Date.UTC(year, month, day));
  // if parsed date already passed far in the past, and no year specified, consider next year for future planning
  if (!parts.some(p => /\d{4}/.test(p)) && d < new Date(Date.UTC(ref.getFullYear(), ref.getMonth(), ref.getDate()))) {
    d.setUTCFullYear(ref.getUTCFullYear());
  }
  return d;
}

function startOfUTC(d, unit) {
  const x = new Date(d);
  if (unit === 'day') return new Date(Date.UTC(x.getUTCFullYear(), x.getUTCMonth(), x.getUTCDate()));
  if (unit === 'week') {
    const dow = (x.getUTCDay()+6)%7; // Monday=0
    const s = new Date(Date.UTC(x.getUTCFullYear(), x.getUTCMonth(), x.getUTCDate()));
    s.setUTCDate(s.getUTCDate()-dow); return s;
  }
  if (unit === 'month') return new Date(Date.UTC(x.getUTCFullYear(), x.getUTCMonth(), 1));
  if (unit === 'year') return new Date(Date.UTC(x.getUTCFullYear(), 0, 1));
  return x;
}
function addUTC(d, unit, n) {
  const x = new Date(d);
  if (unit === 'hour') { x.setUTCHours(x.getUTCHours()+n); return x; }
  if (unit === 'day') { x.setUTCDate(x.getUTCDate()+n); return x; }
  if (unit === 'week') { x.setUTCDate(x.getUTCDate()+n*7); return x; }
  if (unit === 'month') { x.setUTCMonth(x.getUTCMonth()+n); return x; }
  if (unit === 'year') { x.setUTCFullYear(x.getUTCFullYear()+n); return x; }
  return x;
}

async function getColumns(schemaTable) {
  const [schema, table] = schemaTable.split('.');
  const r = await pool.query(`SELECT column_name FROM information_schema.columns WHERE table_schema=$1 AND table_name=$2`, [schema, table]);
  return r.rows.map(x=>x.column_name);
}

async function loadBookingsRange(tbl, from, to) {
  const cols = await getColumns(tbl.fq);
  const lc = cols.map(c => c.toLowerCase());
  // date/time detection
  const dcol = lc.find(c => ['pickup_date','date','trip_date','created_at','start_time','start_at','startdate'].includes(c)) || lc.find(c=>c.includes('date'));
  const tcol = lc.find(c => ['pickup_time','time','start_time','start_at'].includes(c));
  const edcol = lc.find(c => ['dropoff_time','end_time','end_at','completed_at'].includes(c));
  const idcol = lc.includes('charter_id') ? 'charter_id' : (lc.includes('booking_id') ? 'booking_id' : (lc.includes('id') ? 'id' : cols[0]));
  const vehicleCol = lc.includes('vehicle_id') ? 'vehicle_id' : (lc.includes('vehicle') ? 'vehicle' : null);
  const driverCol = lc.includes('driver_id') ? 'driver_id' : (lc.includes('driver') ? 'driver' : null);

  if (!dcol) throw new Error('No date column detected in bookings/charters');
  const rangePred = `${dcol} >= $1 AND ${dcol} < $2`;
  const q = `SELECT ${idcol} as id, ${dcol} as d, ${tcol||'NULL'} as t, ${edcol||'NULL'} as t2, ${vehicleCol||'NULL'} as vehicle, ${driverCol||'NULL'} as driver FROM ${tbl.fq} WHERE ${rangePred}`;
  const r = await pool.query(q, [from.toISOString(), to.toISOString()]);
  // Map to times
  const items = r.rows.map(row => {
    const date = new Date(row.d);
    let start = new Date(date);
    if (row.t) {
      const tt = String(row.t);
      const m = /^(\d{1,2}):(\d{2})/.exec(tt);
      if (m) { start.setUTCHours(Number(m[1]), Number(m[2]), 0, 0); }
    }
    let end = row.t2 ? new Date(row.t2) : new Date(start);
    if (!row.t2) end = addUTC(start, 'hour', 2); // assume 2h if unknown
    return { id: row.id, start, end, vehicle: row.vehicle, driver: row.driver };
  });
  return items;
}

async function countTable(tblCandidates) {
  const t = await findFirstExistingTable(tblCandidates);
  if (!t) return { total: 0, table: null };
  const total = await getCountFromTable(t.fq);
  return { total, table: t };
}

function overlaps(aStart, aEnd, bStart, bEnd) {
  return aStart < bEnd && bStart < aEnd;
}

function renderDailyAvailability(items, totalDrivers, totalVehicles, dayStart) {
  const hours = Array.from({ length: 24 }, (_, h) => new Date(Date.UTC(dayStart.getUTCFullYear(), dayStart.getUTCMonth(), dayStart.getUTCDate(), h)));
  const bookingsPerHour = hours.map(h => items.filter(it => overlaps(it.start, it.end, h, addUTC(h,'hour',1))).length);
  const availDrivers = bookingsPerHour.map(c => Math.max(0, totalDrivers - c));
  const availVehicles = bookingsPerHour.map(c => Math.max(0, totalVehicles - c));
  console.log('\nDaily Availability (Drivers / Vehicles)');
  console.log('-'.repeat(60));
  console.log('Hours:       ', hours.map(h => String(h.getUTCHours()).padStart(2,'0')).join(' '));
  console.log('Drivers:     ', sparkline(availDrivers), `(min ${Math.min(...availDrivers)}, max ${Math.max(...availDrivers)})`);
  console.log('Vehicles:    ', sparkline(availVehicles), `(min ${Math.min(...availVehicles)}, max ${Math.max(...availVehicles)})`);
}

function renderMonthlyCalendar(items, monthStart) {
  const s = startOfUTC(monthStart, 'month');
  const next = addUTC(s, 'month', 1);
  const days = [];
  for (let d = new Date(s); d < next; d = addUTC(d,'day',1)) {
    const cnt = items.filter(it => overlaps(it.start, it.end, d, addUTC(d,'day',1))).length;
    days.push({ d: new Date(d), c: cnt });
  }
  console.log('\nMonthly Calendar (bookings per day)');
  console.log('-'.repeat(60));
  const firstDow = (s.getUTCDay()+6)%7; // Monday=0
  const labels = ['Mo','Tu','We','Th','Fr','Sa','Su'];
  console.log('     ', labels.join('  '));
  let line = '     ' + '   '.repeat(firstDow);
  for (let i=0;i<days.length;i++) {
    const dd = days[i];
    const dayNum = String(dd.d.getUTCDate()).padStart(2,'0');
    line += `${dayNum}${dd.c>0?`(${dd.c})`: '  '} `;
    if (((firstDow + i + 1) % 7) === 0) { console.log(line); line = '     '; }
  }
  if (line.trim()) console.log(line);
}

async function calendarView(opts) {
  const view = opts.view || 'daily';
  const dateStr = opts.date || null;
  const ref = parseFuzzyDate(dateStr, now);
  let from, to;
  if (view === 'hourly' || view === 'daily') {
    from = startOfUTC(ref, 'day');
    to = addUTC(from, 'day', 1);
  } else if (view === 'weekly') {
    from = startOfUTC(ref, 'week');
    to = addUTC(from, 'week', 1);
  } else if (view === 'monthly') {
    from = startOfUTC(ref, 'month');
    to = addUTC(from, 'month', 1);
  } else if (view === 'yearly') {
    from = startOfUTC(ref, 'year');
    to = addUTC(from, 'year', 1);
  } else {
    throw new Error(`Unknown view: ${view}`);
  }

  const vehiclesInfo = await countTable(['public.vehicles']);
  const driversInfo = await countTable(['public.employees','public.drivers']);
  const bookingsTbl = await findFirstExistingTable(['public.bookings','public.charters']);
  if (!bookingsTbl) throw new Error('No bookings/charters table found');
  const items = await loadBookingsRange(bookingsTbl, from, to);

  console.log(`\nCalendar View: ${view} | Range ${from.toISOString()} to ${to.toISOString()}`);
  console.log(`Bookings fetched: ${items.length} | Vehicles: ${vehiclesInfo.total} | Drivers: ${driversInfo.total}`);

  if (view === 'daily' || view === 'hourly') {
    renderDailyAvailability(items, driversInfo.total, vehiclesInfo.total, from);
  } else if (view === 'weekly') {
    // Aggregate per day
    const days = [];
    for (let d = new Date(from); d < to; d = addUTC(d,'day',1)) {
      const cnt = items.filter(it => overlaps(it.start, it.end, d, addUTC(d,'day',1))).length;
      days.push({ label: d.toISOString().slice(5,10), value: cnt });
    }
    console.log('\nWeekly Bookings');
    console.log('-'.repeat(60));
    console.log(drawBarChart(days, 30));
  } else if (view === 'monthly') {
    renderMonthlyCalendar(items, from);
  } else if (view === 'yearly') {
    const months = [];
    for (let m=0;m<12;m++) {
      const ms = new Date(Date.UTC(from.getUTCFullYear(), m, 1));
      const me = addUTC(ms,'month',1);
      const cnt = items.filter(it => overlaps(it.start, it.end, ms, me)).length;
      months.push({ label: ms.toLocaleString('en-US',{month:'short'}), value: cnt });
    }
    console.log('\nYearly Bookings');
    console.log('-'.repeat(60));
    console.log(drawBarChart(months, 30));
  }
}

async function main() {
  console.log('');
  console.log('Arrow Limousine — Dashboard (CLI)');
  console.log('='.repeat(60));

  // Parse args
  const args = Object.fromEntries(process.argv.slice(2).map(x => {
    const m = /^--([^=]+)=(.*)$/.exec(x);
    if (m) return [m[1], m[2]]; else return [x.replace(/^--/,''), true];
  }));

  // Counts: vehicles, clients/customers, employees/drivers, bookings/charters
  const vehiclesTbl = await findFirstExistingTable(['public.vehicles']);
  const clientsTbl = await findFirstExistingTable(['public.clients','public.customers']);
  const employeesTbl = await findFirstExistingTable(['public.employees','public.drivers']);
  const bookingsTbl = await findFirstExistingTable(['public.bookings','public.charters']);

  if (!vehiclesTbl && !clientsTbl && !employeesTbl && !bookingsTbl) {
    console.error('No standard tables found (vehicles/clients/customers/employees/drivers/bookings/charters).');
    process.exit(2);
  }

  const stats = {};
  if (vehiclesTbl) stats.vehicles = await getCountFromTable(vehiclesTbl.fq);
  if (clientsTbl) stats.clients = await getCountFromTable(clientsTbl.fq);
  if (employeesTbl) stats.employees = await getCountFromTable(employeesTbl.fq);
  if (bookingsTbl) stats.bookings = await getCountFromTable(bookingsTbl.fq);

  console.log('\nKey Metrics');
  console.log('-'.repeat(60));
  console.log(pad('Vehicles:', 18), lpad(stats.vehicles ?? 'N/A', 10));
  console.log(pad('Clients:', 18), lpad(stats.clients ?? 'N/A', 10));
  console.log(pad('Employees:', 18), lpad(stats.employees ?? 'N/A', 10));
  console.log(pad('Bookings:', 18), lpad(stats.bookings ?? 'N/A', 10));

  // Monthly revenue (6 months) — prefer payments table
  const paymentsTbl = await findFirstExistingTable(['public.payments','public.square_payments','public.charter_payments']);
  let revenue = null;
  if (paymentsTbl) {
    const dateCol = await getDateColumn(paymentsTbl.fq, ['payment_date','paid_at','created_at','date','transaction_date']);
    const amtCol = await getAmountColumn(paymentsTbl.fq, ['amount','total','paid_amount']);
    if (dateCol && amtCol) {
      const r = await pool.query(
        `SELECT to_char(date_trunc('month', ${dateCol}), 'YYYY-MM') as ym, SUM(${amtCol})::numeric as total
         FROM ${paymentsTbl.fq}
         WHERE ${dateCol} >= (CURRENT_DATE - INTERVAL '6 months')
         GROUP BY 1 ORDER BY 1`
      );
      const byYm = new Map(r.rows.map(x => [x.ym, Number(x.total||0)]));
      const months = monthsBack(6).map(m => ({ label: m.label, value: byYm.get(m.key) || 0 }));
      revenue = months;
    }
  }

  console.log('\nMonthly Revenue (last 6 months)');
  console.log('-'.repeat(60));
  if (revenue) {
    console.log(drawBarChart(revenue.map((m)=>({ label: m.label, value: m.value })), 40, fmtMoney));
  } else {
    console.log('No payments table/columns detected.');
  }

  // Booking trends (6 months)
  let trends = null;
  if (bookingsTbl) {
    const dateCol = await getDateColumn(bookingsTbl.fq, ['pickup_date','created_at','date','trip_date']);
    if (dateCol) {
      const r = await pool.query(
        `SELECT to_char(date_trunc('month', ${dateCol}::timestamp), 'YYYY-MM') as ym, COUNT(*)::int as c
         FROM ${bookingsTbl.fq}
         WHERE ${dateCol} >= (CURRENT_DATE - INTERVAL '6 months')
         GROUP BY 1 ORDER BY 1`
      ).catch(()=>({ rows: [] }));
      const byYm = new Map(r.rows.map(x => [x.ym, Number(x.c||0)]));
      const months = monthsBack(6).map(m => ({ label: m.label, value: byYm.get(m.key) || 0 }));
      trends = months;
    }
  }
  console.log('\nBookings (last 6 months)');
  console.log('-'.repeat(60));
  if (trends) {
    console.log(drawBarChart(trends, 40, fmtNum));
  } else {
    console.log('No bookings/charters date column detected.');
  }

  console.log('\n');

  // Optional calendar view if requested
  if (args.view || args.date) {
    await calendarView({ view: args.view || 'daily', date: args.date || null });
  } else {
    console.log('Tip: add --view=daily|weekly|monthly|yearly and --date="jan 28" for calendar output.');
  }
}

main()
  .then(() => pool.end())
  .catch((err) => {
    console.error('CLI failed:', err.message);
    pool.end();
    process.exit(1);
  });
