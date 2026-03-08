(() => {
    const toggle = document.getElementById("chatToggle");
    const box = document.getElementById("chatBox");
    const close = document.getElementById("chatClose");
    const msgs = document.getElementById("chatMsgs");
    const input = document.getElementById("chatInput");
    const send = document.getElementById("chatSend");

    if (!toggle || !box || !close || !msgs || !input || !send) return;

    const escapeHtml = (s) => (s || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

    const renderLiteMarkdown = (text) => {
        let t = escapeHtml(text || "");
        t = t.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
        t = t.replaceAll("\n", "<br>");
        return t;
    };

    const addBubble = (who, text, me = false) => {
        const wrap = document.createElement("div");
        wrap.className = "chat-bubble" + (me ? " me" : "");
        wrap.innerHTML = `<div class="chat-meta"><b>${who}</b></div>${renderLiteMarkdown(text)}`;
        msgs.appendChild(wrap);
        msgs.scrollTop = msgs.scrollHeight;
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

    const fallbackMessage = (message) => {
        const m = (message || "").toLowerCase();

        if (m.includes("reporte") || m.includes("resumen")) {
            return "La consulta está tardando más de lo esperado. Intenta nuevamente en unos segundos.";
        }

        if (/\b\d{10}\b/.test(m) || m.includes("paciente") || m.includes("historial")) {
            return "La consulta del paciente está tardando más de lo esperado. Intenta nuevamente en unos segundos.";
        }

        if (m.includes("cuánt") || m.includes("cuantos") || m.includes("contar")) {
            return "La consulta está tardando más de lo esperado. Intenta nuevamente en unos segundos.";
        }

        return "No pude responder en este momento. Intenta nuevamente en unos segundos.";
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

            if (data && data.reply) {
                addBubble("Bot", data.reply, false);
                return;
            }

            addBubble("Bot", fallbackMessage(message), false);
        } catch (e) {
            addBubble("Bot", fallbackMessage(message), false);
        }
    };

    send.addEventListener("click", ask);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") ask();
    });
})();