// Script de Sincronización Directa para Navegador Brave
// Compatible con https://outlook.cloud.microsoft/mail/ y outlook.live.com

(function syncHotmailToLocalAssistant() {
  console.log("Iniciando sincronización desde Outlook Cloud Microsoft...");
  
  // Buscar filas de correos en el DOM de Outlook Web (cloud.microsoft & live)
  const emailRows = document.querySelectorAll('[role="option"], [role="listitem"], [data-convid], div[aria-label*="Message"]');
  const emails = [];

  emailRows.forEach((row, index) => {
    if (index > 25) return; // Limitar a los 25 correos más recientes
    const textContent = row.innerText || "";
    const lines = textContent.split("\n").map(l => l.trim()).filter(l => l.length > 0);

    if (lines.length >= 2) {
      const sender = lines[0] || "Remitente Outlook";
      const subject = lines[1] || "Sin asunto";
      const bodyPreview = lines.slice(2, 5).join(" ") || "Detalle del correo recibido.";

      emails.push({
        sender_name: sender,
        sender_email: sender.includes("@") ? sender : `${sender.toLowerCase().replace(/[^a-z0-9]/g, '')}@outlook.cloud.microsoft`,
        subject: subject,
        body: bodyPreview,
        timestamp: new Date().toLocaleString()
      });
    }
  });

  if (emails.length === 0) {
    alert("No se detectaron correos visibles en esta pestaña de Outlook Cloud. Asegúrate de estar en la Bandeja de Entrada de https://outlook.cloud.microsoft/mail/");
    return;
  }

  fetch('http://localhost:8050/api/emails/sync_real', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emails: emails })
  })
  .then(res => res.json())
  .then(data => {
    alert(`¡Éxito! Se han importado y clasificado ${data.synced_count} correos reales de tu Outlook Cloud (outlook.cloud.microsoft) en la memoria del Asistente.`);
  })
  .catch(err => {
    alert("Error al conectar con http://localhost:8050. Asegúrate de tener abierto el asistente local.");
  });
})();
