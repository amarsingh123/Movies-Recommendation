const $ = s => document.querySelector(s);
const IMG = 'https://image.tmdb.org/t/p/w500';
const CATS = {'Trending':'trending','Popular':'popular','Top rated':'top_rated','Upcoming':'upcoming','Now playing':'now_playing'};
const NOPIC = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="500" height="750"><rect width="100%" height="100%" fill="#dfe3f0"/><text x="50%" y="50%" fill="#7a829c" font-family="sans-serif" font-size="28" text-anchor="middle">No poster</text></svg>');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let cards = [], heading = '', reload = () => {};

/* ---------- API ---------- */
try { $('#api').value = localStorage.getItem('api') || ''; } catch {}
$('#api').value = $('#api').value || 'https://movies-recommendation-qqiy.onrender.com';
$('#api').onchange = () => { try { localStorage.setItem('api', $('#api').value.trim()); } catch {} reload(); };

async function get(path, params = {}) {
  const base = $('#api').value.trim().replace(/\/$/, '');
  const u = new URL(base + path);
  Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
  let r;
  try { r = await fetch(u); }
  catch { throw new Error(`Cannot reach the API at ${base}. Start the FastAPI server and check the address.`); }
  if (!r.ok) {
    let d = ''; try { d = (await r.json()).detail; } catch {}
    throw new Error(`API error ${r.status}` + (d ? ': ' + (typeof d === 'string' ? d : d.message || JSON.stringify(d)) : ''));
  }
  return r.json();
}

/* ---------- cards + filters ---------- */
const year = c => (c.release_date || '').slice(0, 4);
const toCard = m => ({tmdb_id: m.id, title: m.title || m.name || '', poster_url: m.poster_path ? IMG + m.poster_path : null, release_date: m.release_date, vote_average: m.vote_average});

const cardHTML = c => `<button class="card" data-id="${c.tmdb_id}">
  <img loading="lazy" src="${c.poster_url || NOPIC}" alt="">
  <b>${esc(c.title)}</b>
  <span><span class="r">${c.vote_average ? '★ ' + c.vote_average.toFixed(1) : 'Unrated'}</span> ${year(c) || 'TBA'}</span></button>`;

function filtered() {
  const minR = +$('#fRating').value, y1 = +$('#fFrom').value || 0, y2 = +$('#fTo').value || 9999;
  const t = $('#fText').value.trim().toLowerCase(), pos = $('#fPoster').checked, s = $('#fSort').value;
  const out = cards.filter(c => {
    const y = +year(c) || 0;
    return (c.vote_average || 0) >= minR && (!y || (y >= y1 && y <= y2)) &&
           (!t || c.title.toLowerCase().includes(t)) && (!pos || c.poster_url);
  });
  const by = {
    rating: (a, b) => (b.vote_average || 0) - (a.vote_average || 0),
    new: (a, b) => (b.release_date || '').localeCompare(a.release_date || ''),
    old: (a, b) => (a.release_date || '9').localeCompare(b.release_date || '9'),
    az: (a, b) => a.title.localeCompare(b.title)
  }[s];
  return by ? out.sort(by) : out;
}

function render() {
  const f = filtered();
  $('#title').textContent = heading;
  if (cards.length) {
    $('#status').textContent = `Showing ${f.length} of ${cards.length} movies` +
      (f.length < cards.length ? ` (${cards.length - f.length} hidden by filters)` : '');
  }
  $('#grid').innerHTML = f.length ? f.map(cardHTML).join('')
    : (cards.length ? '<p class="empty">No movies match these filters. Lower the minimum rating or widen the years.</p>' : '');
}

async function run(h, fn) {
  heading = h; $('#title').textContent = h; $('#status').textContent = 'Loading…'; $('#grid').innerHTML = '';
  try {
    cards = await fn();
    if (!cards.length) $('#status').textContent = 'Nothing found. Try another title.';
    render();
  } catch (e) { cards = []; $('#status').textContent = e.message; }
}

/* ---------- menu + search ---------- */
const setOn = label => document.querySelectorAll('#menu button').forEach(b => b.classList.toggle('on', b.textContent === label));

function browse(label) {
  setOn(label);
  reload = () => run(label, () => get('/home', {category: CATS[label], limit: 50}));
  reload();
}

$('#menu').innerHTML = Object.keys(CATS).map(k => `<button>${k}</button>`).join('');
$('#menu').onclick = e => e.target.closest('button') && browse(e.target.textContent);

$('#searchForm').onsubmit = e => {
  e.preventDefault();
  const q = $('#q').value.trim(); if (!q) return;
  setOn('');
  reload = () => run(`Results for “${q}”`, async () => (await get('/tmdb/search', {query: q})).results.filter(m => m.id).map(toCard));
  reload();
};

document.querySelectorAll('#filters input, #filters select').forEach(el => el.addEventListener('input', render));
$('#filters').onreset = () => setTimeout(render);

/* ---------- detail drawer ---------- */
const dr = $('#drawer');
const closeDrawer = () => { dr.classList.remove('open'); dr.setAttribute('aria-hidden', 'true'); };

async function openMovie(id) {
  dr.classList.add('open'); dr.setAttribute('aria-hidden', 'false'); dr.scrollTo(0, 0);
  $('#dBody').innerHTML = '<p>Loading…</p>';
  try {
    const d = await get('/movie/id/' + id);
    dr._d = d;
    $('#dBody').innerHTML = `${d.backdrop_url ? `<img class="bd" src="${d.backdrop_url}" alt="">` : ''}
      <h2>${esc(d.title)} <small>${(d.release_date || '').slice(0, 4)}</small></h2>
      <p class="gen">${(d.genres || []).map(g => `<span>${esc(g.name)}</span>`).join('')}</p>
      <p>${esc(d.overview || 'No overview available.')}</p>
      <div class="tabs"><button class="on" data-t="tfidf">Similar by content</button><button data-t="genre">Same genre</button></div>
      <div id="recs" class="grid small"></div>`;
    recs('tfidf');
  } catch (e) { $('#dBody').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

async function recs(t) {
  const box = $('#recs'), d = dr._d;
  box.innerHTML = '<p>Loading…</p>';
  try {
    let list;
    if (t === 'tfidf') {
      const b = await get('/movie/search', {query: d.title, tfidf_top_n: 18});
      list = b.tfidf_recommendations.map(r => r.tmdb).filter(Boolean);
    } else {
      list = await get('/recommend/genre', {tmdb_id: d.tmdb_id, limit: 18});
    }
    box.innerHTML = list.length ? list.map(cardHTML).join('') : '<p class="empty">No matches for this movie. Try the other tab.</p>';
  } catch (e) { box.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

document.addEventListener('click', e => {
  const c = e.target.closest('[data-id]'); if (c) return openMovie(c.dataset.id);
  const t = e.target.closest('[data-t]');
  if (t) { document.querySelectorAll('[data-t]').forEach(b => b.classList.toggle('on', b === t)); recs(t.dataset.t); }
  if (e.target.closest('#dClose')) closeDrawer();
});
document.addEventListener('keydown', e => e.key === 'Escape' && closeDrawer());

browse('Trending');
