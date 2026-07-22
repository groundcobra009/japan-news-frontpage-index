const REPO_RAW_BASE = "https://raw.githubusercontent.com/groundcobra009/japan-news-frontpage-index/main/";

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (inQuotes) {
      if (char === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (char === "\r") {
      // skip, \r\n line endings are normalized via the following \n
    } else {
      field += char;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

function rowsToObjects(rows) {
  if (rows.length === 0) return [];
  const header = rows[0];
  return rows
    .slice(1)
    .filter((r) => r.length === header.length)
    .map((r) => {
      const obj = {};
      header.forEach((key, i) => {
        obj[key] = r[i];
      });
      return obj;
    });
}

async function fetchCsv(path) {
  const response = await fetch(REPO_RAW_BASE + path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} の取得に失敗しました(HTTP ${response.status})`);
  }
  const text = await response.text();
  return rowsToObjects(parseCsv(text));
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderTable(tbodyEl, articles) {
  tbodyEl.innerHTML = "";
  const okArticles = articles.filter((a) => a.status === "ok" && a.headline);

  if (okArticles.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="3">該当する記事がありません</td>';
    tbodyEl.appendChild(tr);
    return;
  }

  for (const a of okArticles) {
    const tr = document.createElement("tr");
    const headline = escapeHtml(a.headline);
    const link = a.url
      ? `<a href="${escapeHtml(a.url)}" target="_blank" rel="noopener">${headline}</a>`
      : headline;
    tr.innerHTML = `<td>${escapeHtml(a.category || "")}</td><td>${escapeHtml(a.newspaper || "")}</td><td>${link}</td>`;
    tbodyEl.appendChild(tr);
  }
}

async function loadToday() {
  const statusEl = document.getElementById("today-status");
  const tbody = document.querySelector("#today-table tbody");
  try {
    const articles = await fetchCsv("data/latest.csv");
    statusEl.textContent = `${articles.length}件(data/latest.csv)`;
    renderTable(tbody, articles);
  } catch (err) {
    statusEl.textContent = "データの取得に失敗しました: " + err.message;
  }
}

let currentSearchArticles = [];

async function loadArchiveIndex() {
  const select = document.getElementById("date-select");
  const statusEl = document.getElementById("search-status");
  let dates = [];
  try {
    const response = await fetch(REPO_RAW_BASE + "data/archive-index.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    dates = data.dates || [];
  } catch (err) {
    statusEl.textContent = "アーカイブ一覧の取得に失敗しました: " + err.message;
    return;
  }

  select.innerHTML = "";
  for (const date of dates) {
    const option = document.createElement("option");
    option.value = date;
    option.textContent = date;
    select.appendChild(option);
  }

  if (dates.length > 0) {
    await loadDate(dates[0]);
  } else {
    statusEl.textContent = "アーカイブデータがまだありません";
  }
}

async function loadDate(date) {
  const statusEl = document.getElementById("search-status");
  const [year, month] = date.split("-");
  try {
    currentSearchArticles = await fetchCsv(`data/${year}/${month}/${date}.csv`);
    statusEl.textContent = `${date} のデータ(${currentSearchArticles.length}件)を読み込みました`;
    applyKeywordFilter();
  } catch (err) {
    statusEl.textContent = "データの取得に失敗しました: " + err.message;
  }
}

function applyKeywordFilter() {
  const keyword = document.getElementById("keyword-input").value.trim();
  const tbody = document.querySelector("#search-table tbody");
  const filtered = keyword
    ? currentSearchArticles.filter(
        (a) => (a.headline || "").includes(keyword) || (a.newspaper || "").includes(keyword)
      )
    : currentSearchArticles;
  renderTable(tbody, filtered);
}

document.addEventListener("DOMContentLoaded", () => {
  loadToday();
  loadArchiveIndex();
  document.getElementById("date-select").addEventListener("change", (e) => loadDate(e.target.value));
  document.getElementById("keyword-input").addEventListener("input", applyKeywordFilter);
});
