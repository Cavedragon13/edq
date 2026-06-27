const $ = (id) => document.getElementById(id);
let lastRun = null;
let statusData = null;

function setStatus(text, tone = "") {
  const status = $("status");
  status.textContent = text;
  status.dataset.tone = tone;
}

function looksLikePath(value) {
  const text = value.trim().replace(/^['"]|['"]$/g, "");
  return !text.includes("\n") && text.length < 600 && (/^(\/|~\/)/.test(text) || /^[A-Za-z]:[\\/]/.test(text)) && /\.(pdf|txt|csv|md|rtf)$/i.test(text);
}

function slugifyTitle(value) {
  const slug = String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return slug || `coversynth-cover-${new Date().toISOString().slice(0, 10)}`;
}


function updateModelOptions() {
  const models = statusData?.prompt_models?.openai || ["gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2", "gpt-5", "gpt-4.1-mini"];
  const current = $("model").value;
  $("model").innerHTML = models.map((model) => `<option value="${model}" ${model === current ? "selected" : ""}>${model}</option>`).join("");
  const defaultModel = statusData?.defaults?.prompt_model || models[0];
  $("model").value = models.includes(current) ? current : defaultModel;
}

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    statusData = await res.json();
  } catch (_err) {
    statusData = null;
  }
  updateModelOptions();
}

function renderAnalysis(analysis) {
  const rows = [
    ["Title", analysis.title],
    ["Summary", analysis.summary],
    ["Moods", (analysis.dominant_moods || []).join(", ")],
    ["Sentiment", analysis.sentiment],
    ["Genres", (analysis.genres || []).join(", ")],
    ["Palette", (analysis.color_palette || []).join(", ")],
    ["Motifs", (analysis.visual_motifs || []).join(", ")],
  ];
  $("analysis").innerHTML = rows
    .filter(([, value]) => value)
    .map(([label, value]) => `<div><strong>${label}</strong><span>${String(value)}</span></div>`)
    .join("");
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

async function uploadFile(file) {
  if (!file) return;
  setStatus(`Reading ${file.name}...`);
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Could not read file.");
  $("playlist").value = data.text;
  $("fileMeta").textContent = `${data.filename} · ${data.characters.toLocaleString()} characters loaded`;
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

$("analyze").addEventListener("click", async () => {
  try {
    const playlist = $("playlist").value;
    if (looksLikePath(playlist)) {
      setStatus("That is a file path. Drop the file above or click the upload area so I can read it.", "error");
      return;
    }
    setStatus("Analyzing playlist...");
    const data = await postJson("/api/analyze", { playlist, model: $("model").value });
    lastRun = { ...lastRun, analysis: data.analysis, analysisModel: data.model };
    $("prompt").value = data.analysis.cover_prompt || data.raw || "";
    renderAnalysis(data.analysis);
    $("generate").disabled = !$("prompt").value.trim();
    setStatus(`Analysis complete with ${data.model}.`);
  } catch (err) {
    setStatus(err.message, "error");
  }
});

async function generate(refinement = "") {
  setStatus(refinement ? "Refining cover with GPT Image 2..." : "Generating cover with GPT Image 2...");
  const data = await postJson("/api/generate", {
    prompt: $("prompt").value,
    refinement,
    quality: $("quality").value,
    model: statusData?.defaults?.image_model,
  });
  $("cover").src = `data:image/png;base64,${data.image}`;
  $("prompt").value = data.prompt;
  $("refine").disabled = false;
  $("downloadCover").disabled = false;
  lastRun = { ...lastRun, imageModel: data.model, imagePrompt: data.prompt, image: data.image };
  localStorage.setItem("coversynth:lastRun", JSON.stringify({ ...lastRun, image: "[base64 omitted]" }));
  setStatus(`Cover ready from ${data.model}.`);
}

$("generate").addEventListener("click", () => generate().catch((err) => setStatus(err.message, "error")));
$("refine").addEventListener("click", () => {
  const refinement = $("refinement").value.trim();
  if (!refinement) return;
  $("refinement").value = "";
  generate(refinement).catch((err) => setStatus(err.message, "error"));
});

$("downloadCover").addEventListener("click", () => {
  if (!lastRun?.image) {
    setStatus("Generate a cover before downloading.", "error");
    return;
  }
  const title = lastRun?.analysis?.title || "";
  const a = document.createElement("a");
  a.href = `data:image/png;base64,${lastRun.image}`;
  a.download = `${slugifyTitle(title)}.png`;
  a.click();
});

$("saveLog").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(lastRun || {}, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `coversynth-${new Date().toISOString().slice(0, 19).replaceAll(":", "")}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
});

loadStatus();
