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
    const ariaLabel = row.getAttribute("aria-label") || "";
    const textContent = row.innerText || "";
    
    // 1. Extraer Email Explícito en el texto o aria-label
    const emailMatch = (ariaLabel + " " + textContent).match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
    let senderEmail = emailMatch ? emailMatch[0] : "";

    let lines = textContent.split("\n").map(l => l.trim()).filter(l => l.length > 0);

    // 2. Descartar iniciales del avatar (ej: "B", "A", "CP", "MP") o correos duplicados en primera línea
    while (lines.length > 1) {
      const candidate = lines[0];

      // Si candidate es de 1 a 3 caracteres en MAYÚSCULAS sin @ (ej: "B", "A", "CP")
      const isAvatarPattern = /^[A-Z0-9]{1,3}$/.test(candidate) && !candidate.includes("@");
      const isDuplicateEmail = candidate.toLowerCase() === senderEmail.toLowerCase();

      if (isAvatarPattern || isDuplicateEmail) {
        lines.shift(); // Descartar línea de avatar o email suelto
      } else {
        break;
      }
    }

    if (lines.length >= 2) {
      let senderName = lines[0] || "Remitente Outlook";
      let subject = lines[1] || "Sin asunto";
      let bodyStartIdx = 2;

      // Si senderName sigue siendo corto (<= 2 caracteres), avanzar al siguiente
      if (senderName.length <= 2 && lines.length > 1) {
        senderName = lines[1];
        subject = lines[2] || "Sin asunto";
        bodyStartIdx = 3;
      }

      // Si el asunto capturado contiene un email (ej: "bempleo@ucsm.edu.pe"), moverlo a senderEmail y corregir asunto
      if (subject.includes("@")) {
        if (!senderEmail) senderEmail = subject;
        subject = lines[bodyStartIdx] || "Notificación de Correo";
        bodyStartIdx++;
      }

      if (!senderEmail) {
        // Unir TODOS los nombres y apellidos sin cortar ni omitir ninguna palabra
        const normalizedName = senderName.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        const cleanNameParts = normalizedName.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim().split(/\s+/).filter(p => p.length > 0);
        const emailUser = cleanNameParts.join('.');
        senderEmail = `${emailUser}@est.ucsm.edu.pe`;
      }

      const bodyPreview = lines.slice(bodyStartIdx, bodyStartIdx + 4).join(" ") || "Detalle del correo recibido.";
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
