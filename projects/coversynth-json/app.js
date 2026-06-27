const $ = (id) => document.getElementById(id);

let currentManifest = null;
let currentOutputs = [];
let statusData = null;

function setStatus(text, tone = "") {
  const status = $("status");
  status.textContent = text;
  status.dataset.tone = tone;
}

function manifestIsClean(manifest = currentManifest) {
  const jobs = manifest?.jobs || [];
  return Boolean(manifest?.prompts_cleaned || (jobs.length && jobs.every((job) => job.prompt_cleaned)));
}

function updateCleanState(manifest = currentManifest) {
  const state = $("cleanState");
  if (!state) return;
  if (!manifest) {
    state.textContent = "Cleanup: not run";
    state.dataset.tone = "";
    return;
  }
  if (manifestIsClean(manifest)) {
    const date = manifest.cleaned_at ? new Date(manifest.cleaned_at).toLocaleString() : "";
    state.textContent = `Cleanup: cleaned${date ? ` ${date}` : ""}`;
    state.dataset.tone = "ok";
  } else {
    state.textContent = "Cleanup: not run";
    state.dataset.tone = "warn";
  }
}

function postJson(url, body) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (res) => {
    const data = await res.json();
    if (!res.ok) {
      const firstError = data.validation?.errors?.[0];
      throw new Error(firstError || data.error || "Request failed");
    }
    return data;
  });
}

function parseManifestInput(required = true) {
  const raw = $("manifest").value.trim();
  if (!raw) {
    if (required) throw new Error("Manifest JSON is empty.");
    return null;
  }
  return JSON.parse(raw);
}

function writeManifest(manifest) {
  currentManifest = manifest;
  $("manifest").value = JSON.stringify(manifest, null, 2);
  renderJobs(manifest.jobs || []);
  updateCleanState(manifest);
}

function manifestOptions() {
  return {
    project: $("project").value.trim() || "FrameForge Project",
    count: Number($("jobCount").value),
    prompt_provider: $("imageProvider").value,
    prompt_model: $("promptModel").value,
    image_provider: $("imageProvider").value,
    image_model: $("imageModel").value,
    size: $("size").value,
    quality: $("quality").value,
    allow_text_in_image: $("allowText").checked,
  };
}

function toneForStatus(status) {
  return {
    complete: "ok",
    failed: "error",
    moderated: "warn",
    running: "active",
    skipped: "muted",
  }[status] || "";
}

function renderValidation(validation = {}) {
  const items = [
    ...(validation.errors || []).map((text) => ({ text, tone: "error" })),
    ...(validation.warnings || []).map((text) => ({ text, tone: "warn" })),
  ];
  $("validation").innerHTML = items.length
    ? items.map((item) => `<li data-tone="${item.tone}">${item.text}</li>`).join("")
    : `<li data-tone="ok">Manifest valid.</li>`;
}

function renderPlan(plan = []) {
  $("plan").innerHTML = plan.map((item) => `
    <tr>
      <td>${item.id}</td>
      <td>${item.filename}</td>
      <td>${item.size}</td>
      <td>${item.quality}</td>
      <td>${item.provider || "openai"}</td>
      <td>${item.model}</td>
    </tr>
  `).join("");
}

function renderJobs(jobs = []) {
  $("jobs").innerHTML = jobs.map((job) => `
    <article class="job-card" data-job-id="${job.id}">
      <label class="check-line">
        <input type="checkbox" data-job-select="${job.id}" checked>
        <span>${job.id}</span>
      </label>
      <input data-job-title="${job.id}" value="${escapeAttr(job.title || "")}" aria-label="Title">
      <textarea data-job-prompt="${job.id}" aria-label="Prompt">${escapeHtml(job.prompt_body || "")}</textarea>
      <div class="job-row">
        <select data-job-size="${job.id}" aria-label="Size">
          ${["1024x1024", "1536x1024", "1024x1536", "2048x1024"].map((size) => `<option ${job.size === size ? "selected" : ""}>${size}</option>`).join("")}
        </select>
        <select data-job-quality="${job.id}" aria-label="Quality">
          ${["high", "medium", "low"].map((quality) => `<option ${job.quality === quality ? "selected" : ""}>${quality}</option>`).join("")}
        </select>
      </div>
    </article>
  `).join("");
}

