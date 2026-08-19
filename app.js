const API_BASE = "http://localhost:8050/api";

let globalEmails = [];
let globalTags = [];
let globalDeadlines = [];
let activeEmailForDraft = null;
let currentActiveFilter = "ALL";

// Utility: Extraer dirección de correo limpia (únicamente usuario@dominio.com)
function extractCleanEmailAddress(rawSender) {
  if (!rawSender) return "";
  const match = String(rawSender).match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
  if (match) return match[0];
  return String(rawSender).trim();
}

document.addEventListener("DOMContentLoaded", () => {
  loadTodaySummary();
  loadEmails();
  loadMemory();
  loadFaqs();
  loadDeadlines();
  loadTags();

  // Refrescar el Dashboard en tiempo real cada 15 segundos
  setInterval(() => {
    loadTodaySummary();
    loadEmails();
    loadMemory();
    loadDeadlines();
  }, 15000);
});

// Refrescar todos los módulos con animación visual
async function refreshAllData(btn) {
  if (btn) btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Actualizando...`;
  try {
    await Promise.all([
      loadTodaySummary(),
      loadEmails(),
      loadDeadlines(),
      loadTags(),
      loadMemory()
    ]);
  } catch (e) {
    console.error("Error al refrescar:", e);
  }
  if (btn) {
    setTimeout(() => {
      btn.innerHTML = `<i class="fa-solid fa-check" style="color: #2ed573;"></i> ¡Actualizado!`;
      setTimeout(() => {
        btn.innerHTML = `<i class="fa-solid fa-rotate"></i> Actualizar`;
      }, 1200);
    }, 200);
  }
}

// Cargar Vencimientos del Calendario
async function loadDeadlines() {
  try {
    const res = await fetch(`${API_BASE}/deadlines`);
    globalDeadlines = await res.json();

    document.getElementById("count-deadlines").innerText = globalDeadlines.length;

    // Renderizar panel lateral
    const sideContainer = document.getElementById("sidebar-deadline-container");
    sideContainer.innerHTML = "";

    if (globalDeadlines.length === 0) {
      sideContainer.innerHTML = `<div style="font-size: 0.85rem; color: var(--text-dim); padding: 0.5rem 0;">No hay tareas ni vencimientos pendientes.</div>`;
    } else {
      globalDeadlines.forEach(item => {
        const div = document.createElement("div");
        div.className = `deadline-item ${item.urgency_level}`;
        div.style.cursor = "pointer";
        div.title = "Haz clic para ver y responder este correo de inmediato";
        div.onclick = () => {
          openDraftModal(item.email_id);
        };

        const daysLabel = item.urgency_level === 'RED' ? '🔴 Urgente' : (item.urgency_level === 'YELLOW' ? '🟡 Próximo' : '🟢 Tiempo');
        div.innerHTML = `
          <div class="deadline-title"><i class="fa-solid fa-envelope" style="color: var(--primary-cyan); margin-right: 4px;"></i> ${escapeHtml(item.title)}</div>
          <div class="deadline-date">
            <span><i class="fa-regular fa-clock"></i> ${item.due_date}</span>
            <span style="font-weight:700;">${daysLabel}</span>
          </div>
        `;
        sideContainer.appendChild(div);
      });
    }

    // Renderizar pestaña completa de calendario
    const fullContainer = document.getElementById("full-deadlines-list");
    if (fullContainer) {
      fullContainer.innerHTML = "";
      if (globalDeadlines.length === 0) {
        fullContainer.innerHTML = `<div style="text-align: center; color: var(--text-dim); padding: 3rem;">¡Excelente! No hay fechas límite ni tareas pendientes.</div>`;
      } else {
        globalDeadlines.forEach(item => {
          const card = document.createElement("div");
          card.className = "email-card";
          card.innerHTML = `
            <div>
              <span class="priority-badge ${item.urgency_level === 'RED' ? 'HIGH' : 'MEDIUM'}">${item.urgency_level === 'RED' ? '🔴 VENCE PRONTO' : '🟡 PROGRAMADO'}</span>
            </div>
            <div class="email-content">
              <div class="email-subject"><i class="fa-solid fa-calendar-check" style="color: var(--primary-cyan);"></i> ${escapeHtml(item.title)}</div>
              <div class="email-body">Fecha límite de atención: <strong>${item.due_date}</strong></div>
              <div class="email-footer-tags">
                <span class="tag action"><i class="fa-solid fa-bell"></i> Evento activo en Calendario</span>
              </div>
            </div>
            <div class="email-actions">
              <button class="btn btn-primary" onclick="openDraftModal('${item.email_id}')">
                <i class="fa-solid fa-check"></i> Atender y Resolver
              </button>
            </div>
          `;
          fullContainer.appendChild(card);
        });
      }
    }
  } catch (err) {
    console.error("Error al cargar vencimientos del calendario:", err);
  }
}

// Cargar Etiquetas Personalizadas (#Tags)
async function loadTags() {
  try {
    const res = await fetch(`${API_BASE}/tags`);
    globalTags = await res.json();

    const container = document.getElementById("tags-grid-container");
    const filterBar = document.getElementById("inbox-filter-bar");
    container.innerHTML = "";

    globalTags.forEach(tag => {
      const card = document.createElement("div");
      card.className = "memory-card";
      card.innerHTML = `
        <div class="memory-header">
          <span class="contact-name" style="color: ${tag.color}; font-size: 1.2rem;">${escapeHtml(tag.name)}</span>
        </div>
        <div class="memory-notes">
          <strong>Palabras Clave de Auto-Etiquetado:</strong><br>
          ${escapeHtml(tag.keywords)}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error al cargar etiquetas:", err);
  }
}

