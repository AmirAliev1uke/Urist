// ============================================================
//  Legal AI Assistant — логика надстройки Word
//  Берёт текст документа через Office.js → отправляет в API →
//  показывает отчёт + подсвечивает риски/рекомендации в тексте.
// ============================================================

// Адрес бэкенда. Для разработки — localhost.
// При сетевом развёртывании замените на адрес сервера (HTTPS).
const API_BASE = "http://localhost:8000";

// Цвета подсветки в Word (hex, согласованы с веб-интерфейсом)
const HIGHLIGHT_COLORS = {
  high: "#F87171",          // красный
  medium: "#FBBF24",        // жёлтый
  low: "#34D399",           // зелёный
  compliance: "#34D399",    // зелёный
  missing_clause: "#FBBF24", // жёлтый
  risk: "#F87171",          // красный
  wording: "#60A5FA",       // синий
  general: "#60A5FA",       // синий
};

const SEVERITY_LABELS = {
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
};

const CATEGORY_LABELS = {
  compliance: "Соответствие",
  risk: "Риск",
  missing_clause: "Нет условия",
  wording: "Формулировка",
  general: "Общее",
};

// Office.js инициализация
Office.onReady((info) => {
  if (info.host === Office.HostType.Word) {
    document.getElementById("analyze-btn").onclick = analyzeDocument;
    document.getElementById("clear-btn").onclick = clearHighlights;
  }
});

// ------------------------------------------------------------
//  Главный поток: получить текст → отправить → отрисовать + подсветить
// ------------------------------------------------------------

async function analyzeDocument() {
  const btn = document.getElementById("analyze-btn");
  const loading = document.getElementById("loading");
  const errorEl = document.getElementById("error");
  const resultEl = document.getElementById("result");
  const emptyEl = document.getElementById("empty-state");

  btn.disabled = true;
  loading.classList.add("active");
  errorEl.classList.remove("active");
  resultEl.classList.remove("active");
  emptyEl.style.display = "none";

  try {
    // 1. Получить текст документа через Office.js
    const text = await getDocumentText();
    if (!text || text.trim().length < 10) {
      throw new Error("Документ пуст или слишком короткий для анализа.");
    }

    // 2. Отправить в API анализа текста
    const userQuery = document.getElementById("user-query").value.trim();
    const response = await fetch(`${API_BASE}/api/analyze/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text,
        file_name: getDocumentName(),
        user_query: userQuery,
      }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Ошибка сервера: ${response.status}`);
    }

    const data = await response.json();

    // 3. Отрисовать отчёт в панели
    renderReport(data);

    // 4. Подсветить риски и рекомендации в документе
    await highlightInDocument(data.result);

    resultEl.classList.add("active");
  } catch (error) {
    showError(error.message);
  } finally {
    btn.disabled = false;
    loading.classList.remove("active");
  }
}

// ------------------------------------------------------------
//  Office.js: получение текста документа
// ------------------------------------------------------------

function getDocumentText() {
  // Канонический способ Word.js: загрузка body.text через Word.run + context.sync.
  // Это самый надёжный метод для документов Word любого размера.
  return Word.run((context) => {
    const body = context.document.body;
    body.load("text");
    return context.sync().then(() => body.text);
  });
}

function getDocumentName() {
  try {
    return Office.context.document.url
      ? Office.context.document.url.split("/").pop().split("\\").pop()
      : "document.docx";
  } catch {
    return "document.docx";
  }
}

// ------------------------------------------------------------
//  Подсветка в документе Word (Этап 4)
// ------------------------------------------------------------