function syncJobCardsToManifest() {
  if (!currentManifest) return;
  for (const job of currentManifest.jobs || []) {
    const title = document.querySelector(`[data-job-title="${CSS.escape(job.id)}"]`);
    const prompt = document.querySelector(`[data-job-prompt="${CSS.escape(job.id)}"]`);
    const size = document.querySelector(`[data-job-size="${CSS.escape(job.id)}"]`);
    const quality = document.querySelector(`[data-job-quality="${CSS.escape(job.id)}"]`);
    if (title) job.title = title.value;
    if (prompt && prompt.value !== job.prompt_body) {
      job.prompt_body = prompt.value;
      job.prompt_cleaned = false;
      currentManifest.prompts_cleaned = false;
      delete currentManifest.cleaned_at;
      delete currentManifest.cleanup_model;
    }
    if (size) job.size = size.value;
    if (quality) job.quality = quality.value;
  }
  $("manifest").value = JSON.stringify(currentManifest, null, 2);
  updateCleanState(currentManifest);
}

function selectedJobIds() {
  return Array.from(document.querySelectorAll("[data-job-select]:checked")).map((input) => input.dataset.jobSelect);
}

function renderGallery(outputs = []) {
  currentOutputs = outputs;
  $("gallery").innerHTML = outputs.map((item, index) => `
    <article class="gallery-item" data-status="${item.status}">
      ${item.image ? `<img src="data:image/png;base64,${item.image}" alt="${escapeAttr(item.title || item.id)}">` : `<div class="gallery-placeholder">${item.status || "queued"}</div>`}
      <div class="gallery-meta">
        <strong>${escapeHtml(item.title || item.id || `Image ${index + 1}`)}</strong>
        <span data-tone="${toneForStatus(item.status)}">${item.status || "queued"}</span>
      </div>
      ${item.error ? `<p class="gallery-error">${escapeHtml(item.error)}</p>` : ""}
      <div class="gallery-actions">
        <button data-download-index="${index}" ${item.image ? "" : "disabled"}>Download</button>
      </div>
    </article>
  `).join("");
  $("gallery").querySelectorAll("[data-download-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = currentOutputs[Number(button.dataset.downloadIndex)];
      if (!item?.image) return;
      const a = document.createElement("a");
      a.href = `data:image/png;base64,${item.image}`;
      a.download = item.filename || `${item.id || "frameforge"}.png`;
      a.click();
    });
  });
}

function upsertOutput(item) {
  const index = currentOutputs.findIndex((output) => output.id === item.id);
  if (index >= 0) {
    currentOutputs[index] = { ...currentOutputs[index], ...item };
  } else {
    currentOutputs.push(item);
  }
  renderGallery(currentOutputs);
}

function stageOutputs(ids, manifest) {
  const jobs = manifest.jobs || [];
  currentOutputs = ids.map((id) => {
    const job = jobs.find((item) => item.id === id) || {};
    return {
      id,
      title: job.title || id,
      filename: job.filename || `${id}.png`,
      provider: job.provider || manifest.image_provider || "openai",
      model: job.model || manifest.default_image_model || "",
      size: job.size || manifest.default_size || "",
      quality: job.quality || manifest.default_quality || "",
      status: "queued",
    };
  });
  renderGallery(currentOutputs);
}

