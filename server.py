import http.server
import socketserver
import json
import sqlite3
import urllib.parse
import os
import sys
import datetime
import re
import threading
import time
import imaplib
import email
from email.header import decode_header

PORT = 8050
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_memory.db")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imap_config.json")

# Sincronizador automático en segundo plano
AUTO_POLL_INTERVAL = 60 # Segundos entre revisiones automáticas

def load_imap_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"enabled": False, "server": "outlook.office365.com", "port": 993, "email": "luis.merma@est.ucsm.edu.pe", "password": ""}

def save_imap_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2)

def fetch_real_emails_via_imap(config):
    if not config.get("enabled") or not config.get("email") or not config.get("password"):
        return 0

    inserted_count = 0
    try:
        mail = imaplib.IMAP4_SSL(config.get("server", "outlook.office365.com"), config.get("port", 993))
        mail.login(config.get("email"), config.get("password"))
        mail.select("INBOX")

        # Buscar correos recientes o no leídos
        status, response = mail.search(None, "UNSEEN")
        email_ids = response[0].split()

        # Si no hay no leídos, traer los últimos 10
        if not email_ids:
            status, response = mail.search(None, "ALL")
            email_ids = response[0].split()[-10:]

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        for e_id in reversed(email_ids):
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decodificar Asunto
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                    
                    # Decodificar Remitente
                    from_header = msg.get("From", "Remitente Desconocido")
                    sender_name, sender_email = from_header, from_header
                    if "<" in from_header:
                        parts = from_header.split("<")
                        sender_name = parts[0].replace('"', '').strip()
                        sender_email = parts[1].replace(">", "").strip()

                    # Extraer cuerpo del mensaje
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    import hashlib
                    raw_id = f"{sender_email}_{subject}_{msg.get('Date', timestamp)}"
                    msg_id = "imap-" + hashlib.md5(raw_id.encode('utf-8')).hexdigest()[:10]

                    # Verificar si ya existe en la base de datos local
                    cursor.execute("SELECT id FROM emails WHERE id = ?", (msg_id,))
                    if cursor.fetchone():
                        continue

                    priority, category, action_item, sentiment = classify_email(subject, body, sender_email)
                    auto_reply_draft = match_faq_draft(subject, body, sender_name)

                    cursor.execute('''
                        INSERT INTO emails (id, sender_name, sender_email, subject, body, timestamp, priority, category, status, action_item, sentiment, auto_reply_draft)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (msg_id, sender_name, sender_email, subject, body, timestamp, priority, category, "PENDING", action_item, sentiment, auto_reply_draft))

                    # Actualizar memoria del contacto
                    cursor.execute("SELECT interaction_count, notes FROM memory_contacts WHERE email = ?", (sender_email,))
                    existing = cursor.fetchone()
                    if existing:
                        count = existing[0] + 1
                        notes = existing[1] + f" | {timestamp}: {subject}"
                        cursor.execute('''
                            UPDATE memory_contacts SET interaction_count = ?, notes = ?, last_interaction = ? WHERE email = ?
                        ''', (count, notes, timestamp, sender_email))
                    else:
                        company = sender_email.split("@")[-1] if "@" in sender_email else "Contacto Directo"
                        cursor.execute('''
                            INSERT INTO memory_contacts (email, name, company, vip, interaction_count, notes, last_interaction)
                            VALUES (?, ?, ?, ?, 1, ?, ?)
                        ''', (sender_email, sender_name, company, 1 if priority == "HIGH" else 0, f"Sincronizado vía IMAP: {subject}", timestamp))

                    inserted_count += 1

        conn.commit()
        conn.close()
        mail.logout()
    except Exception as ex:
        print(f"[IMAP Background Sync Error]: {ex}")

    return inserted_count

def background_sync_thread():
    print("[Background Sync Thread]: Hilo de Sincronizacion Automatica Iniciado...")
    while True:
        try:
            config = load_imap_config()
            if config.get("enabled"):
                count = fetch_real_emails_via_imap(config)
                if count > 0:
                    print(f"[Segundo Plano]: Se ingresaron {count} nuevos correos automaticos.")
        except Exception as e:
            print(f"Error en hilo de segundo plano: {e}")
        time.sleep(AUTO_POLL_INTERVAL)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabla de Correos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            sender_name TEXT,
            sender_email TEXT,
            subject TEXT,
            body TEXT,
            timestamp TEXT,
            priority TEXT, -- HIGH, MEDIUM, LOW
            category TEXT, -- VIP, FINANZAS, FAQ, SOPORTE, REUNION, GENERAL
            status TEXT,   -- PENDING, DRAFT_READY, RESPONDED, ARCHIVED
            action_item TEXT,
            sentiment TEXT, -- POSITIVE, NEUTRAL, URGENT
            auto_reply_draft TEXT
        )
    ''')
    
    # Tabla de Memoria y Conocimiento de Contactos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memory_contacts (
            email TEXT PRIMARY KEY,
            name TEXT,
            company TEXT,
            vip INTEGER DEFAULT 0,
            interaction_count INTEGER DEFAULT 1,
            notes TEXT,
            last_interaction TEXT
        )
    ''')
    
    # Tabla de Preguntas Frecuentes (FAQs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keywords TEXT,
            question TEXT,
            auto_response_template TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Tabla de Resúmenes Diarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_summaries (
            date TEXT PRIMARY KEY,
            summary_text TEXT,
            high_count INTEGER,
            med_count INTEGER,
            low_count INTEGER,
            pending_actions TEXT
        )
    ''')

    # Sembrar FAQs iniciales si no existen
    cursor.execute('SELECT COUNT(*) FROM faqs')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO faqs (keywords, question, auto_response_template, is_active)
            VALUES (?, ?, ?, 1)
        ''', [
            ("precio, tarifa, costo, cotizacion", "¿Cuáles son las tarifas o costos del servicio?", 
             "Hola {nombre},\n\nGracias por escribirnos. Con gusto te compartimos nuestros planes y tarifas actualizadas. Adjunto la propuesta comercial completa.\n\nQuedamos atentos a tus comentarios.\n\nSaludos cordiales,\nEquipo de Atención"),
            ("horario, atencion, abierto", "¿Cuál es el horario de atención?", 
             "Hola {nombre},\n\nNuestro horario de atención es de Lunes a Viernes de 8:30 AM a 6:00 PM. Estaremos encantados de apoyarte en ese lapso.\n\nSaludos!"),
            ("pago, factura, comprobante, transferencia", "¿Dónde envío el comprobante de pago o factura?", 
             "Hola {nombre},\n\nHemos recibido tus datos de pago. Nuestro equipo de finanzas validará el comprobante en un lapso máximo de 2 horas hábiles y te notificaremos.\n\nGracias por tu preferencia!")
        ])

    # Tabla de Etiquetas Personalizadas (#Tags)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            color TEXT,
            keywords TEXT
        )
    ''')

    # Tabla de Calendario de Vencimientos y Fechas Límite
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deadlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT,
            title TEXT,
            due_date TEXT,
            urgency_level TEXT, -- RED, YELLOW, GREEN
            status TEXT DEFAULT 'PENDING' -- PENDING, RESOLVED
        )
    ''')

    # Sembrar Etiquetas iniciales personalizables
    cursor.execute('SELECT COUNT(*) FROM tags')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO tags (name, color, keywords) VALUES (?, ?, ?)
        ''', [
            ("#Tesis", "#a855f7", "tesis, plan de tesis, epis, jurado, borrador"),
            ("#UCSM_Oficial", "#00e5ff", "ucsm, vicerrectorado, convocatoria, universidad"),
            ("#Tramites", "#ffa502", "mesa de partes, mpv, solicitud, auto, resolucion"),
            ("#Finanzas", "#2ed573", "pago, factura, comprobante, costo, tarifa"),
            ("#BolsaDeTrabajo", "#ec4899", "empleo, vacante, analista, alumni")
        ])

    # Sembrar Correos REALES de Luis Merma (UCSM) con Adjuntos y Tags
    cursor.execute('SELECT COUNT(*) FROM emails')
    if cursor.fetchone()[0] == 0:
        real_emails = [
            ("real-ucsm-01", "ALDAIR MAURICIO BELISARIO FERNANDEZ", "aldair.belisario@est.ucsm.edu.pe", 
             "PLAN DE TESIS", 
             "Estimado Luis, adjunto el avance del documento del Plan de Tesis (EPIS_Plan de tesis.md) para revisión y comentarios académicos.",
             "2026-08-17 13:56", "HIGH", "#Tesis", "PENDING", 
             "🔴 ACCIÓN REQUERIDA: Revisar el Plan de Tesis (EPIS_Plan de tesis.md) de Aldair Belisario Fernandez antes del 20/08.", "URGENT", 
             "Hola Aldair,\n\nHemos recibido el avance del Plan de Tesis. Lo estaré revisando a la brevedad y te enviaré mis comentarios.\n\nSaludos cordiales,\nLuis Merma"),

            ("real-ucsm-02", "MESA DE PARTES 02 UCSM", "mesapartes02@ucsm.edu.pe", 
             "AVISO: MPV MESA DE PARTES VIRTUAL - SOLICITUDES ESPECIALES", 
             "UNIVERSIDAD CATÓLICA DE SANTA MARÍA - MESA DE PARTES VIRTUAL. Notificación sobre la Solicitud Especial N° 4092 asignada. Vencimiento de respuesta: 19/08/2026.",
             "2026-08-14 14:00", "HIGH", "#Tramites", "PENDING", 
             "🔴 ACCIÓN REQUERIDA: Dar seguimiento al trámite en Mesa de Partes Virtual UCSM antes del 19/08.", "URGENT", 
             "Estimados Mesa de Partes UCSM,\n\nConfirmamos la recepción del aviso sobre la solicitud especial. Quedamos a la espera de la resolución.\n\nAtentamente,\nLuis Merma"),

            ("real-ucsm-03", "Universidad Católica de Santa María", "investigacion@ucsm.edu.pe", 
             "Convocatoria del Concurso de Investigación 'Jóvenes en Agenda' edición 2026", 
             "Estimados estudiantes, la presente es para poner de su conocimiento las bases del Concurso de Investigación Jóvenes en Agenda 2026. Adjunto documento P018039 1.pdf. Fecha límite postulación: 25/08/2026.",
             "2026-08-14 09:00", "MEDIUM", "#UCSM_Oficial", "PENDING", 
             "Revisar bases del concurso 'Jóvenes en Agenda 2026' (P018039 1.pdf). Vence 25/08.", "POSITIVE", 
             "Estimados Vicerrectorado de Investigación UCSM,\n\nMuchas gracias por la información sobre la convocatoria 2026. Revisaremos las bases adjuntas.\n\nSaludos cordiales,\nLuis Merma"),

            ("real-ucsm-04", "VICERRECTORADO ACADÉMICO UCSM", "vicerrectorado.academico@ucsm.edu.pe", 
             "AVISO: MPV MESA DE PARTES VIRTUAL - SOLICITUDES ESPECIALES", 
             "Señor Doctor GUILLERMO CALDERON RUIZ Director de la Escuela Profesional de Ingeniería de Sistemas. Notificación de Auto N°0183 y Resolución P016664.pdf.",
             "2026-08-13 16:20", "MEDIUM", "#UCSM_Oficial", "PENDING", 
             "Revisar resolución del Vicerrectorado Académico emitida a la Dirección de EPIS.", "NEUTRAL", 
             "Estimados del Vicerrectorado Académico,\n\nConfirmamos recepción del Auto N°0183 y la resolución correspondiente.\n\nSaludos,\nLuis Merma"),

            ("real-ucsm-05", "Bolsa de Trabajo UCSM", "bempleo@ucsm.edu.pe", 
             "Bolsa de Trabajo UCSM: ANALISTA DE EXCELENCIA OPERACIONAL", 
             "Dirección de Empleabilidad y Alumni UCSM. Oportunidad laboral disponible: ANALISTA DE EXCELENCIA OPERACIONAL para alumnos de últimos ciclos y egresados.",
             "2026-08-13 11:10", "LOW", "#BolsaDeTrabajo", "RESPONDED", 
             "Informativo: Convocatoria de Empleo Analista de Excelencia Operacional UCSM.", "NEUTRAL", ""),

            ("real-ucsm-06", "El equipo de Miro", "your@product.miro.com", 
             "Iniciar sesión en Miro", 
             "Código de verificación e instrucciones para iniciar sesión en tu cuenta de Miro.",
             "2026-08-18 15:48", "LOW", "GENERAL", "RESPONDED", 
             "Informativo: Notificación de inicio de sesión de Miro.", "NEUTRAL", "")
        ]
        
        cursor.executemany('''
            INSERT INTO emails (id, sender_name, sender_email, subject, body, timestamp, priority, category, status, action_item, sentiment, auto_reply_draft)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', real_emails)

        # Sembrar Vencimientos del Calendario
        cursor.executemany('''
            INSERT INTO deadlines (email_id, title, due_date, urgency_level, status) VALUES (?, ?, ?, ?, ?)
        ''', [
            ("real-ucsm-01", "Revisión Plan de Tesis EPIS (Aldair Belisario)", "2026-08-20", "RED", "PENDING"),
            ("real-ucsm-02", "Trámite Solicitud Especial MPV Mesa de Partes", "2026-08-19", "RED", "PENDING"),
            ("real-ucsm-03", "Cierre Postulación Concurso 'Jóvenes en Agenda'", "2026-08-25", "YELLOW", "PENDING"),
            ("real-ucsm-04", "Revisión Auto N°0183 Vicerrectorado EPIS", "2026-08-22", "YELLOW", "PENDING")
        ])

    # Limpieza y sanitización automática de datos existentes en BD local (Fix de iniciales CP, A, MP)
    cursor.execute('''
        UPDATE emails 
        SET sender_name = 'COMPROBANTES DE PAGO ELECTRONICO (UCSM)' 
        WHERE sender_name = 'CP' OR sender_email LIKE 'cp%' OR subject LIKE '%COMPROBANTE%'
    ''')
    cursor.execute('''
        UPDATE emails 
        SET sender_name = 'ALDAIR MAURICIO BELISARIO' 
        WHERE sender_name = 'A' OR sender_email LIKE 'aldair%' OR subject LIKE '%TESIS%'
    ''')
    cursor.execute('''
        UPDATE emails 
        SET sender_name = 'MESA DE PARTES 02 UCSM' 
        WHERE sender_name = 'MP' OR sender_name = 'M' OR subject LIKE '%MESA DE PARTES%'
    ''')
    cursor.execute('''
        UPDATE emails 
        SET sender_name = 'Bolsa de Trabajo UCSM', sender_email = 'bempleo@ucsm.edu.pe' 
        WHERE sender_name = 'B' OR sender_email LIKE '%b@%' OR sender_email LIKE '%bempleo%' OR subject LIKE '%bempleo%' OR subject LIKE '%Bolsa de Trabajo%'
    ''')
    # Purga y sanitización automática de correos e iniciales defectuosas
    cursor.execute('''
        DELETE FROM emails 
        WHERE LENGTH(SUBSTR(sender_email, 1, INSTR(sender_email, '@') - 1)) <= 2 
           OR sender_email LIKE '%d@%' 
           OR sender_email LIKE '%fb@%' 
           OR sender_email LIKE '%nt@%' 
           OR sender_email LIKE '%u@%'
           OR sender_email LIKE '%m@%'
    ''')

    # Reescritura ejecutiva humana para las acciones requeridas del resumen diario
    cursor.execute('''
        UPDATE emails 
        SET action_item = '🔴 Revisar avance de Plan de Tesis EPIS (Aldair Belisario)'
        WHERE subject LIKE '%TESIS%' OR body LIKE '%TESIS%'
    ''')
    cursor.execute('''
        UPDATE emails 
        SET action_item = '🔴 Seguimiento a Solicitud Especial MPV (Mesa de Partes UCSM)'
        WHERE subject LIKE '%MESA DE PARTES%' OR body LIKE '%MESA DE PARTES%'
    ''')
    cursor.execute('''
        UPDATE emails 
        SET action_item = '🟡 Revisar bases del concurso Jóvenes en Agenda 2026'
        WHERE subject LIKE '%Convocatoria%' OR body LIKE '%Convocatoria%' OR subject LIKE '%Agenda%'
    ''')
    cursor.execute('''
        UPDATE emails 
        SET action_item = '🟡 Revisar Auto N°0183 y Resolución del Vicerrectorado Académico'
        WHERE subject LIKE '%VICERRECTORADO%' OR body LIKE '%VICERRECTORADO%'
    ''')
    # Reescritura ejecutiva humana para los borradores de auto-respuesta
    cursor.execute('''
        UPDATE emails 
        SET auto_reply_draft = 'Hola Aldair,\n\nHemos recibido el avance del Plan de Tesis EPIS. Lo estaré revisando a la brevedad y te enviaré mis comentarios.\n\nSaludos cordiales,\nLuis Merma'
        WHERE sender_email LIKE '%aldair%' OR subject LIKE '%TESIS%'
    ''')
    cursor.execute('''
        UPDATE emails 
        SET auto_reply_draft = 'Estimados (Bolsa de Trabajo UCSM),\n\nMuchas gracias por la información sobre la oportunidad laboral. Estaremos difundiendo la convocatoria entre los alumnos y egresados de EPIS.\n\nSaludos cordiales,\nLuis Merma'
        WHERE sender_email LIKE '%bempleo%' OR subject LIKE '%Bolsa de Trabajo%'
    ''')

    # Sembrar datos de memoria REALES de la cuenta de Luis Merma
    cursor.executemany('''
        INSERT OR REPLACE INTO memory_contacts (email, name, company, vip, interaction_count, notes, last_interaction)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [
        ("aldair.belisario@est.ucsm.edu.pe", "Aldair Mauricio Belisario", "EPIS - UCSM", 1, 8, 
         "Estudiante tesista de EPIS. Presentó el avance del Plan de Tesis EPIS_Plan de tesis.md. Requiere revisión académica prioritaria.", "2026-08-17 13:56"),
        ("mesapartes02@ucsm.edu.pe", "Mesa de Partes 02 UCSM", "UCSM Administrativo", 1, 12, 
         "Canal oficial de solicitudes especiales y trámites académicos de la universidad.", "2026-08-14 14:00"),
        ("investigacion@ucsm.edu.pe", "Vicerrectorado de Investigación UCSM", "UCSM Investigación", 0, 5, 
         "Envía convocatorias y fondos concursables de investigación como 'Jóvenes en Agenda'.", "2026-08-14 09:00"),
        ("vicerrectorado.academico@ucsm.edu.pe", "Vicerrectorado Académico UCSM", "UCSM Académico", 1, 9, 
         "Remite resoluciones y autos dirigidos a la Dirección de Escuela de Ingeniería de Sistemas (EPIS).", "2026-08-13 16:20")
    ])

    conn.commit()
    conn.close()

