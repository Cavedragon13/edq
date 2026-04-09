const STAT_DEFS = [
  { key: "strength", abbr: "S", label: "Strength" },
  { key: "intelligence", abbr: "I", label: "Intelligence" },
  { key: "wisdom", abbr: "W", label: "Wisdom" },
  { key: "dexterity", abbr: "D", label: "Dexterity" },
  { key: "constitution", abbr: "C", label: "Constitution" },
  { key: "charisma", abbr: "Ch", label: "Charisma" }
];

const FIELD_IDS = {
  name: "nameInput",
  heritage: "heritageInput",
  className: "classInput",
  background: "backgroundInput",
  alignment: "alignmentInput",
  homeland: "homelandInput",
  hook: "hookInput",
  armor: "armorInput",
  weapons: "weaponsInput",
  magic: "magicInput",
  notes: "notesInput"
};

const DATA = {
  ancestries: [
    "Human",
    "Elf",
    "Dwarf",
    "Halfling",
    "Dragonborn",
    "Tiefling",
    "Half-Orc",
    "Gnome"
  ],
  backgrounds: [
    "Temple Runaway",
    "Court Courier",
    "Shipwreck Salvager",
    "Lantern Archivist",
    "Borderland Scout",
    "Graveyard Gardener",
    "Guild Enforcer",
    "Mushroom Keeper",
    "Cursed Heir",
    "Watchtower Cook"
  ],
  alignments: [
    "Lawful Good",
    "Neutral Good",
    "Chaotic Good",
    "Lawful Neutral",
    "True Neutral",
    "Chaotic Neutral",
    "Lawful Evil",
    "Neutral Evil",
    "Chaotic Evil"
  ],
  homelands: [
    "a storm-cut harbor",
    "the copper hills",
    "an overgrown watch city",
    "the witchlight marsh",
    "the last safe road north",
    "a cliff monastery",
    "the ember market",
    "the hollowed pine frontier",
    "a buried dwarven gate",
    "the glass desert"
  ],
  hooks: [
    "owes a favor to a dangerous abbess",
    "is hunting the map to a shut adamant vault",
    "keeps hearing a dead saint in dreams",
    "was marked by moonfire and left alive",
    "carries the last key from a broken watchtower",
    "is trying to outrun a prophecy with teeth",
    "knows exactly where the dragon did not die",
    "needs one impossible job to clear the family name"
  ],
  classesByStat: {
    strength: ["Fighter", "Paladin", "Barbarian"],
    intelligence: ["Wizard", "Artificer", "Wizard"],
    wisdom: ["Cleric", "Druid", "Ranger"],
    dexterity: ["Rogue", "Ranger", "Monk", "Bard"],
    constitution: ["Barbarian", "Fighter", "Paladin"],
    charisma: ["Bard", "Warlock", "Sorcerer", "Paladin"]
  },
  firstNames: [
    "Alder",
    "Brenna",
    "Corin",
    "Del",
    "Edda",
    "Fen",
    "Garrick",
    "Hale",
    "Iria",
    "Joren",
    "Kestrel",
    "Liora",
    "Merrik",
    "Nyra",
    "Orin",
    "Petra",
    "Quill",
    "Riven",
    "Syl",
    "Tamsin",
    "Ulric",
    "Vera",
    "Wren",
    "Ysra"
  ],
  surnames: [
    "Ashdown",
    "Briar",
    "Crowfall",
    "Duskwhistle",
    "Emberlane",
    "Fell",
    "Gallowmere",
    "Hearth",
    "Ironroot",
    "Lark",
    "Mournwell",
    "Nightglass",
    "Pineshade",
    "Quickstep",
    "Rune",
    "Stonewake",
    "Thorn",
    "Vale"
  ],
  armorByClass: {
    Fighter: "brigandine, round shield, travel cloak",
    Paladin: "polished half-plate, tabard, warded gorget",
    Barbarian: "fur harness, bone charms, hide bracers",
    Wizard: "rune-stitched robe, layered shawl, charm-thread gloves",
    Cleric: "mail shirt, prayer mantle, brass holy sigil",
    Druid: "barkweave wrap, moss-lined mantle, antler clasp",
    Ranger: "studded leather, rain cape, quiet boots",
    Rogue: "dark leathers, lock sleeve, soft gloves",
    Monk: "wrapped vest, weighted sash, sand-worn sandals",
    Bard: "embroidered coat, duelist scarf, silver rings",
    Sorcerer: "silk longcoat, storm-cord belt, arcane cuffs",
    Warlock: "shadow mantle, lacquered vambrace, pact seal"
  },
  weaponsByClass: {
    Fighter: "longsword, handaxe, and a backup spear",
    Paladin: "warhammer, shield spike, and sun-etched dagger",
    Barbarian: "greataxe, hunting knives, and a weighted club",
    Wizard: "oak staff, ritual knife, and pocket chalk",
    Cleric: "mace, sling, and censer chain",
    Druid: "staff, sickle, and thorn darts",
    Ranger: "longbow, shortsword, and snares",
    Rogue: "rapier, throwing knives, and picks",
    Monk: "quarterstaff, hand wraps, and darts",
    Bard: "dueling sword, hand crossbow, and a fine instrument",
    Sorcerer: "wand, crystal shard, and a ceremonial blade",
    Warlock: "obsidian rod, curved dagger, and a pact focus"
  },
  magicByClass: {
    Fighter: "iron luck token and a whetstone that hums near danger",
    Paladin: "lamp of last vows and a ribbon blessed against fear",
    Barbarian: "totem bead that warms before bloodshed",
    Wizard: "ink bottle that remembers one lost spell diagram",
    Cleric: "saint-bone prayer wheel and a candle that refuses to drown",
    Druid: "seed pouch of sleeping flowers and a moon glass charm",
    Ranger: "compass that points toward unfinished oaths",
    Rogue: "coin that always lands on its edge for one breath",
    Monk: "bead strand that steadies the pulse on command",
    Bard: "whispering tuning fork and a lucky stage pin",
    Sorcerer: "vein of bottled lightning and a cracked focus gem",
    Warlock: "sealed letter from the patron and a cold iron ring"
  },
  notes: [
    "chalk, rope, oilskin map, 11 silver, dried fruit",
    "lantern, bedroll, prayer book, 8 silver, sealing wax",
    "crowbar, tinderbox, bone dice, 14 silver, smoked eel",
    "healing herbs, flint, mirror shard, 9 silver, spare socks",
    "grappling hook, notebook, old warrant, 6 silver, hard cheese"
  ],
  skinTones: ["#f0c9a4", "#d7a07b", "#bb7f5f", "#8d5b44", "#6b4634"],
  hairTones: ["#201915", "#4b2f21", "#7b5d39", "#d3a15a", "#b23b33", "#d9d7cf"],
  eyeTones: ["#294b58", "#3d5e30", "#6b5122", "#7d2d25", "#5a3c77"],
  clothTones: ["#284734", "#6a3325", "#325264", "#5d4a28", "#4d315e"],
  accentTones: ["#c89643", "#d26b47", "#8fb2a8", "#9c79d2", "#d9ccc0"]
};