// Generar Tarjetas de Correo con Badges de Adjuntos e Iconos
function createEmailCard(email) {
  const card = document.createElement("div");
  card.className = "email-card";

  const priorityLabel = email.priority === "HIGH" ? "ALTA" : (email.priority === "MEDIUM" ? "MEDIA" : "BAJA");
  
  // Detectar si el texto menciona archivos adjuntos (.md, .pdf, .docx)
  let attachmentBadgesHTML = "";
  if (email.body.includes(".pdf") || email.subject.includes(".pdf")) {
    attachmentBadgesHTML += `<span class="attachment-badge pdf"><i class="fa-solid fa-file-pdf"></i> Documento PDF</span> `;
  }
  if (email.body.includes(".md") || email.subject.includes(".md")) {
    attachmentBadgesHTML += `<span class="attachment-badge md"><i class="fa-solid fa-file-code"></i> Plan de Tesis (.md)</span> `;
  }

  card.innerHTML = `
    <div>
      <span class="priority-badge ${email.priority}">🔴 ${priorityLabel}</span>
    </div>
    <div class="email-content">
      <div class="sender-info">
        <span class="sender-name">${escapeHtml(email.sender_name)}</span>
        <span class="sender-email">&lt;${escapeHtml(email.sender_email)}&gt;</span>
      </div>
      <div class="email-subject">${escapeHtml(email.subject)}</div>
      <div class="email-body">${escapeHtml(email.body)}</div>
      <div class="email-footer-tags">
        <span class="tag" style="background: rgba(0, 229, 255, 0.15); color: var(--primary-cyan); font-weight:700;">${email.category}</span>
        ${attachmentBadgesHTML}
        <span class="tag action"><i class="fa-solid fa-lightbulb"></i> ${escapeHtml(email.action_item)}</span>
      </div>
    </div>
    <div class="email-actions">
      <span class="time-stamp">${email.timestamp}</span>
      ${email.status === 'RESPONDED' ? 
        `<span class="tag" style="color: var(--priority-low);"><i class="fa-solid fa-check-double"></i> Respondido / Resuelto</span>` :
        `<button class="btn btn-primary" onclick="openDraftModal('${email.id}')">
          <i class="fa-solid fa-pen-to-square"></i> Ver Borrador
        </button>`
      }
    </div>
  `;

  return card;
}

// Navegación por pestañas
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));

  const targetContent = document.getElementById(tabId);
  if (targetContent) targetContent.classList.add("active");

  const activeBtn = Array.from(document.querySelectorAll(".tab-btn")).find(btn => 
    btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(tabId)
  );
  if (activeBtn) activeBtn.classList.add("active");
}

