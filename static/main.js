document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("analysis-form");
    const submitBtn = document.getElementById("submit-btn");
    const btnText = submitBtn.querySelector(".btn-text");
    const stageList = document.getElementById("stage-list");
    const stages = [...stageList.querySelectorAll(".stage")];
    const errorBanner = document.getElementById("error-banner");
    const emptyState = document.getElementById("empty-state");
    const resultBody = document.getElementById("result-body");

    // ── TAP manual toggle ───────────────────────────────────────
    const tapMode = document.getElementById("tap_mode");
    const tapManual = document.getElementById("tap_manual_fields");
    tapMode.addEventListener("change", () => {
        tapManual.classList.toggle("hidden", tapMode.value !== "manual");
    });

    // ── Dropzones (clique + drag-and-drop) ──────────────────────
    const setupDropzone = (inputId, dropId) => {
        const input = document.getElementById(inputId);
        const drop = document.getElementById(dropId);
        const nameEl = drop.querySelector(".dz-name");
        const def = nameEl.dataset.default;

        const sync = () => {
            if (input.files.length) {
                nameEl.textContent = input.files[0].name;
                drop.classList.add("is-set");
            } else {
                nameEl.textContent = def;
                drop.classList.remove("is-set");
            }
        };
        input.addEventListener("change", sync);

        ["dragenter", "dragover"].forEach(ev =>
            drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("is-dragover"); }));
        ["dragleave", "drop"].forEach(ev =>
            drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("is-dragover"); }));
        drop.addEventListener("drop", e => {
            if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; sync(); }
        });
    };
    setupDropzone("cfg_file", "cfg-drop");
    setupDropzone("dat_file", "dat-drop");

    // ── Loading em estágios (feedback do pipeline) ──────────────
    let stageTimer = null;
    const startStages = () => {
        stages.forEach(s => s.classList.remove("active", "done"));
        stageList.classList.remove("hidden");
        let i = 0;
        const advance = () => {
            stages.forEach((s, k) => {
                s.classList.toggle("done", k < i);
                s.classList.toggle("active", k === i);
            });
            i = Math.min(i + 1, stages.length - 1);
        };
        advance();
        stageTimer = setInterval(advance, 650);
    };
    const stopStages = (ok) => {
        clearInterval(stageTimer);
        if (ok) stages.forEach(s => { s.classList.remove("active"); s.classList.add("done"); });
        setTimeout(() => stageList.classList.add("hidden"), ok ? 400 : 0);
    };

    const showError = (msg) => {
        errorBanner.textContent = `⚠  ${msg}`;
        errorBanner.classList.remove("hidden");
    };

    // ── Submit ──────────────────────────────────────────────────
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        errorBanner.classList.add("hidden");

        submitBtn.disabled = true;
        btnText.textContent = "Processando…";
        startStages();

        try {
            const res = await fetch("/api/analisar", { method: "POST", body: new FormData(form) });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Falha na análise (HTTP ${res.status})`);
            }
            const data = await res.json();
            stopStages(true);
            renderResults(data);
        } catch (err) {
            stopStages(false);
            showError(err.message);
            console.error(err);
        } finally {
            submitBtn.disabled = false;
            btnText.textContent = "Executar análise";
        }
    });

    // ── Render ──────────────────────────────────────────────────
    function renderResults(data) {
        const { resumo, images } = data;
        emptyState.classList.add("hidden");
        resultBody.classList.remove("hidden");

        renderVerdict(resumo.veredito);
        renderMeta(resumo);
        renderMetrics(resumo.fases);
        renderGallery(images || []);
        resultBody.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function renderVerdict(v) {
        const box = document.getElementById("verdict");
        const map = { TRIP: "is-trip", BLOQUEIO: "is-bloqueio", ESTAVEL: "is-estavel" };
        box.className = `verdict ${map[v.status] || ""}`;
        document.getElementById("verdict-status").textContent = v.status;
        document.getElementById("verdict-label").textContent = v.label;
        document.getElementById("verdict-detail").textContent = v.detail;
    }

    function renderMeta(r) {
        const chips = document.getElementById("meta-chips");
        const cb = r.config.cross_blocking ? "on" : "off";
        const t = r.taps;
        // Marca "?" no TAP de um enrolamento que não conduziu (estimativa indeterminada)
        const mark = (det) => (t.origem === "estimado" && !det) ? " ?" : "";
        const tapP = `${t.tap_p} A${mark(t.p_determinado)}`;
        const tapS = `${t.tap_s} A${mark(t.s_determinado)}`;
        chips.innerHTML = [
            ["Grupo", `YNd${r.config.vector_group}`],
            ["Y", r.config.lado_estrela],
            ["TAP", t.origem],
            ["TAP P", tapP],
            ["TAP S", tapS],
            ["Lim. H2", `${r.config.limite_h2_pct}%`],
            ["Cross-block", cb],
        ].map(([k, val]) => `<span class="meta-chip">${k} <b>${val}</b></span>`).join("");

        // Nota explicativa quando algum lado ficou indeterminado
        const indet = t.origem === "estimado" && (!t.p_determinado || !t.s_determinado);
        let nota = document.getElementById("tap-note");
        if (indet) {
            const lado = !t.p_determinado ? "primário (W1)" : "secundário (W2)";
            if (!nota) {
                nota = document.createElement("p");
                nota.id = "tap-note";
                nota.className = "tap-note";
                chips.insertAdjacentElement("afterend", nota);
            }
            nota.textContent = `TAP do ${lado} indeterminado — esse enrolamento não conduziu corrente significativa no registro; valor herdado do outro lado (não afeta Idiff/Ibias).`;
        } else if (nota) {
            nota.remove();
        }
    }

    function renderMetrics(fases) {
        const body = document.getElementById("metrics-body");
        body.innerHTML = fases.map(f => `
            <tr>
                <td class="fase-cell">${f.fase}</td>
                <td>${f.idiff_pu.toFixed(3)}</td>
                <td>${f.idiff_a.toFixed(2)}</td>
                <td>${f.ibias_pu.toFixed(3)}</td>
                <td>${f.h2h1_pct.toFixed(1)}</td>
                <td><span class="state-chip ${f.status}">${f.status}</span></td>
            </tr>`).join("");
    }

    function renderGallery(images) {
        const gallery = document.getElementById("image-gallery");
        gallery.innerHTML = "";
        images.forEach(img => {
            const card = document.createElement("div");
            card.className = "result-card";
            card.innerHTML = `
                <div class="result-card-head">
                    <h3>${img.name}</h3>
                    <span class="expand-hint">clique p/ ampliar</span>
                </div>
                <figure><img src="${img.data}" alt="${img.name}" loading="lazy"></figure>`;
            card.querySelector("figure").addEventListener("click", () => openLightbox(img));
            gallery.appendChild(card);
        });
    }

    // ── Lightbox ────────────────────────────────────────────────
    const lightbox = document.getElementById("lightbox");
    const lbImg = document.getElementById("lb-img");
    const lbCaption = document.getElementById("lb-caption");
    const closeLightbox = () => lightbox.classList.add("hidden");

    function openLightbox(img) {
        lbImg.src = img.data;
        lbImg.alt = img.name;
        lbCaption.textContent = img.name;
        lightbox.classList.remove("hidden");
    }
    lightbox.addEventListener("click", e => { if (e.target !== lbImg) closeLightbox(); });
    document.getElementById("lb-close").addEventListener("click", closeLightbox);
    document.addEventListener("keydown", e => {
        if (e.key === "Escape" && !lightbox.classList.contains("hidden")) closeLightbox();
    });
});