const dom = {};
const THEME_STORAGE_KEY = "dnd-generator-theme";

const state = {
  character: {},
  stats: [],
  portraitSpec: null,
  portraitSvg: "",
  theme: "light"
};

window.addEventListener("DOMContentLoaded", () => {
  cacheDom();
  initializeTheme();
  bindControls();
  newCharacter();
});

function cacheDom() {
  dom.portraitImage = document.getElementById("portraitImage");
  dom.portraitCaption = document.getElementById("portraitCaption");
  dom.characterSpark = document.getElementById("characterSpark");
  dom.promptOutput = document.getElementById("promptOutput");
  dom.statsGrid = document.getElementById("statsGrid");
  dom.rollSummary = document.getElementById("rollSummary");
  dom.themeToggleButton = document.getElementById("themeToggleButton");
  dom.themeToggleIcon = document.getElementById("themeToggleIcon");
  dom.themeToggleLabel = document.getElementById("themeToggleLabel");

  Object.entries(FIELD_IDS).forEach(([key, id]) => {
    dom[key] = document.getElementById(id);
  });
}

function bindControls() {
  dom.themeToggleButton.addEventListener("click", toggleTheme);
  document
    .getElementById("newCharacterButton")
    .addEventListener("click", newCharacter);
  document
    .getElementById("rerollStatsButton")
    .addEventListener("click", rerollStatsOnly);
  document
    .getElementById("rerollPortraitButton")
    .addEventListener("click", rerollPortraitOnly);
  document
    .getElementById("savePortraitButton")
    .addEventListener("click", savePortrait);
  document
    .getElementById("copyPromptButton")
    .addEventListener("click", copyPrompt);

  Object.keys(FIELD_IDS).forEach((key) => {
    dom[key].addEventListener("input", () => {
      state.character[key] = dom[key].value.trim();
      refreshNarrative();
    });
  });
}

