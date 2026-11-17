'use strict';

const SCHEDULE_UTC_HOURS = [3, 9, 15, 21]; // Türkiye saati: 06:17, 12:17, 18:17, 00:17
const SCHEDULE_MINUTE = 17;
const trNumber = new Intl.NumberFormat('tr-TR');
const trTime = new Intl.DateTimeFormat('tr-TR', { timeZone: 'Europe/Istanbul', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const shortTime = new Intl.DateTimeFormat('tr-TR', { timeZone: 'Europe/Istanbul', hour: '2-digit', minute: '2-digit' });
const demoMode = new URLSearchParams(location.search).get('demo') === '1';
let liveData = null;

const previewItems = [
  {name:'Haluk Bilginer', category:'Oyuncu', count24h:1294, previous24h:317, headline:'Eski röportajındaki sinema tanımı yeniden gündem oldu', headlineUrl:'https://www.sozcu.com.tr/haluk-bilginer-den-cok-konusulacak-aciklama-p379657'},
  {name:'Arda Güler', category:'Futbolcu', count24h:1062, previous24h:824, headline:'Spor gündemindeki son gelişmeler', headlineUrl:null},
  {name:'Hande Erçel', category:'Oyuncu', count24h:881, previous24h:694, headline:'Dizi ve magazin haberleri', headlineUrl:null},
  {name:'Kenan Yıldız', category:'Futbolcu', count24h:692, previous24h:733, headline:'Futbol haberlerindeki gelişmeler', headlineUrl:null},
  {name:'Hadise', category:'Şarkıcı', count24h:521, previous24h:431, headline:'Müzik ve magazin gündemi', headlineUrl:null},
  {name:'Serenay Sarıkaya', category:'Oyuncu', count24h:461, previous24h:478, headline:'Televizyon ve magazin haberleri', headlineUrl:null},
  {name:'Tarkan', category:'Şarkıcı', count24h:408, previous24h:250, headline:'Müzik dünyasından haberler', headlineUrl:null},
  {name:'Cem Yılmaz', category:'Komedyen', count24h:384, previous24h:400, headline:'Gösteri ve sinema haberleri', headlineUrl:null},
  {name:'Afra Saraçoğlu', category:'Oyuncu', count24h:312, previous24h:249, headline:'Televizyon haberleri', headlineUrl:null},
  {name:'Acun Ilıcalı', category:'Televizyoncu', count24h:289, previous24h:316, headline:'Televizyon dünyasından haberler', headlineUrl:null},
].map((x,i)=>({...x, isDemo:true, previousRank:i+1}));

function nextScheduled(now = new Date()) {
  const base = new Date(now);
  for (const shift of [0, 1]) {
    for (const hour of SCHEDULE_UTC_HOURS) {
      const t = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth(), base.getUTCDate() + shift, hour, SCHEDULE_MINUTE));
      if (t > now) return t;
    }
  }
}
function two(n) { return String(n).padStart(2, '0'); }
function updateClocks() {
  const now = new Date();
  const next = nextScheduled(now);
  let diff = Math.max(0, Math.floor((next - now) / 1000));
  const h = Math.floor(diff / 3600); diff %= 3600;
  const m = Math.floor(diff / 60); const s = diff % 60;
  document.getElementById('countdown').textContent = `${two(h)}:${two(m)}:${two(s)}`;
  document.getElementById('nextRun').textContent = trTime.format(next);
  document.getElementById('headerClock').textContent = shortTime.format(now);
  if (liveData && !demoMode) {
    const el = document.getElementById('runStatus');
    const firstPending = !liveData.updatedAt;
    const age = firstPending ? Infinity : Date.now() - new Date(liveData.updatedAt).getTime();
    const late = !firstPending && age > (6 * 60 + 45) * 60 * 1000;
    el.classList.toggle('alert', late);
    el.innerHTML = '<span class="status-dot"></span>' + (firstPending ? 'İlk veri taraması bekleniyor' : late ? 'Güncelleme gecikmiş olabilir' : '6 saatte bir yenileniyor');
  }
}
function initials(name) { const words = name.trim().split(/\s+/); return (words.length > 1 ? words[0][0] + words[words.length - 1][0] : name.slice(0, 2)).toLocaleUpperCase('tr-TR'); }
function h(tag, classes, text) { const el = document.createElement(tag); if(classes) el.className = classes; if(text !== undefined) el.textContent = String(text); return el; }
function safeUrl(url) { try { const parsed = new URL(url); return ['https:', 'http:'].includes(parsed.protocol) ? parsed.href : null; } catch { return null; } }
function changeFor(item) {
  if (item.previous24h == null) return {label:'—', direction:'flat', title:'Önceki gün verisi yok'};
  if (item.previous24h === 0) return {label:'Yeni', direction:'up', title:'Önceki 24 saatte eşleşme yok'};
  const pct = Math.round((item.count24h - item.previous24h) * 100 / item.previous24h);
  return {label: pct > 0 ? `↑ %${trNumber.format(pct)}` : pct < 0 ? `↓ %${trNumber.format(Math.abs(pct))}` : '→ %0', direction: pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat', title:'Önceki 24 saate göre'};
}
function rankChange(item) {
  if (!Number.isInteger(item.previousRank)) return {label:'YENİ', direction:'flat'};
  const delta = item.previousRank - item.rank;
  if (delta > 0) return {label:`▲ ${delta} sıra`,direction:'up'};
  if (delta < 0) return {label:`▼ ${Math.abs(delta)} sıra`,direction:'down'};
  return {label:'—',direction:'flat'};
}
function historyChart(history) {
  const wrap = h('div','history-area');
  if (!Array.isArray(history) || history.length < 2) {
    wrap.append(h('span','history-empty','Grafik için en az iki başarılı tarama gerekli.'));
    return wrap;
  }
  const values = history.map(v => Math.max(0, Number(v.count)||0));
  const max = Math.max(...values,1), min = Math.min(...values);
  const denominator = Math.max(max-min,1);
  const coords = values.map((v,i) => `${(i*290/(values.length-1)).toFixed(1)},${(75-(v-min)/denominator*62).toFixed(1)}`);
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 290 88'); svg.setAttribute('role','img');
  svg.setAttribute('aria-label','Son başarılı güncellemelerdeki haber eşleşmelerinin değişimi');
  const polyline = document.createElementNS('http://www.w3.org/2000/svg','polyline');
  polyline.setAttribute('points',coords.join(' ')); polyline.setAttribute('fill','none');
  polyline.setAttribute('stroke','#e46d38'); polyline.setAttribute('stroke-width','2.5');
  polyline.setAttribute('stroke-linejoin','round'); polyline.setAttribute('stroke-linecap','round');
  svg.append(polyline); wrap.append(svg);
  wrap.append(h('div','history-caption',`${values.length} tarama · Son değer: ${trNumber.format(values.at(-1))} haber eşleşmesi`));
  return wrap;
}
function createRow(item, i) {
  const wrapper = h('div','ranking-wrapper');
  const row = h('div', 'ranking-item' + (i === 0 ? ' lead' : ''));
  const person = h('div', 'rank-person');
  person.append(h('div', 'rank-number', two(i + 1)));
  const avatar = h('div', 'avatar' + (i === 0 ? '' : ' tint' + (i % 4)), initials(item.name));
  avatar.setAttribute('aria-hidden','true'); person.append(avatar);
  const info = h('div','person-info');
  const btn = h('button','person-name person-expand',item.name+' ＋');
  btn.type='button'; btn.setAttribute('aria-expanded','false');
  btn.setAttribute('aria-label',item.name+' detaylarını göster');
  const detail = h('div','person-details'); detail.hidden = true;
  btn.addEventListener('click',()=>{ detail.hidden = !detail.hidden;
    btn.setAttribute('aria-expanded', String(!detail.hidden));
    btn.textContent=item.name + (detail.hidden ? ' ＋' : ' −');
  });
  info.append(btn);
  const descriptor = `${item.category || 'Gündemdeki isim'} · Endeks ${Number(item.indexScore ?? 0).toLocaleString('tr-TR')}/100`;
  info.append(h('div','person-tag',descriptor)); person.append(info);
  const headline = h('div','trend-title');
  const url = safeUrl(item.headlineUrl);
  if (url && item.headline) {
    const link = h('a','trend-link',item.headline); link.href = url; link.target = '_blank';
    link.rel = 'noopener noreferrer'; link.title = 'Haber kaynağını aç'; headline.append(link);
  } else { headline.append(h('span', 'trend-placeholder', 'Henüz doğrulanmış gündem başlığı yok')); }
  const count = h('div','count',trNumber.format(item.count24h));
  count.append(h('span','count-label','haber eşleşmesi'));
  const movement = h('div','movement');
  const diff = rankChange(item); const daily = changeFor(item);
  movement.append(h('span','change '+diff.direction,diff.label));
  movement.append(h('span','move-caption','24 saat: '+daily.label));
  row.append(person,headline,count,movement);
  const body = h('div','detail-layout');
  const articles = h('div','article-list'); articles.append(h('div','detail-heading','GÜNDEMİN KAYNAKLARI'));
  const available = Array.isArray(item.articles) ? item.articles.filter(a=>safeUrl(a.url) && a.title).slice(0,3):[];
  if (!available.length && url && item.headline) available.push({title:item.headline,url});
  if (available.length) available.forEach((a,i) => {const link=h('a','detail-link',`${i+1}. ${a.title}`);
    link.href=safeUrl(a.url);link.target='_blank';link.rel='noopener noreferrer';articles.append(link);});
  else articles.append(h('div','history-empty','Bu kişi için doğrulanmış güncel haber bağlantısı yok.'));
  const trend = h('div','history-panel'); trend.append(h('div','detail-heading','SON GÜNCELLEMELER'));
  trend.append(historyChart(item.history)); body.append(articles,trend); detail.append(body);
  wrapper.append(row,detail); return wrapper;
}
function renderData(data) {
  const root = document.getElementById('rankingList'); root.replaceChildren();
  let items = Array.isArray(data?.items) ? data.items.slice() : [];
  items = items.filter(x => x && typeof x.name === 'string' && Number.isFinite(x.count24h) && x.count24h >= 0).sort((a,b) => (b.score ?? b.count24h) - (a.score ?? a.count24h));
  document.getElementById('personCount').textContent = items.length ? `${items.length} kişi` : 'Veri bekleniyor';
  const updated = document.getElementById('updatedAt');
  if (!demoMode && data.source === 'google_news_rss') {
    document.getElementById('methodShort').textContent = 'Yedek kaynak: Google News RSS haber eşleşmeleri (sonuç limiti olabilir). Sosyal medya verisi değildir.';
  }
  if (demoMode) { updated.textContent = 'Örnek veriler'; document.getElementById('demoChip').hidden = false; document.getElementById('runStatus').innerHTML = '<span class="status-dot"></span> Tasarım önizlemesi'; }
  else { updated.textContent = data.updatedAt ? trTime.format(new Date(data.updatedAt)) : 'Henüz yok'; }
  if (!items.length) {
    const empty = h('div','empty-state'); empty.append(h('div','empty-title','İlk veri taramasını bekliyoruz'));
    empty.append(h('div','empty-desc','Site hazır. GitHub Actions üzerinde ilk tarama çalıştığında gerçek sıralama burada otomatik görünecek. Şu an herhangi bir kişiye temelsiz bir sıra vermiyoruz.'));
    const a = h('a','demo-link','Örnek tasarımı incele →'); a.href = '?demo=1'; empty.append(a); root.append(empty);
    return;
  }
  items.forEach((item,i)=>root.append(createRow({...item,rank:i+1,indexScore:item.indexScore??Math.round((item.count24h/(items[0]?.count24h||1))*100)},i)));
}
async function load(silent = false) {
  document.getElementById('year').textContent = new Date().getFullYear();
  if (demoMode) {
    document.title = 'ÖRNEK GÖRÜNÜM — GündemRadar';
    renderData({items:previewItems, updatedAt:null}); updateClocks(); return;
  }
  try {
    const res = await fetch('./data/rankings.json?ts=' + Date.now(), {cache:'no-store'});
    if(!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (silent && liveData && data.updatedAt === liveData.updatedAt) return;
    liveData = data; renderData(data);
  } catch (e) {
    console.warn('Veri okunamadı',e);
    if (silent && liveData) return;
    renderData({items:[],updatedAt:null});
    document.getElementById('runStatus').classList.add('alert');
    document.getElementById('runStatus').textContent = 'Veri kaynağına ulaşılamıyor';
  }
  updateClocks();
}
document.getElementById('aboutButton').addEventListener('click',function(){
  const p=document.getElementById('methodPanel'); const expanding=p.hidden;
  p.hidden=!expanding; this.setAttribute('aria-expanded', String(expanding));
});
updateClocks(); setInterval(updateClocks,1000); load();
// Keeping the page open must not freeze the ranking after a successful deployment.
if (!demoMode) setInterval(() => load(true), 60_000);