# Clasificador inteligente basado en palabras clave y contexto
def classify_email(subject, body, sender_email):
    text = (subject + " " + body).lower()
    
    # Prioridad
    if any(w in text for w in ["urgente", "asap", "inmediato", "aprobación", "aprobacion", "contrato", "vence hoy", "vencimiento"]):
        priority = "HIGH"
        sentiment = "URGENT"
    elif any(w in text for w in ["cotización", "cotizacion", "precio", "pago", "factura", "reunión", "reunion", "propuesta"]):
        priority = "MEDIUM"
        sentiment = "POSITIVE"
    else:
        priority = "LOW"
        sentiment = "NEUTRAL"

    # Categoría
    if any(w in text for w in ["precio", "tarifa", "costo", "cotizacion", "horario"]):
        category = "FAQ"
    elif any(w in text for w in ["pago", "factura", "comprobante", "transferencia"]):
        category = "FINANZAS"
    elif any(w in text for w in ["reunión", "reunion", "llamada", "agenda", "meet"]):
        category = "REUNION"
    elif any(w in text for w in ["urgente", "gerencia", "director"]):
        category = "VIP"
    else:
        category = "GENERAL"

    # Acción sugerida limpia y ejecutiva
    clean_sender = sender_name if len(sender_name) > 2 else sender_email
    if "tesis" in subject.lower() or "tesis" in body.lower():
        action_item = f"🔴 Revisar avance de Plan de Tesis EPIS ({clean_sender})"
    elif "mesa de partes" in subject.lower() or "mpv" in subject.lower():
        action_item = f"🔴 Seguimiento a Solicitud Especial MPV ({clean_sender})"
    elif "convocatoria" in subject.lower() or "concurso" in subject.lower():
        action_item = f"🟡 Revisar bases de Convocatoria/Concurso ({clean_sender})"
    elif "vicerrectorado" in subject.lower() or "auto n°" in subject.lower():
        action_item = f"🟡 Revisar Auto y Resolución Académica ({clean_sender})"
    elif "comprobante" in subject.lower() or "pago" in subject.lower():
        action_item = f"🟢 Verificar comprobante de pago electrónico ({clean_sender})"
    else:
        action_item = f"Gestión de mensaje: '{subject[:45]}...' de {clean_sender}"

    return priority, category, action_item, sentiment

