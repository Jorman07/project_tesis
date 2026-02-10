(() => {
    const toggle = document.getElementById("chatToggle");
    const box = document.getElementById("chatBox");
    const close = document.getElementById("chatClose");
    const msgs = document.getElementById("chatMsgs");
    const input = document.getElementById("chatInput");
    const send = document.getElementById("chatSend");

    if (!toggle || !box || !close || !msgs || !input || !send) return;

    const addBubble = (who, text, me = false) => {
        const wrap = document.createElement("div");
        wrap.className = "chat-bubble" + (me ? " me" : "");
        wrap.innerHTML = `<div class="chat-meta"><b>${who}</b></div>${renderLiteMarkdown(text)}`;
        msgs.appendChild(wrap);
        msgs.scrollTop = msgs.scrollHeight;
    };

    const escapeHtml = (s) => (s || "")
        .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

    const renderLiteMarkdown = (text) => {
        // 1) escapa html
        let t = escapeHtml(text || "");

        // 2) **negritas**
        t = t.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");

        // 3) saltos de línea
        t = t.replaceAll("\n", "<br>");

        return t;
    };
    const openChat = () => {
        box.classList.add("is-open");
        box.setAttribute("aria-hidden", "false");
        setTimeout(() => input.focus(), 0);
    };

    const closeChat = () => {
        box.classList.remove("is-open");
        box.setAttribute("aria-hidden", "true");
    };


    toggle.addEventListener("click", openChat);
    close.addEventListener("click", closeChat);

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && box.classList.contains("is-open")) {
            closeChat();
        }
    });


    // --- Router simple (para probar ya mismo en tu plataforma)
    const routeLocal = async (message) => {
        const m = message.trim();

        // 1) Reporte mensual: "reporte 2025-12" o "resumen diciembre 2025"
        const monthMatch = m.match(/(\d{4}-\d{2})/);
        if (m.toLowerCase().includes("reporte") || m.toLowerCase().includes("resumen")) {
            const month = monthMatch ? monthMatch[1] : null;
            if (month) {
                const r = await fetch(`/api/bot/reporte-mensual?month=${encodeURIComponent(month)}`);
                const j = await r.json();
                if (!r.ok) return j.error || "No se pudo obtener el reporte.";
                const data = j.data || {};
                const total = data.total_mensual ?? 0;
                const top = Array.isArray(data.dosis_por_vacuna) ? data.dosis_por_vacuna.slice(0, 3) : [];

                let out = `**Resumen mensual — ${data.month || month}**\n\n`;
                out += `• Total de dosis registradas: ${total}\n\n`;
                if (top.length) {
                    out += `Vacunas con mayor aplicación:\n`;
                    top.forEach((it, idx) => out += `${idx + 1}. ${it.vacuna}: ${it.dosis_total}\n`);
                }
                return out;
            }
            return "Indícame el mes en formato YYYY-MM. Ejemplo: “reporte 2025-12”.";
        }

        // 2) Historial paciente: detecta 10 dígitos (cédula)
        const cedMatch = m.match(/\b\d{10}\b/);
        if (m.toLowerCase().includes("historial") || cedMatch) {
            const cedula = cedMatch ? cedMatch[0] : null;
            if (!cedula) return "Indícame la cédula (10 dígitos). Ejemplo: “historial 0950123456”.";
            const r = await fetch(`/api/bot/historial-paciente?cedula=${encodeURIComponent(cedula)}`);
            const j = await r.json();

            if (r.status === 404) return "No se encontraron registros para esa cédula.";
            if (!r.ok) return j.error || "No se pudo obtener historial.";

            const p = j.paciente || { cedula, nombres: "N/D", edad: "N/D", grupo_riesgo: "N/D" };
            const rows = j.rows || [];

            let out = `**Paciente encontrado**\n`;
            out += `• Cédula: **${p.cedula}**\n`;
            out += `• Nombres: **${p.nombres}**\n`;
            out += `• Sexo: **${p.sexo || "N/D"}**\n`;
            out += `• Edad: **${p.edad}**\n`;
            out += `• Grupo de riesgo: **${p.grupo_riesgo}**\n`;
            out += `• Parroquia: **${p.parroquia || "N/D"}**\n`;
            out += `• Establecimiento: **${p.establecimiento || "N/D"}**\n\n`;

            out += `**Historial (más reciente)**\n`;
            const last = rows.slice(-10).reverse();
            last.forEach((r, idx) => {
                const fecha = r.fecha_vacunacion || "N/D";
                const vac = r.vacuna_canon || "N/D";
                const raw = r.vacuna_raw ? ` (raw: ${r.vacuna_raw})` : "";
                out += `${idx + 1}. ${fecha} — ${vac}${raw} | Dosis: ${r.dosis || "N/D"} | Esquema: ${r.esquema || "N/D"} | Estado: ${r.estado_registro || "N/D"}\n`;
            });
            return out;

        }

        // 3) Contar vacuna por día: requiere fecha YYYY-MM-DD y vacuna palabra
        const dateMatch = m.match(/(\d{4}-\d{2}-\d{2})/);
        if (m.toLowerCase().includes("cuánt") || m.toLowerCase().includes("cuantos") || m.toLowerCase().includes("contar")) {
            const fecha = dateMatch ? dateMatch[1] : null;
            // vacuna: lo que vaya después de "con" o última palabra relevante (simple)
            const vMatch = m.match(/con\s+(.+?)\s+(?:el|en)\s+\d{4}-\d{2}-\d{2}/i);
            const vacuna = vMatch ? vMatch[1].trim() : null;

            if (!fecha || !vacuna) {
                return "Ejemplo: “cuántos se vacunaron con BCG el 2025-12-10”.";
            }

            const r = await fetch(`/api/bot/contar-vacuna-dia?vacuna=${encodeURIComponent(vacuna)}&fecha=${encodeURIComponent(fecha)}`);
            const j = await r.json();
            if (!r.ok) return j.error || "No se pudo contar.";

            return `**Conteo de vacunación — ${fecha}**\n• Vacuna: ${vacuna}\n• Total de registros: ${j.total ?? 0}`;
        }

        return "Puedo ayudarte con: “reporte 2025-12”, “historial 0950123456”, “cuántos con BCG el 2025-12-10”.";
    };

    const ask = async () => {
        const message = (input.value || "").trim();
        if (!message) return;
        input.value = "";
        addBubble("Tú", message, true);

        try {
            const r = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message })
            });
            const data = await r.json();

            // Si respondió Rasa
            if (data && data.engine === "rasa" && data.reply) {
                addBubble("Bot", data.reply, false);
                return;
            }

            // Fallback local
            const fb = await routeLocal(message);
            addBubble("Bot", fb, false);
        } catch (e) {
            // Rasa/Flask falló -> fallback local
            const fb = await routeLocal(message);
            addBubble("Bot", fb, false);
        }
    };


    send.addEventListener("click", ask);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });

})();