// Saltar directamente desde una tarjeta de métrica a la bandeja filtrada
function jumpToFilter(priority) {
  switchTab('tab-inbox');
  const buttons = document.querySelectorAll(".filter-buttons .filter-btn");
  let matchedBtn = null;
  buttons.forEach(btn => {
    if (btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(`'${priority}'`)) {
      matchedBtn = btn;
    }
  });
  filterEmails(priority, matchedBtn);
}

// Cargar Resumen Ejecutivo Diario
async function loadTodaySummary() {
  try {
    const res = await fetch(`${API_BASE}/summary/today`);
    const data = await res.json();

    document.getElementById("stat-high").innerText = data.high_count || 0;
    document.getElementById("stat-med").innerText = data.med_count || 0;
    document.getElementById("stat-low").innerText = data.low_count || 0;
    document.getElementById("stat-total").innerText = data.total || 0;

    document.getElementById("digest-summary-text").innerText = data.summary_text || "Sin novedades reportadas.";

    const actionContainer = document.getElementById("action-items-container");
    actionContainer.innerHTML = "";
    
    if (data.pending_actions && data.pending_actions.length > 0) {
      data.pending_actions.forEach(action => {
        const item = document.createElement("div");
        item.className = "action-item";
        item.innerHTML = `<i class="fa-solid fa-arrow-right-long" style="color: var(--priority-high);"></i> <span>${action}</span>`;
        actionContainer.appendChild(item);
      });
    } else {
      actionContainer.innerHTML = `<div class="action-item" style="border-left-color: var(--priority-low);">
        <i class="fa-solid fa-check" style="color: var(--priority-low);"></i> <span>¡Felicidades! No hay acciones pendientes urgentes por responder.</span>
      </div>`;
    }
  } catch (err) {
    console.error("Error al cargar resumen diario:", err);
  }
}

// Cargar Bandeja de Correos
async function loadEmails() {
  try {
    const res = await fetch(`${API_BASE}/emails`);
    globalEmails = await res.json();

    document.getElementById("count-inbox").innerText = globalEmails.length;
    applyActiveFilter();
  } catch (err) {
    console.error("Error al cargar correos:", err);
  }
}

function filterEmails(priority, btnElement) {
  currentActiveFilter = priority;
  document.querySelectorAll(".filter-buttons .filter-btn").forEach(b => b.classList.remove("active"));
  if (btnElement) {
    btnElement.classList.add("active");
  } else {
    // Buscar y marcar el botón si fue llamado externamente
    const buttons = document.querySelectorAll(".filter-buttons .filter-btn");
    buttons.forEach(btn => {
      if (btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(`'${priority}'`)) {
        btn.classList.add("active");
      }
    });
  }

  applyActiveFilter();
}

function applyActiveFilter() {
  if (currentActiveFilter === "ALL") {
    renderEmailLists(globalEmails);
  } else if (currentActiveFilter === "PENDING") {
    const filtered = globalEmails.filter(e => e.status === "PENDING" || e.status === "DRAFT_READY");
    renderEmailLists(filtered);
  } else {
    const filtered = globalEmails.filter(e => e.priority === currentActiveFilter);
    renderEmailLists(filtered);
  }
}

function renderEmailLists(emails) {
  const fullContainer = document.getElementById("full-email-list");
  const urgentContainer = document.getElementById("urgent-email-list");

  fullContainer.innerHTML = "";
  if (urgentContainer) urgentContainer.innerHTML = "";

  if (emails.length === 0) {
    fullContainer.innerHTML = `<div style="text-align: center; color: var(--text-dim); padding: 3rem;">No hay correos para mostrar.</div>`;
    return;
  }

  emails.forEach(email => {
    const card = createEmailCard(email);
    fullContainer.appendChild(card);

    // Agregar a la sección de urgentes si es de Alta Prioridad
    if (urgentContainer && email.priority === "HIGH" && email.status !== "RESPONDED") {
      const urgentCard = createEmailCard(email);
      urgentContainer.appendChild(urgentCard);
    }
  });
}

