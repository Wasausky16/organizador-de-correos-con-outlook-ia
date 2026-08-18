// ==UserScript==
// @name         Sincronizador Automático de Outlook para Asistente Local
// @namespace    http://localhost:8050/
// @version      1.0
// @description  Sincroniza automáticamente los nuevos correos de Outlook Cloud con tu Asistente Inteligente Local cada 30 segundos
// @match        https://outlook.cloud.microsoft/mail/*
// @match        https://outlook.live.com/mail/*
// @match        https://outlook.office.com/mail/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    console.log("🤖 [Asistente Local]: Sincronizador en segundo plano activo...");

    let lastHash = "";

    function syncNewEmails() {
        const emailRows = document.querySelectorAll('[role="option"], [role="listitem"], [data-convid], div[aria-label*="Message"]');
        const emails = [];

        emailRows.forEach((row, index) => {
            if (index > 30) return; // Revisar los 30 más recientes
            const textContent = row.innerText || "";
            const lines = textContent.split("\n").map(l => l.trim()).filter(l => l.length > 0);

            if (lines.length >= 2) {
                const sender = lines[0] || "Remitente Outlook";
                const subject = lines[1] || "Sin asunto";
                const bodyPreview = lines.slice(2, 5).join(" ") || "Detalle del correo recibido.";

                emails.push({
                    sender_name: sender,
                    sender_email: sender.includes("@") ? sender : `${sender.toLowerCase().replace(/[^a-z0-9]/g, '')}@ucsm.edu.pe`,
                    subject: subject,
                    body: bodyPreview,
                    timestamp: new Date().toLocaleString()
                });
            }
        });

        if (emails.length === 0) return;

        const currentHash = JSON.stringify(emails.map(e => e.subject + e.timestamp));
        if (currentHash === lastHash) {
            // No hay cambios en la bandeja
            return;
        }
        lastHash = currentHash;

        // Enviar silenciosamente al servidor local
        fetch('http://localhost:8050/api/emails/sync_real', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emails: emails })
        })
        .then(r => r.json())
        .then(d => {
            if (d.synced_count > 0) {
                console.log(`✅ [Asistente Local]: Se ingresaron automáticamente ${d.synced_count} nuevos correos en segundo plano.`);
            }
        })
        .catch(err => {
            // Silencioso si el servidor local no responde
        });
    }

    // Ejecutar cada 20 segundos automáticamente en segundo plano
    setInterval(syncNewEmails, 20000);
    setTimeout(syncNewEmails, 4000);
})();