function setButtonsDisabled(disabled) {
  ["generateManifest", "validateManifest", "sanitizeManifest", "dryRun", "runSelected", "runAll", "retryFailed", "formatJson", "loadExample"].forEach((id) => {
    const button = $(id);
    if (button) button.disabled = disabled;
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

function applyProviderChoiceToManifest() {
  if (!currentManifest) return;
  const provider = $("imageProvider").value;
  const model = $("imageModel").value;
  currentManifest.prompt_provider = provider;
  currentManifest.image_provider = provider;
  currentManifest.default_prompt_model = $("promptModel").value;
  currentManifest.default_image_model = model;
  for (const job of currentManifest.jobs || []) {
    job.provider = provider;
    job.model = model;
  }
  $("manifest").value = JSON.stringify(currentManifest, null, 2);
  renderPlan(currentManifest.jobs || []);
}

function updateProviderUi() {
  const provider = $("imageProvider").value;
  const models = statusData?.image_models?.[provider] || (provider === "google" ? ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview", "gemini-2.5-flash-image"] : ["gpt-image-2"]);
  const promptModels = statusData?.prompt_models?.[provider] || (provider === "google" ? ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro"] : ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2", "gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini"]);
  const current = $("imageModel").value;
  const currentPrompt = $("promptModel").value;
  $("imageModel").innerHTML = models.map((model) => `<option value="${escapeAttr(model)}" ${model === current ? "selected" : ""}>${escapeHtml(model)}</option>`).join("");
  $("promptModel").innerHTML = promptModels.map((model) => `<option value="${escapeAttr(model)}" ${model === currentPrompt ? "selected" : ""}>${escapeHtml(model)}</option>`).join("");
  if (!models.includes(current)) $("imageModel").value = models[0];
  if (!promptModels.includes(currentPrompt)) $("promptModel").value = promptModels[0];
  $("providerStatus").textContent = provider === "google" ? "Gemini / Google" : "OpenAI";
  $("modelStatus").textContent = $("imageModel").value;
}

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    statusData = await res.json();
    updateProviderUi();
  } catch (_err) {
    updateProviderUi();
  }
}

async function sanitizeCurrentManifest(reason = "Cleaning prompts...", force = false) {
  syncJobCardsToManifest();
  if (!force && manifestIsClean()) {
    setStatus("Prompts are already marked clean; skipping cleanup.");
    return currentManifest;
  }
  setStatus(reason);
  const data = await postJson("/api/sanitize-manifest", {
    manifest: parseManifestInput(true),
    ...manifestOptions(),
  });
  writeManifest(data.manifest);
  renderValidation(data.validation);
  renderPlan(data.validation.plan);
  setStatus(`Prompts cleaned: ${data.manifest.jobs.length} job(s).`);
  return data.manifest;
}

async function ensureCanonicalManifest() {
  syncJobCardsToManifest();
  if (currentManifest?.jobs?.length) return currentManifest;
  setStatus("Validating manifest...");
  const data = await postJson("/api/validate-manifest", {
    manifest: parseManifestInput(true),
    ...manifestOptions(),
  });
  writeManifest(data.manifest);
  renderValidation(data.validation);
  renderPlan(data.validation.plan);
  if (!data.validation.valid) throw new Error(data.validation.errors?.[0] || "Manifest needs changes.");
  return data.manifest;
}

async function runJobs(ids, label = "jobs") {
  let manifest = await ensureCanonicalManifest();
  if (!ids?.length) ids = (manifest.jobs || []).map((job) => job.id);
  if (!ids.length) throw new Error("Select at least one job.");
  if ($("autoClean").checked) {
    manifest = await sanitizeCurrentManifest("Cleaning prompts before run...");
  } else {
    setStatus("Running exact JSON prompts.");
  }
  stageOutputs(ids, manifest);
  setButtonsDisabled(true);
  let projectDir = "";
  let complete = 0;
  let failed = 0;
  try {
    for (const [index, id] of ids.entries()) {
      const job = (manifest.jobs || []).find((item) => item.id === id);
      upsertOutput({ ...(job || { id }), id, status: "running" });
      setStatus(`Running ${index + 1}/${ids.length}: ${job?.title || id}...`);
      try {
        const data = await postJson("/api/run-manifest", {
          manifest: parseManifestInput(true),
          selected_ids: [id],
        });
        projectDir = data.project_dir || projectDir;
        const output = (data.outputs || []).find((item) => item.id === id) || (data.outputs || []).find((item) => item.status !== "skipped");
        if (output) {
          upsertOutput(output);
          if (output.status === "complete") complete += 1;
          else failed += 1;
        } else {
          failed += 1;
          upsertOutput({ id, title: job?.title || id, status: "failed", error: "No output returned for this job." });
        }
      } catch (err) {
        failed += 1;
        upsertOutput({ id, title: job?.title || id, status: "failed", error: err.message });
      }
    }
  } finally {
    setButtonsDisabled(false);
  }
  const summary = `${label} finished: ${complete} complete, ${failed} failed${projectDir ? `; saved to ${projectDir}` : ""}.`;
  setStatus(summary, failed ? "error" : "");
}

async function uploadFile(file) {
  if (!file) return;
  setStatus(`Reading ${file.name}...`);
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Could not read file.");
  $("manifest").value = data.text;
  currentManifest = null;
  updateCleanState(null);
  $("fileMeta").textContent = `${data.filename} · ${data.characters.toLocaleString()} characters`;
  setStatus(`Loaded ${data.filename}.`);
}

$("file").addEventListener("change", (event) => {
  uploadFile(event.target.files[0]).catch((err) => setStatus(err.message, "error"));
});

const dropZone = $("dropZone");
["dragenter", "dragover"].forEach((name) => {
  dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragging");
  });
});
["dragleave", "drop"].forEach((name) => {
  dropZone.addEventListener(name, () => dropZone.classList.remove("is-dragging"));
});
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  uploadFile(event.dataTransfer.files[0]).catch((err) => setStatus(err.message, "error"));
});