function createEmailCard(email) {
  const card = document.createElement("div");
  card.className = "email-card";

  const priorityLabel = email.priority === "HIGH" ? "ALTA" : (email.priority === "MEDIUM" ? "MEDIA" : "BAJA");
  
  card.innerHTML = `
    <div>
      <span class="priority-badge ${email.priority}">🔴 ${priorityLabel}</span>
    </div>
    <div class="email-content">
      <div class="sender-info">
        <span class="sender-name">${escapeHtml(email.sender_name)}</span>
        <span class="sender-email">&lt;${escapeHtml(email.sender_email)}&gt;</span>
      </div>
      <div class="email-subject">${escapeHtml(email.subject)}</div>
      <div class="email-body">${escapeHtml(email.body)}</div>
      <div class="email-footer-tags">
        <span class="tag">Categoría: ${email.category}</span>
        <span class="tag action"><i class="fa-solid fa-lightbulb"></i> ${escapeHtml(email.action_item)}</span>
      </div>
    </div>
    <div class="email-actions">
      <span class="time-stamp">${email.timestamp}</span>
      ${email.status === 'RESPONDED' ? 
        `<span class="tag" style="color: var(--priority-low);"><i class="fa-solid fa-check-double"></i> Respondido</span>` :
        `<button class="btn btn-primary" onclick="openDraftModal('${email.id}')">
          <i class="fa-solid fa-pen-to-square"></i> Ver Borrador
        </button>`
      }
    </div>
  `;

  return card;
}

// Filtros y Búsqueda
function filterEmails(priority, btnElement) {
  document.querySelectorAll(".filter-buttons .filter-btn").forEach(b => b.classList.remove("active"));
  if (btnElement) btnElement.classList.add("active");

  if (priority === "ALL") {
    renderEmailLists(globalEmails);
  } else if (priority === "PENDING") {
    const filtered = globalEmails.filter(e => e.status === "PENDING" || e.status === "DRAFT_READY");
    renderEmailLists(filtered);
  } else {
    const filtered = globalEmails.filter(e => e.priority === priority);
    renderEmailLists(filtered);
  }
}

function searchEmails(query) {
  const q = query.toLowerCase();
  const filtered = globalEmails.filter(e => 
    e.subject.toLowerCase().includes(q) || 
    e.sender_name.toLowerCase().includes(q) || 
    e.sender_email.toLowerCase().includes(q)
  );
  renderEmailLists(filtered);
}