async function highlightInDocument(result) {
  if (!result) return;

  // Собираем все цитаты для подсветки: риски + рекомендации
  const highlights = [];

  (result.risks || []).forEach((risk, i) => {
    if (risk.quote && risk.quote.trim().length >= 5) {
      highlights.push({
        quote: risk.quote.trim(),
        color: HIGHLIGHT_COLORS[risk.severity] || HIGHLIGHT_COLORS.medium,
        id: `risk-${i}`,
        type: "risk",
      });
    }
  });

  (result.recommendations || []).forEach((rec, i) => {
    if (rec.quote && rec.quote.trim().length >= 5) {
      highlights.push({
        quote: rec.quote.trim(),
        color: HIGHLIGHT_COLORS[rec.category] || HIGHLIGHT_COLORS.general,
        id: `rec-${i}`,
        type: "recommendation",
      });
    }
  });

  if (highlights.length === 0) return;

  // Подсвечиваем каждую цитату через Word.run
  await Word.run(async (context) => {
    const body = context.document.body;

    for (const hl of highlights) {
      try {
        // Ищем цитату в документе
        const searchResults = body.search(hl.quote, { matchCase: false });
        context.load(searchResults, "items");
        await context.sync();

        // Подсвечиваем все вхождения (обычно 1)
        for (const range of searchResults.items) {
          range.font.highlightColor = hl.color;
        }
      } catch (e) {
        console.warn(`Не удалось подсветить: ${hl.quote.slice(0, 40)}...`, e);
      }
    }

    await context.sync();
  });
}

// Снять всю подсветку
async function clearHighlights() {
  try {
    await Word.run(async (context) => {
      const body = context.document.body;
      // Получаем весь документ и сбрасываем подсветку
      // (Word не умеет искать по цвету подсветки, поэтому сбрасываем на всём теле)
      const range = body.getRange();
      range.font.highlightColor = null;
      await context.sync();
    });
    showError(null);
    document.getElementById("result").classList.remove("active");
    document.getElementById("empty-state").style.display = "block";
  } catch (e) {
    showError("Не удалось очистить подсветку: " + e.message);
  }
}

// Прокрутить документ к выбранному риску/рекомендации
async function scrollToQuote(quote) {
  if (!quote) return;
  await Word.run(async (context) => {
    const results = context.document.body.search(quote, { matchCase: false });
    context.load(results, "items");
    await context.sync();
    if (results.items.length > 0) {
      results.items[0].select();
    }
  });
}

// ------------------------------------------------------------
//  Отрисовка отчёта в панели
// ------------------------------------------------------------