function initializeTheme() {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const resolvedTheme = stored || (mediaQuery.matches ? "dark" : "light");

  applyTheme(resolvedTheme);

  mediaQuery.addEventListener("change", (event) => {
    if (!window.localStorage.getItem(THEME_STORAGE_KEY)) {
      applyTheme(event.matches ? "dark" : "light");
    }
  });
}

function toggleTheme() {
  const nextTheme = state.theme === "dark" ? "light" : "dark";
  window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  applyTheme(nextTheme);
}

function applyTheme(theme) {
  state.theme = theme;
  document.documentElement.dataset.theme = theme;
  dom.themeToggleButton.setAttribute("aria-pressed", String(theme === "dark"));
  dom.themeToggleIcon.textContent = theme === "dark" ? "☀️" : "🌙";
  dom.themeToggleLabel.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
}

function newCharacter() {
  state.stats = STAT_DEFS.map((definition) => {
    const rolled = rollStat();
    return { ...definition, ...rolled };
  });

  const identity = buildIdentity(state.stats);
  const loadout = buildLoadout(identity.className);

  state.character = { ...identity, ...loadout };
  state.portraitSpec = buildPortraitSpec();

  syncFieldsFromState();
  renderAll();
}

function rerollStatsOnly() {
  state.stats = STAT_DEFS.map((definition) => {
    const rolled = rollStat();
    return { ...definition, ...rolled };
  });
  renderAll();
}

function rerollPortraitOnly() {
  state.portraitSpec = buildPortraitSpec();
  renderPortrait();
  refreshNarrative();
}

function renderAll() {
  renderStats();
  renderPortrait();
  refreshNarrative();
}

function syncFieldsFromState() {
  Object.keys(FIELD_IDS).forEach((key) => {
    dom[key].value = state.character[key] || "";
  });
}

function rollStat() {
  const rolled = Array.from({ length: 5 }, () => randomInt(1, 6));
  const sorted = [...rolled].sort((left, right) => right - left);
  const kept = sorted.map((value, index) => ({
    value,
    kept: index < 3
  }));
  const score = kept
    .filter((die) => die.kept)
    .reduce((total, die) => total + die.value, 0);

  return { rolled, kept, score, modifier: formatModifier(score) };
}

function buildIdentity(stats) {
  const ordered = [...stats].sort((left, right) => right.score - left.score);
  const prime = ordered[0];
  const second = ordered[1];
  const heritage = pick(DATA.ancestries);
  const className = pick(DATA.classesByStat[prime.key]) || "Fighter";
  const background = pick(DATA.backgrounds);
  const homeland = pick(DATA.homelands);
  const alignment = pick(DATA.alignments);
  const hook = pick(DATA.hooks);

  return {
    name: `${pick(DATA.firstNames)} ${pick(DATA.surnames)}`,
    heritage,
    className,
    background,
    alignment,
    homeland,
    hook: `${capitalize(hook)}.`,
    concept: `${className.toLowerCase()} tuned around ${prime.label.toLowerCase()} and backed by ${second.label.toLowerCase()}.`
  };
}