// Cargar Memoria de Contactos
async function loadMemory() {
  try {
    const res = await fetch(`${API_BASE}/memory`);
    const memory = await res.json();

    const container = document.getElementById("memory-grid-container");
    container.innerHTML = "";

    memory.forEach(item => {
      const card = document.createElement("div");
      card.className = "memory-card";
      card.innerHTML = `
        <div class="memory-header">
          <span class="contact-name">${escapeHtml(item.name)}</span>
          ${item.vip ? `<span class="vip-star" title="Contacto VIP"><i class="fa-solid fa-star"></i> VIP</span>` : ''}
        </div>
        <div class="memory-company">${escapeHtml(item.company || 'Empresa Independiente')}</div>
        <div class="memory-notes">
          <i class="fa-solid fa-brain" style="color: var(--primary-cyan);"></i> <strong>Notas de Memoria:</strong><br>
          ${escapeHtml(item.notes)}
        </div>
        <div class="memory-meta">
          <span>Interacciones: <strong>${item.interaction_count}</strong></span>
          <span>Última: ${item.last_interaction}</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error al cargar memoria:", err);
  }
}

// Cargar FAQs
async function loadFaqs() {
  try {
    const res = await fetch(`${API_BASE}/faqs`);
    const faqs = await res.json();

    const container = document.getElementById("faq-list-container");
    container.innerHTML = "";

    faqs.forEach(faq => {
      const card = document.createElement("div");
      card.className = "faq-card";
      card.innerHTML = `
        <span class="faq-keywords">Palabras clave: ${escapeHtml(faq.keywords)}</span>
        <div class="faq-question"><i class="fa-solid fa-circle-question" style="color: var(--primary-cyan);"></i> ${escapeHtml(faq.question)}</div>
        <div class="faq-template">${escapeHtml(faq.auto_response_template)}</div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error al cargar FAQs:", err);
  }
}

// Modal de Borrador
function openDraftModal(emailId) {
  const email = globalEmails.find(e => e.id === emailId);
  if (!email) return;

  activeEmailForDraft = email;

  document.getElementById("draft-recipient").value = `${email.sender_name} <${email.sender_email}>`;
  document.getElementById("draft-subject").value = `Re: ${email.subject}`;
  document.getElementById("draft-body").value = email.auto_reply_draft || `Hola ${email.sender_name},\n\nHemos recibido tu mensaje y lo estamos atendiendo.`;

  const modal = document.getElementById("modal-draft");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("active");
  }
}

function confirmSendResponse() {
  try {
    if (!activeEmailForDraft) {
      closeModal("modal-draft");
      return;
    }

    const subjectInput = document.getElementById("draft-subject");
    const bodyInput = document.getElementById("draft-body");

    const subjectText = subjectInput ? subjectInput.value : `Re: ${activeEmailForDraft.subject}`;
    const draftBodyText = bodyInput ? bodyInput.value : (activeEmailForDraft.auto_reply_draft || "");
    const cleanRecipientEmail = extractCleanEmailAddress(activeEmailForDraft.sender_email);

    // 1. Construir la URL directa de redacción en Outlook Cloud
    const composeUrl = `https://outlook.cloud.microsoft/mail/deeplink/compose?to=${encodeURIComponent(cleanRecipientEmail)}&subject=${encodeURIComponent(subjectText)}&body=${encodeURIComponent(draftBodyText)}`;

    // 2. Cerrar el modal en pantalla DE INMEDIATO
    closeModal("modal-draft");

    // 3. Notificar al backend local en segundo plano
    fetch(`${API_BASE}/emails/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: activeEmailForDraft.id, status: "RESPONDED" })
    }).catch(err => console.error("Status update error:", err));

    // 4. Copiar texto al portapapeles en segundo plano
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(draftBodyText).catch(e => console.log("Clipboard copy:", e));
    }

    // 5. Abrir la pestaña oficial de envío en Outlook Cloud
    const targetWin = window.open(composeUrl, "_blank", "noopener");
    if (!targetWin) {
      window.open(composeUrl, "_self");
    }

    // 6. Recargar las métricas de la bandeja local
    setTimeout(() => {
      loadTodaySummary();
      loadEmails();
      loadDeadlines();
    }, 400);
  } catch (err) {
    console.error("Error en confirmSendResponse:", err);
    closeModal("modal-draft");
  }
}

// Modal Simular Correo Entrante
function openSimulateModal() {
  document.getElementById("modal-simulate").classList.add("active");
}

async function submitSimulatedEmail() {
  const name = document.getElementById("sim-name").value.trim();
  const email = document.getElementById("sim-email").value.trim();
  const subject = document.getElementById("sim-subject").value.trim();
  const body = document.getElementById("sim-body").value.trim();

  if (!name || !email || !subject) {
    alert("Por favor completa al menos Nombre, Correo y Asunto.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/emails/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender_name: name, sender_email: email, subject: subject, body: body })
    });

    const data = await res.json();
    closeModal("modal-simulate");
    
    // Limpiar formulario
    document.getElementById("sim-name").value = "";
    document.getElementById("sim-email").value = "";
    document.getElementById("sim-subject").value = "";
    document.getElementById("sim-body").value = "";

    loadTodaySummary();
    loadEmails();
    loadMemory();
    alert(`¡Correo procesado! Clasificado automáticamente como Prioridad ${data.priority}.`);
  } catch (err) {
    console.error("Error al simular correo:", err);
  }
}

// Modal Agregar FAQ
function openAddFaqModal() {
  document.getElementById("modal-add-faq").classList.add("active");
}

async function submitNewFaq() {
  const keywords = document.getElementById("faq-keywords").value.trim();
  const question = document.getElementById("faq-question").value.trim();
  const template = document.getElementById("faq-template").value.trim();

  if (!keywords || !question || !template) {
    alert("Por favor llena todos los campos de la regla FAQ.");
    return;
  }

  try {
    await fetch(`${API_BASE}/faqs/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keywords, question, auto_response_template: template })
    });

    closeModal("modal-add-faq");
    loadFaqs();
    alert("¡Regla FAQ añadida exitosamente!");
  } catch (err) {
    console.error("Error al agregar FAQ:", err);
  }
}

// Exportar e Importar Memoria (Portabilidad)
function exportBackup() {
  window.open(`${API_BASE}/export`, "_blank");
}

