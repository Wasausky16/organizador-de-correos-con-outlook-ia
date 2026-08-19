console.log("🤖 [Extensión Asistente Local]: Sincronizador en segundo plano iniciado (Límite: Últimos 2 meses)...");

let lastMailHash = "";

function autoSyncOutlookEmails() {
  const emailRows = document.querySelectorAll('[role="option"], [role="listitem"], [data-convid], div[aria-label*="Message"]');
  const emails = [];

  // Límite de 60 días atrás desde la fecha actual
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - 60);

  emailRows.forEach((row, index) => {
    if (index > 150) return; // Escanear hasta 150 correos visibles conforme se desplaza en Outlook
    const textContent = row.innerText || "";
    let lines = textContent.split("\n").map(l => l.trim()).filter(l => l.length > 0);

    // Omitir iniciales del avatar (ej. "CP", "VA", "MP", "A", "AB", "UCSM")
    while (lines.length > 1) {
      const candidate = lines[0].trim();
      const nextLine = lines[1].trim();

      // Si candidate es de 1 a 3 caracteres en MAYÚSCULAS sin espacios ni @ (ej: "CP", "A", "MP")
      const isAvatarPattern = /^[A-Z0-9]{1,3}$/.test(candidate) && !candidate.includes("@");

      // O si candidate coincide con las iniciales del nombre completo en la siguiente línea
      const initialsOfNext = nextLine.split(/\s+/).map(w => w[0]).join('').toUpperCase();
      const isInitialsMatch = candidate.toUpperCase() === initialsOfNext || initialsOfNext.startsWith(candidate.toUpperCase());

      if (isAvatarPattern || (isInitialsMatch && candidate.length <= 4)) {
        lines.shift(); // Descartar la inicial del avatar
      } else {
        break;
      }
    }

    if (lines.length >= 2) {
      const senderName = lines[0] || "Remitente Outlook";
      const subject = lines[1] || "Sin asunto";
      const bodyPreview = lines.slice(2, 6).join(" ") || "Detalle del correo recibido.";

      // Buscar correo electrónico explícito en la fila del DOM
      const emailMatch = textContent.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
      let senderEmail = emailMatch ? emailMatch[0] : "";

      if (!senderEmail) {
        // Generar un correo consistente y válido a partir del nombre completo
        const cleanNameParts = senderName.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim().split(/\s+/);
        const emailUser = cleanNameParts.length >= 2 ? `${cleanNameParts[0]}.${cleanNameParts[1]}` : cleanNameParts[0];
        senderEmail = `${emailUser}@ucsm.edu.pe`;
      }

      const dateText = lines.find(l => l.match(/(\d{1,2}:\d{2})|(Ayer)|(Lun|Mar|Mié|Jue|Vie|Sáb|Dom)|(\d{1,2}\/\d{1,2}\/\d{2,4})/i)) || new Date().toLocaleDateString();

      emails.push({
        sender_name: senderName,
        sender_email: senderEmail,
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
