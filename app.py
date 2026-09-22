from flask import Flask, request, jsonify, render_template_string
import sqlite3, os, time

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "darsi.db")

STATIONS = {
    "ps5-1":   {"label": "PS5 Arena I",   "detail": '55" Display',        "type": "ps5",      "icon": "🎮"},
    "ps5-2":   {"label": "PS5 Arena II",  "detail": '45" Display',        "type": "ps5",      "icon": "🎮"},
    "ps5-3":   {"label": "PS5 Arena III", "detail": '45" Display',        "type": "ps5",      "icon": "🎮"},
    "racing":  {"label": "Racing Rig",    "detail": "Steering Wheel Setup", "type": "steering", "icon": "🏎️"},
    "vr":      {"label": "VR Deck",       "detail": "Virtual Reality",    "type": "vr",       "icon": "🥽"},
    "pc":      {"label": "PC Bay",        "detail": "Gaming PC",          "type": "pc",       "icon": "🖥️"},
}

# NOTE: no rate was given for "pc" — set the same as ps5 for now. Change if different.
RATES = {
    "ps5":      {"half": 50, "hour": 75},
    "steering": {"half": 50, "hour": 75},
    "vr":       {"half": 50, "hour": 100},
    "pc":       {"half": 50, "hour": 75},
}

DURATIONS = [0.5, 1, 1.5, 2, 2.5, 3]
OPEN_MIN, CLOSE_MIN = 9 * 60, 20 * 60  # 9:00 AM - 8:00 PM


def get_price(station_type, duration_hrs):
    rate = RATES[station_type]
    full_hours = int(duration_hrs)
    has_half = (duration_hrs - full_hours) >= 0.49
    return full_hours * rate["hour"] + (rate["half"] if has_half else 0)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station TEXT NOT NULL,
            date TEXT NOT NULL,
            start_min INTEGER NOT NULL,
            end_min INTEGER NOT NULL,
            duration REAL NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_bookings(station, date):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM bookings WHERE station=? AND date=? ORDER BY start_min",
        (station, date)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and a_end > b_start


@app.route("/api/bookings", methods=["GET"])
def api_get_bookings():
    station = request.args.get("station", "")
    date = request.args.get("date", "")
    if station not in STATIONS or not date:
        return jsonify({"error": "invalid station or date"}), 400
    return jsonify(get_bookings(station, date))


@app.route("/api/bookings", methods=["POST"])
def api_create_booking():
    data = request.get_json(force=True, silent=True) or {}
    station = data.get("station")
    date = data.get("date")
    start_min = data.get("start_min")
    duration = data.get("duration")
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()

    if station not in STATIONS:
        return jsonify({"error": "Unknown station."}), 400
    if not date:
        return jsonify({"error": "Date is required."}), 400
    if duration not in DURATIONS:
        return jsonify({"error": "Invalid duration."}), 400
    if not isinstance(start_min, int):
        return jsonify({"error": "Invalid start time."}), 400
    if not name:
        return jsonify({"error": "Name is required."}), 400
    if len(''.join(filter(str.isdigit, phone))) < 7:
        return jsonify({"error": "Please enter a valid phone number."}), 400

    duration_min = round(duration * 60)
    end_min = start_min + duration_min
    if start_min < OPEN_MIN or end_min > CLOSE_MIN:
        return jsonify({"error": "Booking must fall within 9:00 AM - 8:00 PM."}), 400

    existing = get_bookings(station, date)
    for b in existing:
        if overlaps(start_min, end_min, b["start_min"], b["end_min"]):
            return jsonify({"error": "That slot was just taken. Please pick another time."}), 409

    station_type = STATIONS[station]["type"]
    price = get_price(station_type, duration)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO bookings (station, date, start_min, end_min, duration, name, phone, price, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (station, date, start_min, end_min, duration, name, phone, price, int(time.time()))
    )
    conn.commit()
    conn.close()

    return jsonify({
        "station": station, "date": date, "start_min": start_min, "end_min": end_min,
        "duration": duration, "name": name, "price": price
    }), 201


PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Darsi Gaming Zone</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#08060f; --panel:#140f26; --panel-line:#2a2145;
    --magenta:#ff2e88; --cyan:#21e6ff; --violet:#8b5cf6; --amber:#ffb800;
    --text:#ede9f7; --text-dim:#a89fc4; --danger:#ff4d5e; --ok:#2be08a;
  }
  * { box-sizing: border-box; }
  body {
    margin:0; font-family:'Rajdhani',system-ui,sans-serif; font-size:17px; color:var(--text);
    background: radial-gradient(1100px 600px at 15% -10%, rgba(139,92,246,0.25), transparent 60%),
                radial-gradient(900px 500px at 110% 10%, rgba(33,230,255,0.14), transparent 55%), var(--bg);
  }
  h1,h2,h3,h4 { font-family:'Orbitron',sans-serif; }
  .wrap { max-width:1080px; margin:0 auto; padding:0 20px; }
  header.top { position:sticky; top:0; z-index:20; background:rgba(8,6,15,0.85); border-bottom:1px solid var(--panel-line); }
  .topbar { display:flex; align-items:center; justify-content:space-between; padding:14px 20px; max-width:1080px; margin:0 auto; }
  .brand { font-family:'Orbitron',sans-serif; font-weight:800; font-size:1.05rem; }
  .brand .mark { color:var(--magenta); }
  .hours-chip { font-size:0.82rem; color:var(--cyan); border:1px solid rgba(33,230,255,0.4); padding:6px 12px; border-radius:999px; }
  .hero { text-align:center; padding:70px 20px 50px; }
  .kicker { color:var(--cyan); letter-spacing:3px; font-size:0.8rem; text-transform:uppercase; }
  .hero h1 { font-size:clamp(2.2rem,7vw,4rem); margin:12px 0 6px; color:#fff; }
  .hero h1 .glow { color:var(--magenta); text-shadow:0 0 18px rgba(255,46,136,0.6); }
  .hero p.sub { color:var(--text-dim); max-width:520px; margin:0 auto 24px; }
  section { padding:50px 0; }
  .section-head { text-align:center; margin-bottom:32px; }
  .section-head .accent { color:var(--cyan); }
  .stations-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }
  .station-card { background:linear-gradient(155deg,var(--panel),#100b20); border:1px solid var(--panel-line); padding:22px 20px; }
  .station-card .icon { font-size:2rem; }
  .price-row { display:flex; justify-content:space-between; font-size:0.85rem; padding:7px 0; border-top:1px dashed var(--panel-line); color:var(--text-dim); }
  .price-row b { color:var(--amber); }
  .terminal { background:#0f0a1e; border:1px solid var(--panel-line); padding:30px; }
  .step { margin-bottom:28px; } .step-label { display:flex; gap:10px; align-items:center; margin-bottom:12px; }
  .step-num { width:26px; height:26px; border:1px solid var(--violet); color:var(--violet); display:flex; align-items:center; justify-content:center; font-family:'Orbitron',sans-serif; font-size:0.8rem; }
  .step-body { padding-left:36px; }
  input, select { background:#0d0a1a; border:1px solid var(--panel-line); color:var(--text); padding:12px 14px; font-family:'Rajdhani',sans-serif; font-size:1rem; font-weight:600; width:100%; max-width:320px; }
  label.field-label { display:block; font-size:0.8rem; color:var(--text-dim); margin-bottom:6px; text-transform:uppercase; letter-spacing:1px; }
  .station-pick-row, .duration-row { display:flex; flex-wrap:wrap; gap:10px; }
  .pick-chip { border:1px solid var(--panel-line); background:#0d0a1a; color:var(--text-dim); padding:10px 16px; cursor:pointer; font-weight:600; }
  .pick-chip.active { border-color:var(--magenta); background:rgba(255,46,136,0.12); color:#fff; }
  .dur-chip { border:1px solid var(--panel-line); background:#0d0a1a; color:var(--text-dim); padding:8px 14px; cursor:pointer; font-size:0.85rem; font-weight:600; }
  .dur-chip.active { border-color:var(--cyan); color:#fff; background:rgba(33,230,255,0.1); }
  .slot-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(96px,1fr)); gap:8px; margin-top:10px; }
  .slot-btn { border:1px solid var(--panel-line); background:#0d0a1a; color:var(--text-dim); padding:10px 6px; font-size:0.82rem; font-weight:600; cursor:pointer; text-align:center; }
  .slot-btn.available:hover { border-color:var(--ok); color:#fff; }
  .slot-btn.selected { border-color:var(--ok); background:rgba(43,224,138,0.14); color:#fff; }
  .slot-btn.booked { color:var(--danger); border-color:rgba(255,77,94,0.35); background:rgba(255,77,94,0.06); cursor:not-allowed; text-decoration:line-through; }
  .slot-btn.past { color:#453d5c; cursor:not-allowed; opacity:0.5; }
  .details-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; max-width:500px; }
  .price-box { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-top:22px; padding-top:22px; border-top:1px solid var(--panel-line); flex-wrap:wrap; }
  .price-tag { font-family:'Orbitron',sans-serif; color:var(--amber); font-size:1.5rem; }
  .btn { font-family:'Orbitron',sans-serif; font-weight:700; font-size:0.9rem; border:none; cursor:pointer; padding:15px 30px; color:#08060f; background:linear-gradient(100deg,var(--cyan),var(--magenta)); }
  .btn:disabled { opacity:0.4; cursor:not-allowed; }
  .msg { font-size:0.88rem; padding:10px 14px; border-left:3px solid; margin-top:14px; }
  .msg.error { border-color:var(--danger); color:#ffb3ba; background:rgba(255,77,94,0.08); }
  .msg.info { border-color:var(--cyan); color:var(--text-dim); background:rgba(33,230,255,0.06); }
  .ticket { background:#170f2c; border:1px dashed var(--cyan); padding:26px; max-width:440px; margin:30px auto 0; }
  .ticket .row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px dashed var(--panel-line); }
  .ticket h3 { color:var(--ok); margin:0 0 6px; }
  @media (max-width:480px){ .details-grid{grid-template-columns:1fr;} .step-body{padding-left:0;} }
</style>
</head>
<body>
<header class="top">
  <div class="topbar">
    <div class="brand"><span class="mark">◆</span> DARSI <span style="color:var(--cyan)">GAMING ZONE</span></div>
    <div class="hours-chip">OPEN 9:00 AM – 8:00 PM</div>
  </div>
</header>

<section class="hero">
  <div class="wrap">
    <div class="kicker">Console · Racing · VR · PC</div>
    <h1>YOUR NEXT <span class="glow">WIN</span><br>STARTS HERE</h1>
    <p class="sub">Three PS5 arenas, a racing rig, a VR deck and a gaming PC — book your slot before someone else takes it.</p>
    <a href="#book" class="btn">BOOK A SLOT</a>
  </div>
</section>

<section id="stations">
  <div class="wrap">
    <div class="section-head"><h2>The <span class="accent">Setup</span></h2></div>
    <div class="stations-grid" id="stationsGrid"></div>
  </div>
</section>

<section id="book">
  <div class="wrap">
    <div class="section-head"><h2>Reserve Your <span class="accent">Slot</span></h2></div>
    <div class="terminal">
      <div class="step">
        <div class="step-label"><div class="step-num">1</div><h4>CHOOSE DATE</h4></div>
        <div class="step-body"><input type="date" id="dateInput"></div>
      </div>
      <div class="step">
        <div class="step-label"><div class="step-num">2</div><h4>CHOOSE STATION</h4></div>
        <div class="step-body"><div class="station-pick-row" id="stationPickRow"></div></div>
      </div>
      <div class="step">
        <div class="step-label"><div class="step-num">3</div><h4>DURATION &amp; TIME</h4></div>
        <div class="step-body">
          <label class="field-label">Duration</label>
          <div class="duration-row" id="durationRow"></div>
          <label class="field-label" style="margin-top:14px;">Start Time</label>
          <div class="slot-grid" id="slotGrid"></div>
          <div id="loadingMsg" class="msg info" style="display:none;">Loading availability…</div>
        </div>
      </div>
      <div class="step">
        <div class="step-label"><div class="step-num">4</div><h4>YOUR DETAILS</h4></div>
        <div class="step-body">
          <div class="details-grid">
            <div><label class="field-label">Name</label><input type="text" id="nameInput" placeholder="Your name"></div>
            <div><label class="field-label">Phone</label><input type="tel" id="phoneInput" placeholder="10-digit number"></div>
          </div>
          <div class="price-box">
            <div><div class="field-label">Total</div><div class="price-tag">₹<span id="priceOut">0</span></div></div>
            <button class="btn" id="confirmBtn">CONFIRM BOOKING</button>
          </div>
          <div id="bookMsg"></div>
        </div>
      </div>
    </div>
    <div id="ticketWrap"></div>
  </div>
</section>

<script>
var STATIONS = {{ stations_json|safe }};
var RATES = {{ rates_json|safe }};
var DURATIONS = [0.5,1,1.5,2,2.5,3];
var OPEN_MIN = 540, CLOSE_MIN = 1200;
var state = { date:null, stationId:null, duration:1, startMin:null, bookings:[] };

function fmtTime(min){
  var h=Math.floor(min/60), m=min%60, ampm = h>=12?'PM':'AM', hh = h%12; if(hh===0) hh=12;
  return hh+':'+(m<10?'0'+m:m)+' '+ampm;
}
function todayStr(){ var d=new Date(); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
function nowMinIfToday(dateStr){ if(dateStr!==todayStr()) return -1; var d=new Date(); return d.getHours()*60+d.getMinutes(); }
function getPrice(type,dur){ var r=RATES[type]; var full=Math.floor(dur+1e-9); var half=(dur-full)>=0.49; return full*r.hour+(half?r.half:0); }
function overlaps(a1,a2,b1,b2){ return a1<b2 && a2>b1; }

function renderStationsGrid(){
  var g=document.getElementById('stationsGrid');
  g.innerHTML = Object.keys(STATIONS).map(function(id){
    var s=STATIONS[id], r=RATES[s.type];
    return '<div class="station-card"><div class="icon">'+s.icon+'</div><h3>'+s.label+'</h3>'+
      '<div style="color:var(--text-dim);font-size:0.88rem;margin-bottom:14px;">'+s.detail+'</div>'+
      '<div class="price-row"><span>30 min</span><b>₹'+r.half+'</b></div>'+
      '<div class="price-row"><span>1 hour</span><b>₹'+r.hour+'</b></div></div>';
  }).join('');
}
function renderStationPicker(){
  var row=document.getElementById('stationPickRow');
  row.innerHTML = Object.keys(STATIONS).map(function(id){
    return '<div class="pick-chip" data-id="'+id+'"><span>'+STATIONS[id].icon+'</span> '+STATIONS[id].label+'</div>';
  }).join('');
  row.querySelectorAll('.pick-chip').forEach(function(chip){
    chip.addEventListener('click', function(){
      state.stationId = chip.getAttribute('data-id');
      row.querySelectorAll('.pick-chip').forEach(function(c){c.classList.remove('active');});
      chip.classList.add('active');
      state.startMin = null;
      loadBookings();
    });
  });
}
function renderDurationRow(){
  var row=document.getElementById('durationRow');
  var labels={0.5:'30 min',1:'1 hr',1.5:'1 hr 30 min',2:'2 hr',2.5:'2 hr 30 min',3:'3 hr'};
  row.innerHTML = DURATIONS.map(function(d){
    return '<div class="dur-chip'+(d===state.duration?' active':'')+'" data-v="'+d+'">'+labels[d]+'</div>';
  }).join('');
  row.querySelectorAll('.dur-chip').forEach(function(chip){
    chip.addEventListener('click', function(){
      state.duration = parseFloat(chip.getAttribute('data-v'));
      state.startMin = null;
      row.querySelectorAll('.dur-chip').forEach(function(c){c.classList.remove('active');});
      chip.classList.add('active');
      renderSlotGrid(); updatePrice();
    });
  });
}
function renderSlotGrid(){
  var grid=document.getElementById('slotGrid');
  if(!state.stationId || !state.date){ grid.innerHTML='<div class="msg info">Choose a date and station first.</div>'; return; }
  var durMin=Math.round(state.duration*60);
  var pastCutoff=nowMinIfToday(state.date);
  var html='';
  for(var m=OPEN_MIN; m+durMin<=CLOSE_MIN; m+=30){
    var isPast = pastCutoff>=0 && m<=pastCutoff;
    var isBooked=false;
    for(var i=0;i<state.bookings.length;i++){
      var b=state.bookings[i];
      if(overlaps(m,m+durMin,b.start_min,b.end_min)){ isBooked=true; break; }
    }
    var cls='slot-btn ';
    if(isPast) cls+='past'; else if(isBooked) cls+='booked'; else cls+='available';
    if(!isPast && !isBooked && state.startMin===m) cls+=' selected';
    html+='<div class="'+cls+'" data-m="'+m+'">'+fmtTime(m)+'</div>';
  }
  grid.innerHTML = html || '<div class="msg info">No slots left for this duration today.</div>';
  grid.querySelectorAll('.slot-btn.available').forEach(function(btn){
    btn.addEventListener('click', function(){ state.startMin=parseInt(btn.getAttribute('data-m'),10); renderSlotGrid(); });
  });
}
function updatePrice(){
  var st=STATIONS[state.stationId];
  var price = st ? getPrice(st.type, state.duration) : 0;
  document.getElementById('priceOut').textContent = price;
}
function loadBookings(){
  document.getElementById('loadingMsg').style.display='block';
  if(!state.stationId || !state.date){ document.getElementById('loadingMsg').style.display='none'; return; }
  fetch('/api/bookings?station='+encodeURIComponent(state.stationId)+'&date='+encodeURIComponent(state.date))
    .then(function(r){return r.json();})
    .then(function(data){ state.bookings=data; document.getElementById('loadingMsg').style.display='none'; renderSlotGrid(); })
    .catch(function(){ document.getElementById('loadingMsg').style.display='none'; });
}
function showMsg(text,type){ document.getElementById('bookMsg').innerHTML = text ? '<div class="msg '+type+'">'+text+'</div>' : ''; }
function renderTicket(b){
  var st=STATIONS[b.station];
  document.getElementById('ticketWrap').innerHTML =
    '<div class="ticket"><h3>✓ BOOKING CONFIRMED</h3>'+
    '<div class="row"><span>Station</span><span>'+st.icon+' '+st.label+'</span></div>'+
    '<div class="row"><span>Date</span><span>'+b.date+'</span></div>'+
    '<div class="row"><span>Time</span><span>'+fmtTime(b.start_min)+' – '+fmtTime(b.end_min)+'</span></div>'+
    '<div class="row"><span>Name</span><span>'+b.name+'</span></div>'+
    '<div class="row"><span>Total</span><span>₹'+b.price+'</span></div></div>';
}
function confirmBooking(){
  showMsg('','');
  if(!state.date || !state.stationId || state.startMin==null){ showMsg('Please choose a date, station and time slot.','error'); return; }
  var name=document.getElementById('nameInput').value.trim();
  var phone=document.getElementById('phoneInput').value.trim();
  if(!name){ showMsg('Please enter your name.','error'); return; }
  if(phone.replace(/\D/g,'').length<7){ showMsg('Please enter a valid phone number.','error'); return; }
  var btn=document.getElementById('confirmBtn'); btn.disabled=true; btn.textContent='BOOKING…';
  fetch('/api/bookings', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({station:state.stationId, date:state.date, start_min:state.startMin, duration:state.duration, name:name, phone:phone})
  }).then(function(r){ return r.json().then(function(data){ return {ok:r.ok, data:data}; }); })
    .then(function(res){
      btn.disabled=false; btn.textContent='CONFIRM BOOKING';
      if(!res.ok){ showMsg(res.data.error || 'Could not book that slot.', 'error'); loadBookings(); return; }
      renderTicket(res.data);
      state.startMin=null;
      document.getElementById('nameInput').value=''; document.getElementById('phoneInput').value='';
      loadBookings();
    }).catch(function(){ btn.disabled=false; btn.textContent='CONFIRM BOOKING'; showMsg('Network error. Please try again.','error'); });
}

renderStationsGrid(); renderStationPicker(); renderDurationRow();
var dateInput=document.getElementById('dateInput');
var t=todayStr(); dateInput.min=t; dateInput.value=t; state.date=t;
dateInput.addEventListener('change', function(){ state.date=dateInput.value; state.startMin=null; loadBookings(); });
document.getElementById('confirmBtn').addEventListener('click', confirmBooking);
renderSlotGrid(); updatePrice();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    import json
    return render_template_string(PAGE, stations_json=json.dumps(STATIONS), rates_json=json.dumps(RATES))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
