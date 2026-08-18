# 🤖 Organizador de Correos con Outlook IA

Un asistente inteligente ejecutivo **100% local, portable y privado** para Microsoft Outlook / Hotmail (`outlook.cloud.microsoft`, `outlook.live.com` y `outlook.office.com`).

El sistema clasifica tus correos entrantes por prioridad (**🔴 Alta**, **🟡 Media**, **🟢 Baja / Informativos**), mantiene una **memoria persistente de tus contactos y temas**, genera **resúmenes ejecutivos diarios** y automatiza las respuestas a **preguntas frecuentes (FAQs)** con un solo clic.

---

## 🌟 Características Principales

* 🔒 **100% Local y Privado**: Corre en tu propia máquina en `http://localhost:8050`. Todos tus datos se almacenan en una base de datos local SQLite (`knowledge_memory.db`).
* 📦 **Totalmente Portable**: Puedes mover la carpeta completa a cualquier laptop (o sincronizarla por OneDrive/Google Drive) y el asistente mantendrá **toda su memoria e historial aprendidos**.
* ⚡ **Sincronización Automática en Segundo Plano**: Incluye una extensión nativa para el navegador **Brave / Chrome** (`brave-extension`) que lee y clasifica los correos nuevos cada 15 segundos **sin abrir la consola F12 ni presionar botones**.
* ⏳ **Filtro Temporal de 2 Meses**: Filtra e ignora correos antiguos de años pasados para enfocar la inteligencia únicamente en tus correos actuales (últimos 60 días) y correos futuros.
* 📩 **Despacho Directo a Outlook Cloud**: Al aprobar un borrador redactado por la IA, el sistema abre la ventana de redacción oficial de Outlook pre-llenando el destinatario, el asunto y la respuesta.
* 📊 **Dashboard Ejecutivo Interactivo**: Interfaz web moderna (Glassmorphism Dark Mode) con tarjetas de métricas interactivas y filtros de 1 clic.

---

## 🔐 Permisos y Seguridad Requeridos

Para que el proyecto funcione en tu computadora y navegador, se requieren los siguientes permisos básicos:

1. **Permiso de Modo Desarrollador en Brave/Chrome**:
   - Requerido para cargar la extensión nativa local desde `brave://extensions`.
2. **Permisos Host en la Extensión (`manifest.json`)**:
   - Acceso a `https://outlook.cloud.microsoft/*` (para leer los encabezados de la bandeja de entrada abierta).
   - Acceso a `http://localhost:8050/*` (para enviar los correos detectados al servidor local Python).
3. **Acceso Local a Puerto 8050**:
   - Permiso de red local para que la interfaz se comunique con `server.py`.

---

## 🚀 Guía de Instalación y Uso Paso a Paso

### 1. Clonar o Descargar el Repositorio
```bash
git clone https://github.com/TU_USUARIO/organizador-de-correos-con-outlook-ia.git
cd organizador-de-correos-con-outlook-ia
```

### 2. Iniciar el Asistente Local (Windows)
Haz doble clic en el archivo **`iniciar_asistente.bat`** o ejecuta en consola:
```bash
python server.py
```
Se abrirá automáticamente el panel web en: **`http://localhost:8050`**.

### 3. Instalar la Extensión Automática en Brave (1 Clic)
1. Abre tu navegador Brave y ve a **`brave://extensions`**.
2. Activa el interruptor **Modo Desarrollador** (esquina superior derecha).
3. Haz clic en el botón **Cargar descomprimida** (Load unpacked).
4. Selecciona la carpeta **`brave-extension`** dentro del proyecto.

¡Listo! A partir de ese momento, cada vez que abras tu correo en Outlook Cloud, la extensión sincronizará automáticamente todos los nuevos mensajes con tu asistente local.

---

## 📁 Estructura del Código

* **`server.py`**: Servidor local ligero en Python con SQLite y motor de clasificación por IA.
* **`knowledge_memory.db`**: Base de datos SQLite local que almacena la memoria de contactos, historial y FAQs.
* **`index.html`**: Dashboard de control ejecutivo responsive.
* **`styles.css`**: Sistema de diseño moderno con variables CSS, animaciones y glassmorphism.
* **`app.js`**: Lógica cliente, persistencia de filtros en tiempo real y despacho de borradores.
* **`brave-extension/`**: Extensión nativa de manifiesto V3 para sincronización en segundo plano en Brave.
* **`iniciar_asistente.bat`**: Ejecutable de inicio rápido en 1 clic para Windows.

---

## 📄 Licencia

Licencia MIT. Libre para uso personal, educativo y comercial.