async function importBackup(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const data = JSON.parse(e.target.result);
      const res = await fetch(`${API_BASE}/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      if (res.ok) {
        alert("¡Memoria e historial importados con éxito desde la copia de respaldo!");
        loadTodaySummary();
        loadEmails();
        loadMemory();
        loadFaqs();
      }
    } catch (err) {
      alert("Error al procesar el archivo de respaldo.");
    }
  };
  reader.readAsText(file);
}

function openBraveSyncGuide() {
  document.getElementById("modal-brave-sync").classList.add("active");
}

function copyBraveScript() {
  const box = document.getElementById("brave-script-box");
  box.select();
  document.execCommand("copy");
  alert("¡Código copiado! Pégalo en la consola F12 de tu Outlook y presiona Enter.");
}

async function pasteAndSyncFromClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    let emails = [];
    
    try {
      emails = JSON.parse(text);
    } catch (e) {
      alert("No se encontraron datos válidos en el portapapeles. Asegúrate de haber ejecutado el código en la consola de Outlook primero.");
      return;
    }

    if (!Array.isArray(emails) || emails.length === 0) {
      alert("El contenido copiado no contiene correos. Ejecuta el código en la consola de Outlook nuevamente.");
      return;
    }

    const res = await fetch(`${API_BASE}/emails/sync_real`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ emails: emails })
    });

    const data = await res.json();
    closeModal("modal-brave-sync");
    loadTodaySummary();
    loadEmails();
    loadMemory();
    alert(`¡Éxito Total! Se han importado y clasificado ${data.synced_count} correos reales de tu Outlook en la memoria del Asistente.`);
  } catch (err) {
    alert("Para pegar automáticamente, concede permiso al navegador o asegúrate de haber copiado los correos.");
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
  if (modalId === "modal-draft") {
    activeEmailForDraft = null;
  }
}

function openDrawer(drawerId) {
  const drawer = document.getElementById(drawerId);
  if (drawer) drawer.classList.add("active");
}

function closeDrawer(drawerId) {
  const drawer = document.getElementById(drawerId);
  if (drawer) drawer.classList.remove("active");
}

async function purgeCache() {
  if (!confirm("¿Estás seguro de que deseas borrar la caché y reiniciar la memoria local desde cero?")) return;
  try {
    const res = await fetch(`${API_BASE}/cache/purge`, { method: "POST" });
    const data = await res.json();
    alert("✅ " + (data.message || "Caché de base de datos borrada con éxito."));
    closeDrawer("drawer-options");
    refreshAllData();
  } catch (err) {
    console.error("Error al borrar caché:", err);
    alert("Ocurrió un error al intentar borrar la caché.");
  }
}

function openAddTagModal() {
  document.getElementById("modal-add-tag").classList.add("active");
}

async function submitNewTag() {
  const name = document.getElementById("tag-name").value.trim();
  const color = document.getElementById("tag-color").value.trim();
  const keywords = document.getElementById("tag-keywords").value.trim();

  if (!name) {
    alert("Por favor ingresa un nombre para la etiqueta (ej: #Tesis).");
    return;
  }

  try {
    await fetch(`${API_BASE}/tags/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, color, keywords })
    });

    closeModal("modal-add-tag");
    loadTags();
    alert(`¡Etiqueta ${name} creada exitosamente! Culaquier usuario puede personalizar etiquetas.`);
  } catch (err) {
    console.error("Error al guardar etiqueta:", err);
  }
}

function escapeHtml(text) {
  if (!text) return "";
  return text.replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
}

async function saveBackgroundImapConfig() {
  const enabled = document.getElementById("bg-sync-enable").checked;
  const server = document.getElementById("bg-imap-server").value.trim() || "outlook.office365.com";
  const email = document.getElementById("bg-imap-email").value.trim() || "luis.merma@est.ucsm.edu.pe";
  const password = document.getElementById("bg-imap-password").value.trim();

  try {
    const res = await fetch(`${API_BASE}/config/imap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled, server, email, password })
    });

    const data = await res.json();
    alert("¡Configuración de Sincronización en Segundo Plano Guardada!\n\nEl servidor Python revisará automáticamente tu bandeja de entrada en segundo plano.");
    loadTodaySummary();
    loadEmails();
  } catch (err) {
    alert("Error al guardar configuración de segundo plano.");
  }
}