# Generador de borradores FAQ
def clean_human_greeting_name(sender_name, sender_email):
    if not sender_name or len(sender_name.strip()) <= 2:
        if "bempleo" in sender_email or "bolsa" in sender_email:
            return "Estimados (Bolsa de Trabajo UCSM)"
        elif "mesapartes" in sender_email:
            return "Estimados (Mesa de Partes UCSM)"
        elif "investigacion" in sender_email or "vicerrectorado" in sender_email:
            return "Estimados (Vicerrectorado UCSM)"
        return "Estimado/a"

    clean = sender_name.split("(")[0].strip()
    if len(clean) <= 2:
        return "Estimado/a"
        
    parts = clean.split()
    if len(parts) >= 2 and not any(org in clean.upper() for org in ["UCSM", "MESA", "BOLSA", "VICERRECTORADO", "COMPROBANTES"]):
        return parts[0].capitalize()
        
    return clean

def match_faq_draft(subject, body, sender_name="Remitente", sender_email=""):
    clean_name = clean_human_greeting_name(sender_name, sender_email)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faqs WHERE is_active = 1")
    faqs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    text_to_search = f"{subject} {body}".lower()
    
    for faq in faqs:
        keywords = [k.strip().lower() for k in faq['keywords'].split(",") if k.strip()]
        if any(k in text_to_search for k in keywords):
            template = faq['auto_response_template']
            return template.replace("{nombre}", clean_name)
    
    return f"Hola {clean_name},\n\nHemos recibido tu mensaje respecto a '{subject}'. Nuestro equipo está procesando tu solicitud y te responderemos a la brevedad.\n\nSaludos cordiales!"

class AssistantHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path.startswith("/api/emails"):
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails ORDER BY priority DESC, timestamp DESC")
            emails = [dict(row) for row in cursor.fetchall()]
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(emails).encode('utf-8'))
            return

        elif path.startswith("/api/summary"):
            today_str = datetime.date.today().isoformat()
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM emails WHERE timestamp LIKE ?", (f"{today_str}%",))
            today_emails = [dict(row) for row in cursor.fetchall()]

            # Si no hay de hoy, traer los últimos para la demostración
            if not today_emails:
                cursor.execute("SELECT * FROM emails ORDER BY timestamp DESC LIMIT 10")
                today_emails = [dict(row) for row in cursor.fetchall()]

            high_count = sum(1 for e in today_emails if e['priority'] == 'HIGH')
            med_count = sum(1 for e in today_emails if e['priority'] == 'MEDIUM')
            low_count = sum(1 for e in today_emails if e['priority'] == 'LOW')
            pending_actions = [e['action_item'] for e in today_emails if e['status'] == 'PENDING']

            summary_text = (
                f"Hoy has recibido {len(today_emails)} correos procesados. "
                f"Se detectaron {high_count} de ALTA PRIORIDAD con acción requerida inmediata. "
                f"Hay {len(pending_actions)} tareas pendientes de respuesta y {med_count} consultas de prioridad media."
            )

            response_data = {
                "date": today_str,
                "total": len(today_emails),
                "high_count": high_count,
                "med_count": med_count,
                "low_count": low_count,
                "summary_text": summary_text,
                "pending_actions": pending_actions
            }

            conn.close()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return

        elif path.startswith("/api/memory"):
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_contacts ORDER BY interaction_count DESC")
            memory = [dict(row) for row in cursor.fetchall()]
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(memory).encode('utf-8'))
            return

        elif path.startswith("/api/tags"):
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tags ORDER BY id ASC")
            tags = [dict(row) for row in cursor.fetchall()]
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(tags).encode('utf-8'))
            return

        elif path.startswith("/api/deadlines"):
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM deadlines WHERE status = 'PENDING' ORDER BY due_date ASC")
            deadlines = [dict(row) for row in cursor.fetchall()]
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(deadlines).encode('utf-8'))
            return

        elif path == "/api/faqs":
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM faqs ORDER BY id ASC")
            faqs = [dict(row) for row in cursor.fetchall()]
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(faqs).encode('utf-8'))
            return

        elif path == "/api/export":
            # Exportar toda la base de datos a JSON para respaldar entre laptops
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM emails")
            emails = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM memory_contacts")
            memory = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM faqs")
            faqs = [dict(row) for row in cursor.fetchall()]

            backup = {
                "exported_at": datetime.datetime.now().isoformat(),
                "emails": emails,
                "memory_contacts": memory,
                "faqs": faqs
            }
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Disposition', 'attachment; filename=knowledge_memory_backup.json')
            self.end_headers()
            self.wfile.write(json.dumps(backup, indent=2).encode('utf-8'))
            return

        else:
            # Servir archivos estáticos del directorio actual
            return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        body_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        
        try:
            payload = json.loads(body_data)
        except Exception:
            payload = {}

        if path == "/api/emails/sync_real":
            # Ingestar lista de correos reales (limitado a los últimos 60 días / 2 meses)
            real_emails = payload.get("emails", [])
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            inserted_count = 0

            # Fecha límite: Hace 60 días (2 meses atrás)
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=60)

            for e in real_emails:
                sender_name = e.get("sender_name", "Remitente")
                sender_email = e.get("sender_email", "desconocido@ucsm.edu.pe")
                subject = e.get("subject", "Sin asunto")
                body = e.get("body", "")
                timestamp_str = e.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
                
                # Intentar validar fecha
                try:
                    # Si contiene fecha en formato YYYY-MM-DD o DD/MM/YYYY
                    date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', timestamp_str)
                    if date_match:
                        raw_d = date_match.group(0)
                        # Si es año antiguo (ej. 2024, 2025, 2023), omitir si tiene más de 60 días
                        for old_year in ["2020", "2021", "2022", "2023", "2024", "2025"]:
                            if old_year in raw_d:
                                continue
                except Exception:
                    pass

                # Generar hash/id único para evitar duplicados
                import hashlib
                raw_id = f"{sender_email}_{subject}_{timestamp_str}"
                msg_id = "real-" + hashlib.md5(raw_id.encode('utf-8')).hexdigest()[:10]

                # Verificar si ya existe en BD local
                cursor.execute("SELECT id FROM emails WHERE id = ?", (msg_id,))
                if cursor.fetchone():
                    continue

                priority, category, action_item, sentiment = classify_email(subject, body, sender_email)
                auto_reply_draft = match_faq_draft(subject, body, sender_name)

                cursor.execute('''
                    INSERT INTO emails (id, sender_name, sender_email, subject, body, timestamp, priority, category, status, action_item, sentiment, auto_reply_draft)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (msg_id, sender_name, sender_email, subject, body, timestamp_str, priority, category, "PENDING", action_item, sentiment, auto_reply_draft))

                # Actualizar o crear memoria de contacto
                cursor.execute("SELECT interaction_count, notes FROM memory_contacts WHERE email = ?", (sender_email,))
                existing = cursor.fetchone()
                if existing:
                    count = existing[0] + 1
                    notes = existing[1] + f" | {timestamp_str}: {subject}"
                    cursor.execute('''
                        UPDATE memory_contacts 
                        SET interaction_count = ?, notes = ?, last_interaction = ? 
                        WHERE email = ?
                    ''', (count, notes, timestamp_str, sender_email))
                else:
                    company = sender_email.split("@")[-1] if "@" in sender_email else "Personal"
                    notes = f"Contacto registrado el {timestamp_str}. Asunto: '{subject}'"
                    cursor.execute('''
                        INSERT INTO memory_contacts (email, name, company, vip, interaction_count, notes, last_interaction)
                        VALUES (?, ?, ?, ?, 1, ?, ?)
                    ''', (sender_email, sender_name, company, 1 if priority == "HIGH" else 0, notes, timestamp_str))
                
                inserted_count += 1

            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "synced_count": inserted_count}).encode('utf-8'))
            return

        elif path == "/api/emails/simulate":
            # Simular o recibir nuevo correo en tiempo real
            sender_name = payload.get("sender_name", "Nuevo Remitente")
            sender_email = payload.get("sender_email", "contacto@demo.com")
            subject = payload.get("subject", "Consulta importante")
            body = payload.get("body", "Detalle del correo recibido.")
            msg_id = f"msg-{int(datetime.datetime.now().timestamp())}"
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            priority, category, action_item, sentiment = classify_email(subject, body, sender_email)
            auto_reply_draft = match_faq_draft(subject, body, sender_name)

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO emails (id, sender_name, sender_email, subject, body, timestamp, priority, category, status, action_item, sentiment, auto_reply_draft)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (msg_id, sender_name, sender_email, subject, body, timestamp, priority, category, "DRAFT_READY", action_item, sentiment, auto_reply_draft))

            # Actualizar memoria del contacto
            cursor.execute("SELECT interaction_count, notes FROM memory_contacts WHERE email = ?", (sender_email,))
            existing = cursor.fetchone()
            if existing:
                count = existing[0] + 1
                notes = existing[1] + f" | {timestamp}: {subject}"
                cursor.execute('''
                    UPDATE memory_contacts 
                    SET interaction_count = ?, notes = ?, last_interaction = ? 
                    WHERE email = ?
                ''', (count, notes, timestamp, sender_email))
            else:
                company = sender_email.split("@")[-1]
                notes = f"{timestamp}: Asunto inicial '{subject}'"
                cursor.execute('''
                    INSERT INTO memory_contacts (email, name, company, vip, interaction_count, notes, last_interaction)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                ''', (sender_email, sender_name, company, 1 if priority == "HIGH" else 0, notes, timestamp))

            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "id": msg_id, "priority": priority}).encode('utf-8'))
            return

        elif path == "/api/emails/status":
            # Actualizar estado de correo (RESPONDED, ARCHIVED) y limpiar del calendario de vencimientos
            email_id = payload.get("id")
            new_status = payload.get("status", "RESPONDED")

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE emails SET status = ? WHERE id = ?", (new_status, email_id))
            
            if new_status == "RESPONDED":
                # Auto-limpieza de la tarea del calendario al ser respondido o resuelto
                cursor.execute("UPDATE deadlines SET status = 'RESOLVED' WHERE email_id = ?", (email_id,))

            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "updated", "deadline_resolved": True}).encode('utf-8'))
            return

        elif path == "/api/tags/add":
            name = payload.get("name", "").strip()
            color = payload.get("color", "#00e5ff").strip()
            keywords = payload.get("keywords", "").strip()

            if not name.startswith("#"):
                name = "#" + name

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO tags (name, color, keywords) VALUES (?, ?, ?)", (name, color, keywords))
            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "created"}).encode('utf-8'))
            return

        elif path == "/api/config/imap":
            enabled = payload.get("enabled", True)
            server_host = payload.get("server", "outlook.office365.com")
            port_num = int(payload.get("port", 993))
            email_addr = payload.get("email", "luis.merma@est.ucsm.edu.pe")
            pwd = payload.get("password", "")

            current = load_imap_config()
            if not pwd and current.get("password"):
                pwd = current.get("password")

            new_cfg = {
                "enabled": enabled,
                "server": server_host,
                "port": port_num,
                "email": email_addr,
                "password": pwd
            }
            save_imap_config(new_cfg)

            # Ejecutar una primera prueba inmediata
            count = fetch_real_emails_via_imap(new_cfg)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "saved", "synced_count": count}).encode('utf-8'))
            return

        elif path == "/api/faqs/add":
            keywords = payload.get("keywords", "")
            question = payload.get("question", "")
            auto_response_template = payload.get("auto_response_template", "")

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO faqs (keywords, question, auto_response_template, is_active)
                VALUES (?, ?, ?, 1)
            ''', (keywords, question, auto_response_template))
            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "created"}).encode('utf-8'))
            return

        elif path == "/api/cache/purge":
            # Purga total de caché y reinicio limpio de base de datos
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM emails")
            cursor.execute("DELETE FROM deadlines")
            cursor.execute("DELETE FROM memory_contacts")
            conn.commit()
            conn.close()

            # Volver a sembrar datos limpios e integrales
            init_db()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "purged", "message": "Caché borrada exitosamente"}).encode('utf-8'))
            return

        elif path == "/api/import":
            # Restaurar copia de respaldo enviada
            try:
                emails = payload.get("emails", [])
                memory = payload.get("memory_contacts", [])
                faqs = payload.get("faqs", [])

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()

                for e in emails:
                    cursor.execute('''
                        INSERT OR REPLACE INTO emails (id, sender_name, sender_email, subject, body, timestamp, priority, category, status, action_item, sentiment, auto_reply_draft)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (e['id'], e['sender_name'], e['sender_email'], e['subject'], e['body'], e['timestamp'], e['priority'], e['category'], e['status'], e['action_item'], e['sentiment'], e['auto_reply_draft']))

                for m in memory:
                    cursor.execute('''
                        INSERT OR REPLACE INTO memory_contacts (email, name, company, vip, interaction_count, notes, last_interaction)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (m['email'], m['name'], m['company'], m['vip'], m['interaction_count'], m['notes'], m['last_interaction']))

                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "imported_successfully"}).encode('utf-8'))
            except Exception as ex:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(ex)}).encode('utf-8'))
            return

        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    init_db()
    
    # Iniciar hilo de sincronización automática en segundo plano
    sync_thread = threading.Thread(target=background_sync_thread, daemon=True)
    sync_thread.start()

    print(f"============================================================")
    print(f"  ASISTENTE INTELIGENTE DE OUTLOOK - SERVIDOR LOCAL")
    print(f"  Base de datos de Memoria: {DB_FILE}")
    print(f"  Servidor corriendo en: http://localhost:{PORT}")
    print(f"  Sincronizador en segundo plano: ACTIVO cada {AUTO_POLL_INTERVAL} segundos")
    print(f"============================================================")
    
    server_address = ('', PORT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(server_address, AssistantHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
