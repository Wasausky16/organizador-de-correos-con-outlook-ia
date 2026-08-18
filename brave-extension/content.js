console.log("🤖 [Extensión Asistente Local]: Sincronizador en segundo plano iniciado (Límite: Últimos 2 meses)...");

let lastMailHash = "";

function autoSyncOutlookEmails() {
  const emailRows = document.querySelectorAll('[role="option"], [role="listitem"], [data-convid], div[aria-label*="Message"]');
  const emails = [];

  // Límite de 60 días atrás desde la fecha actual
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - 60);

  emailRows.forEach((row, index) => {
    if (index > 25) return; // Limitar a los 25 más recientes de la bandeja
    const textContent = row.innerText || "";
    const lines = textContent.split("\n").map(l => l.trim()).filter(l => l.length > 0);

    if (lines.length >= 2) {
      const sender = lines[0] || "Remitente Outlook";
      const subject = lines[1] || "Sin asunto";
      const bodyPreview = lines.slice(2, 5).join(" ") || "Detalle del correo recibido.";
      const dateText = lines.find(l => l.match(/(\d{1,2}:\d{2})|(Ayer)|(Lun|Mar|Mié|Jue|Vie|Sáb|Dom)|(\d{1,2}\/\d{1,2}\/\d{2,4})/i)) || new Date().toLocaleDateString();

      emails.push({
        sender_name: sender,
        sender_email: sender.includes("@") ? sender : `${sender.toLowerCase().replace(/[^a-z0-9]/g, '')}@ucsm.edu.pe`,
        subject: subject,
        body: bodyPreview,
        timestamp: dateText
      });
    }
  });

  if (emails.length === 0) return;

  const currentHash = JSON.stringify(emails.map(e => e.subject + e.timestamp));
  if (currentHash === lastMailHash) return;

  fetch('http://localhost:8050/api/emails/sync_real', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emails: emails })
  })
  .then(r => r.json())
  .then(data => {
    lastMailHash = currentHash;
    if (data.synced_count > 0) {
      console.log(`✅ [Extensión Asistente]: Se ingresaron automáticamente ${data.synced_count} nuevos correos recientes (últimos 2 meses).`);
    }
  })
  .catch(err => {
    // Servidor local disponible en http://localhost:8050
  });
}

// Ejecutar automáticamente cada 15 segundos en segundo plano
setInterval(autoSyncOutlookEmails, 15000);
setTimeout(autoSyncOutlookEmails, 3000);