function buildLoadout(className) {
  return {
    armor: DATA.armorByClass[className] || "patched leathers and a steady cloak",
    weapons: DATA.weaponsByClass[className] || "reliable steel and one hidden trick",
    magic: DATA.magicByClass[className] || "one suspicious talisman",
    notes: pick(DATA.notes)
  };
}

function buildPortraitSpec() {
  return {
    skin: pick(DATA.skinTones),
    hair: pick(DATA.hairTones),
    eyes: pick(DATA.eyeTones),
    cloth: pick(DATA.clothTones),
    accent: pick(DATA.accentTones),
    backgroundA: pick(DATA.clothTones),
    backgroundB: pick(DATA.accentTones),
    faceWidth: randomInt(112, 132),
    faceHeight: randomInt(146, 162),
    eyeSize: randomInt(5, 8),
    hairStyle: randomInt(0, 3),
    hairLength: randomInt(0, 2),
    beard: Math.random() > 0.68,
    scar: Math.random() > 0.76,
    cloakShape: randomInt(0, 2),
    accessory: randomInt(0, 3),
    halo: Math.random() > 0.58,
    ornament: randomInt(0, 10000)
  };
}

function renderStats() {
  const total = state.stats.reduce((sum, stat) => sum + stat.score, 0);
  const prime = [...state.stats].sort((left, right) => right.score - left.score)[0];

  dom.rollSummary.textContent = `Total ${total}. Prime stat ${prime.label} ${prime.score}.`;
  dom.statsGrid.innerHTML = state.stats
    .map((stat) => {
      const diceMarkup = stat.kept
        .map(
          (die) =>
            `<span class="die" data-kept="${String(die.kept)}">${die.value}</span>`
        )
        .join("");

      return `
        <article class="stat-card">
          <div class="stat-topline">
            <div>
              <span class="stat-abbr">${stat.abbr}</span>
              <p class="stat-name">${stat.label}</p>
            </div>
            <div>
              <div class="stat-score">${stat.score}</div>
              <div class="stat-mod">${stat.modifier}</div>
            </div>
          </div>
          <div class="dice-row">${diceMarkup}</div>
          <p class="stat-note">Rolled 5d6, kept the best 3.</p>
        </article>
      `;
    })
    .join("");
}

function renderPortrait() {
  state.portraitSvg = buildPortraitSvg(state.character, state.portraitSpec, state.stats);
  dom.portraitImage.src = svgToDataUri(state.portraitSvg);
  dom.portraitCaption.textContent = buildPortraitCaption();
}

function refreshNarrative() {
  dom.characterSpark.textContent = buildCharacterSpark();
  dom.promptOutput.value = buildImagePrompt();
  dom.portraitCaption.textContent = buildPortraitCaption();
}

function buildCharacterSpark() {
  const prime = [...state.stats].sort((left, right) => right.score - left.score)[0];
  const weak = [...state.stats].sort((left, right) => left.score - right.score)[0];
  const { name, heritage, className, background, homeland, hook } = state.character;

  return `${name} is a ${heritage.toLowerCase()} ${className.toLowerCase()} from ${homeland} with the instincts of a ${background.toLowerCase()}. ${hook} Their best edge is ${prime.label.toLowerCase()} at ${prime.score}, while ${weak.label.toLowerCase()} at ${weak.score} is where the trouble usually starts.`;
}

function buildPortraitCaption() {
  const total = state.stats.reduce((sum, stat) => sum + stat.score, 0);
  const prime = [...state.stats].sort((left, right) => right.score - left.score)[0];
  return `${state.character.name}, ${state.character.className}. Total stats ${total}. Built around ${prime.label.toLowerCase()} ${prime.score}.`;
}