$("imageProvider").addEventListener("change", () => {
  updateProviderUi();
  applyProviderChoiceToManifest();
});
$("imageModel").addEventListener("change", () => {
  updateProviderUi();
  applyProviderChoiceToManifest();
});

$("generateManifest").addEventListener("click", async () => {
  try {
    setStatus("Refining manifest...");
    const data = await postJson("/api/refine", { idea: $("idea").value, ...manifestOptions() });
    writeManifest(data.manifest);
    renderValidation(data.validation);
    renderPlan(data.validation.plan);
    setStatus(`Manifest ready: ${data.manifest.jobs.length} jobs.`);
  } catch (err) {
    setStatus(err.message, "error");
  }
});

$("sanitizeManifest").addEventListener("click", async () => {
  try {
    await sanitizeCurrentManifest("Cleaning prompts...", true);
  } catch (err) {
    setStatus(err.message, "error");
  }
});

$("validateManifest").addEventListener("click", async () => {
  try {
    syncJobCardsToManifest();
    setStatus("Validating manifest...");
    const data = await postJson("/api/validate-manifest", { manifest: parseManifestInput(true), ...manifestOptions() });
    writeManifest(data.manifest);
    renderValidation(data.validation);
    renderPlan(data.validation.plan);
    setStatus(data.validation.valid ? "Manifest valid." : "Manifest needs changes.", data.validation.valid ? "" : "error");
  } catch (err) {
    setStatus(err.message, "error");
  }
});

$("runSelected").addEventListener("click", async () => {
  try {
    const ids = selectedJobIds();
    if (!ids.length) throw new Error("Select at least one job.");
    await runJobs(ids, "Selected run");
  } catch (err) {
    setStatus(err.message, "error");
  }
});

$("runAll").addEventListener("click", async () => {
  try {
    await runJobs(null, "Run");
  } catch (err) {
    setStatus(err.message, "error");
  }
});

$("dryRun").addEventListener("click", async () => {
  try {
    syncJobCardsToManifest();
    setStatus("Previewing execution plan...");
    const data = await postJson("/api/run-manifest", { manifest: parseManifestInput(true), dry_run: true });
    renderGallery(data.outputs || []);
    setStatus(`Dry run complete: ${(data.outputs || []).length} job(s).`);
  } catch (err) {
    setStatus(err.message, "error");
  }
});

$("retryFailed").addEventListener("click", async () => {
  try {
    const failedIds = currentOutputs.filter((item) => item.status === "failed" || item.status === "moderated").map((item) => item.id);
    if (!failedIds.length) throw new Error("No failed jobs to retry.");
    await runJobs(failedIds, "Retry");
  } catch (err) {
    setStatus(err.message, "error");
  }
});

$("formatJson").addEventListener("click", () => {
  try {
    writeManifest(parseManifestInput(true));
    setStatus("JSON formatted.");
  } catch (err) {
    setStatus(err.message, "error");
  }
});

$("loadExample").addEventListener("click", () => {
  const example = {
    project: "Seed 13 Launch Set",
    brand: "Seed 13 Productions",
    app: "FrameForge",
    prompt_provider: $("imageProvider").value,
    image_provider: $("imageProvider").value,
    default_prompt_model: $("promptModel").value,
    default_image_model: $("imageModel").value,
    default_quality: "high",
    default_size: "1024x1024",
    allow_text_in_image: true,
    continue_on_error: true,
    max_jobs: 10,
    output_path: "ai_generated/seed_13_launch_set",
    reference_images: [],
    jobs: [
      {
        id: "01_title_card",
        title: "Title Card",
        filename: "01_title_card.png",
        size: "1536x1024",
        quality: "high",
        required_text: ["DRAGONSYNTH", "SEED 13 PRODUCTIONS"],
        prompt_body: "Retro-futurist production studio title card, polished chrome dragon silhouette, luminous control-room glass, cinematic product launch energy.",
        negative_instructions: "No collage. No split panels. No extra text.",
        reference_image_ids: [],
      },
      {
        id: "02_gallery_thumb",
        title: "Gallery Thumb",
        filename: "02_gallery_thumb.png",
        size: "1024x1024",
        quality: "high",
        required_text: [],
        prompt_body: "Single square gallery thumbnail showing a refined image-generation console with one finished artwork preview, tactile controls, warm highlights, premium software aesthetic.",
        negative_instructions: "No random lettering. No UI clutter.",
        reference_image_ids: [],
      },
    ],
  };
  $("project").value = example.project;
  writeManifest(example);
  renderValidation({});
  renderPlan(example.jobs);
  setStatus("Example loaded.");
});

loadStatus();