function renderReport(data) {
  const el = document.getElementById("result");
  const r = data.result;
  if (!r) {
    el.innerHTML = '<div class="empty">Результат недоступен</div>';
    return;
  }

  let html = "";

  // Резюме
  html += `<div class="section">
    <h3>Краткое резюме</h3>
    <div class="summary-box">${escapeHtml(r.summary)}</div>
  </div>`;

  // Рекомендации
  if (r.recommendations && r.recommendations.length) {
    html += `<div class="section">
      <h3>Рекомендации (${r.recommendations.length})</h3>`;
    r.recommendations.forEach((rec, i) => {
      const clickable = rec.quote ? `onclick="scrollToQuote(${escapeAttr(JSON.stringify(rec.quote))})"` : "";
      const hint = rec.quote ? `<span class="card-hint"> → к тексту</span>` : "";
      html += `<div class="card card-${rec.category}" ${clickable}>
        <div class="card-title">${escapeHtml(rec.text)}</div>
        <div class="card-meta">${CATEGORY_LABELS[rec.category] || rec.category}${hint}</div>
      </div>`;
    });
    html += `</div>`;
  }

  // Риски
  if (r.risks && r.risks.length) {
    html += `<div class="section">
      <h3>Выявленные риски (${r.risks.length})</h3>`;
    r.risks.forEach((risk, i) => {
      const clickable = risk.quote ? `onclick="scrollToQuote(${escapeAttr(JSON.stringify(risk.quote))})"` : "";
      const hint = risk.quote ? `<span class="card-hint"> → к тексту</span>` : "";
      html += `<div class="card card-risk-${risk.severity}" ${clickable}>
        <div class="card-title">
          ${escapeHtml(risk.text)}
          <span class="badge badge-risk-${risk.severity}">${SEVERITY_LABELS[risk.severity] || risk.severity}</span>
        </div>
        ${risk.quote ? `<div class="card-meta">«${escapeHtml(risk.quote.slice(0, 100))}»${hint}</div>` : ""}
      </div>`;
    });
    html += `</div>`;
  }

  // Нормы (кликабельны — открывают модалку)
  if (r.references && r.references.length) {
    html += `<div class="section">
      <h3>Нормы права (${r.references.length})</h3>`;
    r.references.forEach((ref) => {
      const sim = Math.round((ref.similarity || 0) * 100);
      const refData = escapeAttr(JSON.stringify(ref));
      html += `<div class="ref-item" onclick="openRef(${refData})">
        <div class="ref-title">
          ${escapeHtml(ref.title)}${ref.article_ref ? " · " + escapeHtml(ref.article_ref) : ""}
          <span class="ref-sim">${sim}%</span>
        </div>
        <div class="ref-quote">${escapeHtml(ref.quote.slice(0, 100))}…</div>
        <div class="sim-bar"><div class="sim-fill" style="width:${sim}%"></div></div>
      </div>`;
    });
    html += `</div>`;
  }

  // Судебная практика от ИИ (с предупреждением)
  if (r.case_law && r.case_law.length) {
    html += `<div class="section">
      <h3>Судебная практика (${r.case_law.length})</h3>
      <div class="warning-box">
        ⚠ Судебная практика предоставлена ИИ. Реквизиты дел требуют проверки
        по официальным источникам (sudact.ru, kad.arbitr.ru).
      </div>`;
    r.case_law.forEach((c) => {
      const verifyBadge = c.needs_verification ? `<span class="badge-warn">требует проверки</span>` : "";
      html += `<div class="card card-caselaw">
        <div class="card-title">
          ${escapeHtml(c.court || "Суд не указан")}
          ${c.case_number ? " · " + escapeHtml(c.case_number) : ""}
          ${c.date ? " · " + escapeHtml(c.date) : ""}
          ${verifyBadge}
        </div>
        <div class="card-meta" style="margin-top:5px;"><strong>Суть:</strong> ${escapeHtml(c.subject)}</div>
        ${c.ruling ? `<div class="card-meta" style="margin-top:3px;"><strong>Вывод суда:</strong> ${escapeHtml(c.ruling)}</div>` : ""}
        ${c.relevance ? `<div class="card-meta" style="margin-top:3px;"><strong>Релевантность:</strong> ${escapeHtml(c.relevance)}</div>` : ""}
      </div>`;
    });
    html += `</div>`;
  }

  el.innerHTML = html;
}

// ------------------------------------------------------------
//  Модальное окно для нормы права
// ------------------------------------------------------------

function openRef(ref) {
  document.getElementById("modal-title").textContent =
    ref.title + (ref.article_ref ? " · " + ref.article_ref : "");
  document.getElementById("modal-meta").textContent =
    (ref.doc_type || "") +
    (ref.similarity ? ` · релевантность ${Math.round(ref.similarity * 100)}%` : "");
  document.getElementById("modal-body").textContent = ref.quote;
  document.getElementById("ref-modal").classList.add("active");
}

function closeModal() {
  document.getElementById("ref-modal").classList.remove("active");
}

// Закрытие по Esc
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

// Закрытие по клику вне окна
document.getElementById("ref-modal").addEventListener("click", (e) => {
  if (e.target.id === "ref-modal") closeModal();
});

// ------------------------------------------------------------
//  Утилиты
// ------------------------------------------------------------

function showError(msg) {
  const el = document.getElementById("error");
  if (msg) {
    el.textContent = "⚠ " + msg;
    el.classList.add("active");
  } else {
    el.classList.remove("active");
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return String(str).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