function buildImagePrompt() {
  const prime = [...state.stats].sort((left, right) => right.score - left.score)[0];
  return `Fantasy character portrait of ${state.character.name}, a ${state.character.heritage.toLowerCase()} ${state.character.className.toLowerCase()} from ${state.character.homeland}. ${state.character.hook} Wears ${state.character.armor}. Carries ${state.character.weapons}. Signature magic item: ${state.character.magic}. Emphasize ${prime.label.toLowerCase()}, painterly tabletop art, dramatic light, detailed face, half-body composition, adventure-worn clothing, clean background, no text.`;
}

function buildPortraitSvg(character, spec, stats) {
  const heritage = (character.heritage || "").toLowerCase();
  const className = (character.className || "").toLowerCase();
  const prime = [...stats].sort((left, right) => right.score - left.score)[0];
  const chinY = 236 + spec.faceHeight / 2;
  const cloakPath = [
    "M58 470C86 362 142 324 200 322C258 324 314 362 342 470L318 520H82Z",
    "M44 478C78 344 136 304 200 304C264 304 322 344 356 478L320 520H80Z",
    "M70 476C108 374 146 338 200 332C254 338 292 374 330 476L316 520H84Z"
  ][spec.cloakShape];

  const hairPath = [
    "M102 168C110 114 150 92 198 92C248 92 292 116 304 170C294 150 272 136 246 130C224 124 210 122 186 124C154 126 126 140 102 168Z",
    "M94 170C112 112 156 84 208 88C262 92 300 122 304 174C282 156 260 144 228 140C194 136 154 142 94 170Z",
    "M106 162C122 112 164 92 204 92C248 92 286 116 294 162C268 150 236 146 210 148C174 150 142 156 106 162Z",
    "M88 182C100 114 150 86 206 86C258 86 304 116 314 182C294 162 268 148 230 144C190 140 142 148 88 182Z"
  ][spec.hairStyle];

  const backHair = spec.hairLength === 0
    ? ""
    : `<path d="M122 212C128 284 118 336 114 390H286C280 338 276 280 282 208C254 228 226 238 198 238C170 238 144 228 122 212Z" fill="${spec.hair}" opacity="0.72"/>`;

  const beard = spec.beard
    ? `<path d="M154 ${chinY - 8}C160 ${chinY + 34} 178 ${chinY + 58} 202 ${chinY + 60}C226 ${chinY + 58} 244 ${chinY + 34} 250 ${chinY - 8}C228 ${chinY + 10} 176 ${chinY + 10} 154 ${chinY - 8}Z" fill="${shade(spec.hair, -18)}" opacity="0.92"/>`
    : "";

  const scar = spec.scar
    ? '<path d="M238 188C232 202 228 214 220 230" stroke="rgba(120,40,36,0.65)" stroke-width="3" stroke-linecap="round"/>'
    : "";

  const heritageExtras = heritage.includes("elf")
    ? `
      <path d="M110 210C92 196 92 172 108 162C112 176 114 194 110 210Z" fill="${spec.skin}"/>
      <path d="M290 210C308 196 308 172 292 162C288 176 286 194 290 210Z" fill="${spec.skin}"/>
    `
    : heritage.includes("tiefling")
      ? `
        <path d="M138 92C120 64 120 34 144 20C138 48 146 76 160 96Z" fill="${shade(spec.hair, 12)}"/>
        <path d="M262 92C280 64 280 34 256 20C262 48 254 76 240 96Z" fill="${shade(spec.hair, 12)}"/>
      `
      : heritage.includes("dragonborn")
        ? `
          <path d="M144 120C166 102 188 92 204 92C220 92 242 102 264 120L250 138C228 126 218 122 204 122C190 122 180 126 158 138Z" fill="${shade(spec.skin, -10)}"/>
        `
        : heritage.includes("half-orc")
          ? `
            <path d="M170 ${chinY - 6}L164 ${chinY + 12}" stroke="#f4e0c8" stroke-width="4" stroke-linecap="round"/>
            <path d="M230 ${chinY - 6}L236 ${chinY + 12}" stroke="#f4e0c8" stroke-width="4" stroke-linecap="round"/>
          `
          : "";

  const classExtras = className.includes("wizard")
    ? `<path d="M120 136L200 56L280 136L248 142L224 116L200 138L176 116L152 142Z" fill="${shade(spec.cloth, -10)}" opacity="0.94"/>`
    : className.includes("paladin") || className.includes("cleric")
      ? `<path d="M192 382H208V430H192Z M176 398H224V414H176Z" fill="${spec.accent}" opacity="0.85"/>`
      : className.includes("rogue")
        ? `<path d="M110 146C126 126 150 112 168 110C146 132 136 152 130 174Z" fill="${shade(spec.cloth, -12)}" opacity="0.84"/>`
        : className.includes("bard")
          ? `<circle cx="292" cy="378" r="12" fill="${spec.accent}" opacity="0.82"/><circle cx="292" cy="378" r="4" fill="#fff3dc"/>`
          : "";

  const accessory = [
    "",
    `<circle cx="132" cy="372" r="10" fill="${spec.accent}" opacity="0.85"/>`,
    `<rect x="258" y="358" width="22" height="30" rx="6" fill="${shade(spec.accent, -8)}" opacity="0.82"/>`,
    `<path d="M200 366L214 390L200 412L186 390Z" fill="${spec.accent}" opacity="0.9"/>`
  ][spec.accessory];

  const halo = spec.halo
    ? `<circle cx="200" cy="238" r="156" fill="url(#glow)" opacity="0.5"/>`
    : "";

  const rune = prime.abbr || prime.label.charAt(0);

  return `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 520" role="img" aria-label="${escapeXml(character.name)} portrait">
      <defs>
        <linearGradient id="bg" x1="0%" x2="100%" y1="0%" y2="100%">
          <stop offset="0%" stop-color="${spec.backgroundA}"/>
          <stop offset="100%" stop-color="${spec.backgroundB}"/>
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="42%" r="56%">
          <stop offset="0%" stop-color="${withAlpha(spec.accent, 0.86)}"/>
          <stop offset="100%" stop-color="${withAlpha(spec.accent, 0)}"/>
        </radialGradient>
      </defs>

      <rect width="400" height="520" fill="url(#bg)"/>
      <rect width="400" height="520" fill="rgba(16, 16, 14, 0.12)"/>
      ${halo}
      <circle cx="84" cy="102" r="66" fill="${withAlpha("#ffffff", 0.08)}"/>
      <circle cx="322" cy="120" r="50" fill="${withAlpha(spec.accent, 0.14)}"/>
      <path d="M38 448C92 420 154 404 200 404C246 404 308 420 362 448" stroke="${withAlpha("#fdf7eb", 0.24)}" stroke-width="2" fill="none"/>
      <path d="M68 88L112 58L138 104" fill="none" stroke="${withAlpha("#fdf7eb", 0.26)}" stroke-width="2"/>
      <text x="314" y="458" fill="${withAlpha("#fdf7eb", 0.34)}" font-family="Georgia, serif" font-size="38">${escapeXml(rune)}</text>
      <text x="42" y="478" fill="${withAlpha("#fdf7eb", 0.2)}" font-family="Georgia, serif" font-size="22">${spec.ornament}</text>

      <path d="${cloakPath}" fill="${spec.cloth}"/>
      <path d="M112 510C136 426 166 388 200 388C234 388 264 426 288 510" fill="${shade(spec.cloth, -12)}" opacity="0.94"/>
      <path d="M140 360C154 334 174 320 200 320C226 320 246 334 260 360L244 420H156Z" fill="${shade(spec.skin, -12)}" opacity="0.8"/>
      ${backHair}
      ${classExtras}
      <ellipse cx="200" cy="214" rx="${spec.faceWidth}" ry="${spec.faceHeight}" fill="${spec.skin}"/>
      ${heritageExtras}
      <path d="${hairPath}" fill="${spec.hair}"/>
      <path d="M126 182C146 166 168 158 194 156C226 154 252 160 278 182" fill="none" stroke="${shade(spec.hair, -20)}" stroke-width="6" stroke-linecap="round"/>
      <path d="M150 206C166 198 178 196 188 198" fill="none" stroke="${shade(spec.hair, -18)}" stroke-width="5" stroke-linecap="round"/>
      <path d="M212 198C224 194 238 196 252 206" fill="none" stroke="${shade(spec.hair, -18)}" stroke-width="5" stroke-linecap="round"/>
      <ellipse cx="168" cy="220" rx="${spec.eyeSize + 10}" ry="${spec.eyeSize}" fill="#f8f1e6"/>
      <ellipse cx="232" cy="220" rx="${spec.eyeSize + 10}" ry="${spec.eyeSize}" fill="#f8f1e6"/>
      <circle cx="168" cy="220" r="${spec.eyeSize}" fill="${spec.eyes}"/>
      <circle cx="232" cy="220" r="${spec.eyeSize}" fill="${spec.eyes}"/>
      <circle cx="170" cy="218" r="2" fill="#ffffff"/>
      <circle cx="234" cy="218" r="2" fill="#ffffff"/>
      <path d="M200 226C194 240 192 252 194 270C197 274 203 274 206 270C208 254 206 240 200 226Z" fill="${shade(spec.skin, -18)}"/>
      <path d="M174 286C188 294 212 294 226 286" fill="none" stroke="${shade(spec.hair, -20)}" stroke-width="4" stroke-linecap="round"/>
      <path d="M150 314C166 326 184 332 200 332C216 332 234 326 250 314" fill="none" stroke="${withAlpha("#ffffff", 0.22)}" stroke-width="2"/>
      ${beard}
      ${scar}
      ${accessory}
      <rect x="16" y="16" width="368" height="488" rx="22" fill="none" stroke="${withAlpha("#fdf7eb", 0.34)}" stroke-width="2"/>
    </svg>
  `;
}

function savePortrait() {
  const svgUrl = svgToDataUri(state.portraitSvg);
  const image = new Image();

  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = 1200;
    canvas.height = 1560;

    const context = canvas.getContext("2d");
    context.fillStyle = "#f7f1e4";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);

    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = slugify(state.character.name || "adventurer") + "-portrait.png";
    link.click();
  };

  image.src = svgUrl;
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(dom.promptOutput.value);
    dom.promptOutput.select();
  } catch (error) {
    dom.promptOutput.focus();
    dom.promptOutput.select();
  }
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pick(list) {
  return list[randomInt(0, list.length - 1)];
}

function formatModifier(score) {
  const modifier = Math.floor((score - 10) / 2);
  return modifier >= 0 ? `+${modifier}` : String(modifier);
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function svgToDataUri(svg) {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function escapeXml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function withAlpha(hex, alpha) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function shade(hex, amount) {
  const { r, g, b } = hexToRgb(hex);
  const clamp = (value) => Math.max(0, Math.min(255, value));
  return `rgb(${clamp(r + amount)}, ${clamp(g + amount)}, ${clamp(b + amount)})`;
}

function hexToRgb(hex) {
  const normalized = hex.replace("#", "");
  const chunk =
    normalized.length === 3
      ? normalized
          .split("")
          .map((value) => value + value)
          .join("")
      : normalized;

  return {
    r: Number.parseInt(chunk.slice(0, 2), 16),
    g: Number.parseInt(chunk.slice(2, 4), 16),
    b: Number.parseInt(chunk.slice(4, 6), 16)
  };
}
