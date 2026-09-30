const S = {
  profil: "iot",
  domaine: "",
  onglet: "mots",
  jours: 7,
  q: "",
  profils: [],
  mots: null,
  timerEssai: 0,
  timerFiltre: 0,
  poll: 0,
  suiviExport: false,
};

const $ = (sel) => document.querySelector(sel);

async function api(path, options) {
  const reponse = await fetch(path, options);
  const data = await reponse.json().catch(() => ({}));
  if (!reponse.ok && !data.erreur) data.erreur = "La requête a échoué.";
  return data;
}

function quand(iso) {
  if (!iso) return "sans date";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "sans date";
  const heures = (Date.now() - date.getTime()) / 36e5;
  if (heures < 1) return "à l'instant";
  if (heures < 24) return `il y a ${Math.round(heures)} h`;
  if (heures < 48) return "hier";
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

function el(tag, classe, texte) {
  const node = document.createElement(tag);
  if (classe) node.className = classe;
  if (texte != null) node.textContent = texte;
  return node;
}

async function chargerEtat() {
  const data = await api("/api/etat");
  const job = data.job || {};
  const barre = $("#progression");
  const actif = Boolean(job.actif);
  barre.hidden = !actif && !job.message;
  $("#prog-msg").textContent = job.message || "";
  const ratio = job.total ? Math.min(100, Math.round((100 * job.fait) / job.total)) : actif ? 8 : 100;
  $("#prog-i").style.width = `${actif ? Math.max(ratio, 4) : 100}%`;
  $("#rafraichir").disabled = actif;
  document.querySelectorAll("[data-format], #exporter-tout").forEach((bouton) => {
    bouton.disabled = actif;
  });
  const morceaux = [`${data.articles || 0} articles`, `${data.sources || 0} sources`];
  if (data.sources_erreur) morceaux.push(`${data.sources_erreur} en erreur`);
  $("#compteurs").textContent = morceaux.join(" · ");
  if (actif && !S.poll) S.poll = setInterval(chargerEtat, 1200);
  if (!actif && (S.poll || S.suiviExport)) {
    const finExport = S.suiviExport && job.type === "export";
    if (S.poll) {
      clearInterval(S.poll);
      S.poll = 0;
      chargerArticles();
      if (S.onglet !== "mots") rendrePanneau();
    }
    if (finExport || (job.type === "export" && S.suiviExport)) {
      S.suiviExport = false;
      const message = $("#export-msg");
      message.replaceChildren();
      if (job.erreur) {
        message.textContent = job.erreur;
      } else {
        message.append(document.createTextNode(`${job.message || "Publication terminée"} · `));
        const index = document.createElement("a");
        index.href = "https://f4eed.pages-perso.free.fr/Veille_2/";
        index.target = "_blank";
        index.rel = "noreferrer";
        index.textContent = "la page Veille 2";
        message.append(index);
      }
    }
  }
}

async function chargerProfils() {
  const data = await api("/api/profils");
  S.profils = data.profils || [];
  if (!S.profils.some((p) => p.id === S.profil) && S.profils[0]) S.profil = S.profils[0].id;
  const courant = S.profils.find((p) => p.id === S.profil);
  if (courant) S.jours = courant.periode_jours || 7;
  const nav = $("#veilles");
  nav.replaceChildren();
  for (const profil of S.profils) {
    const bouton = el("button", "veille" + (profil.id === S.profil ? " actif" : ""));
    bouton.type = "button";
    bouton.append(el("span", "", profil.titre), el("small", "", String(profil.periode_jours) + " j"));
    bouton.addEventListener("click", () => choisirProfil(profil.id));
    nav.append(bouton);
  }
  const fenetre = $("#fenetre");
  fenetre.replaceChildren();
  for (const jours of [1, 3, 7, 14, 30, 90]) {
    const bouton = el("button", jours === S.jours ? "actif" : "", `${jours} j`);
    bouton.type = "button";
    bouton.addEventListener("click", async () => {
      S.jours = jours;
      await api("/api/periode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profil: S.profil, jours }),
      });
      await chargerProfils();
      chargerArticles();
      if (V3.ouvert) chargerVue3d();
    });
    fenetre.append(bouton);
  }
}

function choisirProfil(id) {
  S.profil = id;
  S.domaine = "";
  const courant = S.profils.find((p) => p.id === id);
  S.jours = courant ? courant.periode_jours || 7 : 7;
  chargerProfils();
  chargerArticles();
  chargerMots();
  if (V3.ouvert) chargerVue3d();
}

async function chargerArticles() {
  const params = new URLSearchParams({
    profil: S.profil,
    jours: String(S.jours),
    domaine: S.domaine,
    q: S.q,
  });
  const data = await api("/api/articles?" + params.toString());
  const courant = S.profils.find((p) => p.id === S.profil);
  $("#titre").textContent = courant ? courant.titre : S.profil;
  $("#perimetre").textContent = courant ? courant.perimetre : "";
  const rubriques = $("#rubriques");
  rubriques.replaceChildren();
  const tout = el("button", S.domaine === "" ? "actif" : "", `Tout ${data.total || 0}`);
  tout.type = "button";
  tout.addEventListener("click", () => {
    S.domaine = "";
    chargerArticles();
  });
  rubriques.append(tout);
  for (const rubrique of data.rubriques || []) {
    if (!rubrique.nombre) continue;
    const bouton = el(
      "button",
      rubrique.id === S.domaine ? "actif" : "",
      `${rubrique.label} ${rubrique.nombre}`,
    );
    bouton.type = "button";
    bouton.addEventListener("click", () => {
      S.domaine = rubrique.id;
      chargerArticles();
    });
    rubriques.append(bouton);
  }
  $("#volume").textContent = data.total
    ? `${data.affiches} affichés sur ${data.total}`
    : "rien dans cette fenêtre";
  const liste = $("#articles");
  liste.replaceChildren();
  if (!(data.articles || []).length) {
    liste.append(
      el(
        "p",
        "vide",
        "Aucun article pour ces mots. Rafraîchis les flux, ou cherche le mot dans l'atelier : la recherche part tout de suite.",
      ),
    );
    return;
  }
  for (const article of data.articles) {
    const fiche = el("article", "fiche");
    const titre = el("h2");
    if (article.lien) {
      const lien = el("a", "", article.titre);
      lien.href = article.lien;
      lien.target = "_blank";
      lien.rel = "noreferrer";
      lien.addEventListener("click", (event) => event.stopPropagation());
      titre.append(lien);
    } else {
      titre.textContent = article.titre;
    }
    fiche.append(titre);
    const meta = [article.source, quand(article.date), article.domaine_label].filter(Boolean).join(" · ");
    fiche.append(el("p", "meta", meta));
    if ((article.mots || []).length || (article.tendances || []).length) {
      const badges = el("p", "badges");
      for (const mot of article.mots || []) badges.append(el("span", "badge", mot));
      for (const tendance of article.tendances || []) badges.append(el("span", "tendance", tendance));
      fiche.append(badges);
    }
    if (article.resume) fiche.append(el("p", "resume", article.resume));
    fiche.addEventListener("click", () => fiche.classList.toggle("ouvert"));
    liste.append(fiche);
  }
}

async function chargerMots() {
  S.mots = await api("/api/mots?profil=" + encodeURIComponent(S.profil));
  if (S.onglet === "mots") rendreMots();
}

function rendreMots() {
  const panneau = $("#panneau");
  panneau.replaceChildren();
  const data = S.mots || { domaines: [] };
  const essai = el("div", "essai");
  essai.append(el("p", "legende", "Essayer un mot"));
  const ligne = el("div", "ligne");
  const champ = el("input");
  champ.placeholder = "black-out, QGIS, MeshCore…";
  const select = el("select");
  for (const domaine of data.domaines || []) {
    const option = el("option", "", domaine.label);
    option.value = domaine.id;
    select.append(option);
  }
  const chercher = el("button", "", "Chercher");
  chercher.type = "button";
  ligne.append(champ, select, chercher);
    const bilan = el(
      "p",
      "",
      S.bilan || "Le chiffre compte ce qui est déjà en base. Chercher interroge Google News tout de suite.",
    );
  const exemples = el("ul", "exemples");
  for (const hote of S.hotes || []) {
    const item = el("li");
    item.textContent = `${hote.nom} · ${hote.mentions} mention(s) `;
    const sonder = el("button", "secondaire", "Trouver le flux");
    sonder.type = "button";
    sonder.addEventListener("click", () => trouverFlux(hote.hote, item));
    item.append(sonder);
    exemples.append(item);
  }
  essai.append(ligne, bilan, exemples);
  panneau.append(essai);

  champ.addEventListener("input", () => {
    clearTimeout(S.timerEssai);
    S.timerEssai = setTimeout(async () => {
      const mot = champ.value.trim();
      if (mot.length < 2) {
        bilan.textContent = "Tape un mot pour voir ce qu'il attrape.";
        exemples.replaceChildren();
        return;
      }
      const resultat = await api("/api/essayer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profil: S.profil, mot, jours: S.jours }),
      });
      bilan.textContent = `${resultat.nombre || 0} article(s) déjà en base pour « ${mot} ».`;
      exemples.replaceChildren();
      for (const exemple of resultat.exemples || []) {
        exemples.append(el("li", "", exemple.titre));
      }
    }, 220);
  });

  chercher.addEventListener("click", async () => {
    const mot = champ.value.trim();
    if (mot.length < 2) return;
    chercher.disabled = true;
    bilan.textContent = `Recherche de « ${mot} »…`;
    const resultat = await api("/api/chercher", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profil: S.profil, mot, domaine: select.value }),
    });
    chercher.disabled = false;
    if (resultat.erreur && !resultat.ajoutees) {
      S.bilan = resultat.erreur;
      bilan.textContent = S.bilan;
      return;
    }
    await api("/api/mots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profil: S.profil, domaine: select.value, mot }),
    });
    S.bilan = `${resultat.ajoutees || 0} article(s) ramenés pour « ${mot} », rangés dans la rubrique choisie.`;
    S.hotes = resultat.hotes || [];
    await chargerMots();
    await chargerArticles();
    chargerEtat();
  });

  for (const domaine of data.domaines || []) {
    const bloc = el("section", "rubrique-mots");
    bloc.append(el("h3", "", domaine.label));
    const nuage = el("div");
    for (const mot of domaine.mots || []) {
      const puce = el("span", "puce");
      puce.append(document.createTextNode(mot));
      const retirer = el("button", "", "×");
      retirer.type = "button";
      retirer.title = "Retirer";
      retirer.addEventListener("click", async () => {
        await api("/api/mots/retirer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profil: S.profil, domaine: domaine.id, mot }),
        });
        chargerMots();
        chargerArticles();
      });
      puce.append(retirer);
      nuage.append(puce);
    }
    const ajout = el("form", "ajout");
    const input = el("input");
    input.placeholder = "Ajouter un mot";
    input.required = true;
    const ok = el("button", "secondaire", "Ajouter");
    ok.type = "submit";
    ajout.append(input, ok);
    ajout.addEventListener("submit", async (event) => {
      event.preventDefault();
      await api("/api/mots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profil: S.profil, domaine: domaine.id, mot: input.value.trim() }),
      });
      chargerMots();
      chargerArticles();
    });
    bloc.append(nuage, ajout);
    panneau.append(bloc);
  }

  if ((data.tendances || []).length) {
    panneau.append(el("p", "legende", "Tendances"));
    for (const tendance of data.tendances) {
      panneau.append(el("p", "meta", `${tendance.label} — ${(tendance.mots || []).join(", ")}`));
    }
  }
}

async function trouverFlux(site, conteneur) {
  conteneur.append(el("span", "meta", " sondage…"));
  const resultat = await api("/api/sonder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ site, profil: S.profil }),
  });
  if (resultat.erreur) {
    conteneur.append(el("span", "erreur", " " + resultat.erreur));
    return;
  }
  conteneur.append(el("span", "ok", " " + (resultat.nom || resultat.url)));
  if (S.onglet === "radar") rendreRadar();
}

async function rendreRadar() {
  const panneau = $("#panneau");
  panneau.replaceChildren();
  const intro = el(
    "p",
    "meta",
    "Le radar interroge Google News et le web avec les mots de cette veille, puis ne garde que les flux dont les titres collent au sujet.",
  );
  const lancer = el("button", "", "Lancer le radar");
  lancer.type = "button";
  lancer.addEventListener("click", async () => {
    lancer.disabled = true;
    await api("/api/radar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profil: S.profil }),
    });
    chargerEtat();
  });
  panneau.append(intro, lancer);
  const data = await api("/api/candidats?profil=" + encodeURIComponent(S.profil));
  if (!(data.candidats || []).length) {
    panneau.append(el("p", "vide", "Aucune proposition pour cette veille."));
    return;
  }
  for (const candidat of data.candidats) {
    const carte = el("article", "candidat");
    carte.append(el("strong", "", candidat.nom || candidat.site));
    carte.append(el("p", "meta", candidat.raison || ""));
    const liste = el("ul");
    for (const titre of candidat.echantillon || []) liste.append(el("li", "", titre));
    const boutons = el("div", "ligne-boutons");
    const garder = el("button", "", "Ajouter le flux");
    garder.type = "button";
    garder.addEventListener("click", async () => {
      garder.disabled = true;
      await api("/api/adopter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: candidat.url }),
      });
      rendreRadar();
      chargerArticles();
      chargerEtat();
    });
    const rejeter = el("button", "secondaire", "Écarter");
    rejeter.type = "button";
    rejeter.addEventListener("click", async () => {
      await api("/api/rejeter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: candidat.url }),
      });
      rendreRadar();
    });
    boutons.append(garder, rejeter);
    carte.append(liste, boutons);
    panneau.append(carte);
  }
}

async function rendreSources() {
  const panneau = $("#panneau");
  panneau.replaceChildren();
  const filtre = el("input", "sources-filtre");
  filtre.placeholder = "Filtrer les sources";
  const liste = el("div");
  panneau.append(filtre, liste);
  const data = await api("/api/sources");
  const toutes = data.sources || [];

  function dessiner() {
    const q = filtre.value.trim().toLowerCase();
    liste.replaceChildren();
    const vues = toutes.filter((source) => !q || `${source.nom} ${source.url} ${source.erreur}`.toLowerCase().includes(q)).slice(0, 80);
    liste.append(el("p", "meta", `${vues.length} affichées / ${toutes.length}`));
    for (const source of vues) {
      const ligne = el("div", "source-ligne");
      ligne.append(el("strong", "", source.nom));
      const etat = source.erreur ? el("span", "erreur", "erreur") : source.dernier_ok ? el("span", "ok", `${source.nb_entrees}`) : el("span", "meta", source.kind);
      ligne.append(etat);
      ligne.append(el("small", "", source.erreur || source.url));
      liste.append(ligne);
    }
  }
  filtre.addEventListener("input", dessiner);
  dessiner();
}

function rendrePanneau() {
  if (S.onglet === "mots") rendreMots();
  else if (S.onglet === "radar") rendreRadar();
  else rendreSources();
}

document.querySelectorAll("[data-format]").forEach((bouton) => {
  bouton.addEventListener("click", async () => {
    const message = $("#export-msg");
    message.replaceChildren(document.createTextNode("Envoi en cours…"));
    bouton.disabled = true;
    const resultat = await api("/api/publier", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profil: S.profil, jours: S.jours, format: bouton.dataset.format }),
    });
    bouton.disabled = false;
    message.replaceChildren();
    if (resultat.erreur) {
      message.textContent = resultat.erreur;
      return;
    }
    const lien = document.createElement("a");
    lien.href = resultat.url;
    lien.target = "_blank";
    lien.rel = "noreferrer";
    lien.textContent = resultat.nom;
    message.append(lien, document.createTextNode(" · "));
    const index = document.createElement("a");
    index.href = resultat.index;
    index.target = "_blank";
    index.rel = "noreferrer";
    index.textContent = "la page Veille 2";
    message.append(index);
  });
});

$("#exporter-tout").addEventListener("click", async () => {
  const message = $("#export-msg");
  message.textContent = "Export de toutes les veilles en PDF, HTML et Markdown…";
  let resultat;
  try {
    resultat = await api("/api/publier-tout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
  } catch (err) {
    message.textContent = "Le serveur n'a pas répondu.";
    return;
  }
  if (resultat.erreur) {
    message.textContent = resultat.erreur;
    return;
  }
  S.suiviExport = true;
  chargerEtat();
});

$("#rafraichir").addEventListener("click", async () => {
  $("#rafraichir").disabled = true;
  await api("/api/collecte", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  chargerEtat();
});

$("#filtre-texte").addEventListener("input", (event) => {
  S.q = event.target.value.trim();
  clearTimeout(S.timerFiltre);
  S.timerFiltre = setTimeout(chargerArticles, 220);
});

const V3 = {
  ouvert: false,
  yaw: 0.5,
  pitch: 0.28,
  zoom: 1,
  auto: true,
  drag: false,
  x: 0,
  y: 0,
  scene: null,
  frame: 0,
};

const TEINTES = ["#dff25a", "#ff8a4c", "#9dffc3", "#f3f0e2", "#8eb4ff", "#f2c14e", "#e07a9a", "#c9b6ff"];

function placeSphere(index, total, rayon) {
  if (total <= 1) return [rayon, 0, 0];
  const hauteur = 1 - (index / (total - 1)) * 2;
  const anneau = Math.sqrt(Math.max(0, 1 - hauteur * hauteur));
  const angle = Math.PI * (3 - Math.sqrt(5)) * index;
  return [Math.cos(angle) * anneau * rayon, hauteur * rayon * 0.72, Math.sin(angle) * anneau * rayon];
}

function sceneDepuis(data) {
  const noeuds = [];
  const liens = [];
  const rubriques = (data.rubriques || []).filter((rubrique) => rubrique.nombre || (rubrique.mots || []).length);
  rubriques.forEach((rubrique, index) => {
    const [x, y, z] = placeSphere(index, rubriques.length, 260);
    const id = `r${index}`;
    noeuds.push({
      id,
      kind: "rubrique",
      label: rubrique.label,
      nombre: rubrique.nombre || 0,
      x,
      y,
      z,
      teinte: TEINTES[index % TEINTES.length],
    });
    liens.push(["centre", id]);
    const mots = rubrique.mots || [];
    mots.forEach((mot, ordre) => {
      const local = placeSphere(ordre, mots.length, 78 + Math.min(36, mots.length * 3));
      const mid = `m${index}-${ordre}`;
      noeuds.push({
        id: mid,
        kind: "mot",
        label: mot.mot,
        nombre: mot.nombre || 0,
        articles: mot.articles || [],
        x: x + local[0],
        y: y + local[1],
        z: z + local[2],
        teinte: TEINTES[index % TEINTES.length],
      });
      liens.push([id, mid]);
    });
  });
  return { titre: data.titre || "Veille", total: data.total || 0, jours: data.periode_jours || S.jours, noeuds, liens };
}

function projeter(point, largeur, hauteur) {
  const cosY = Math.cos(V3.yaw);
  const sinY = Math.sin(V3.yaw);
  const x1 = point.x * cosY + point.z * sinY;
  const z1 = -point.x * sinY + point.z * cosY;
  const cosP = Math.cos(V3.pitch);
  const sinP = Math.sin(V3.pitch);
  const y1 = point.y * cosP - z1 * sinP;
  const z2 = point.y * sinP + z1 * cosP;
  const foyer = 780;
  const echelle = (foyer / (foyer + z2)) * V3.zoom;
  return { x: largeur / 2 + x1 * echelle, y: hauteur / 2 + y1 * echelle, z: z2, echelle };
}

function dessinerVue3d() {
  const canvas = $("#vue3d-canvas");
  const scene = V3.scene;
  if (!canvas || !scene || !V3.ouvert) return;
  const ctx = canvas.getContext("2d");
  const largeur = canvas.width;
  const hauteur = canvas.height;
  ctx.clearRect(0, 0, largeur, hauteur);
  const index = new Map(scene.noeuds.map((noeud) => [noeud.id, noeud]));
  const centre = { x: 0, y: 0, z: 0 };
  for (const [depart, arrivee] of scene.liens) {
    const a = depart === "centre" ? centre : index.get(depart);
    const b = index.get(arrivee);
    if (!a || !b) continue;
    const pa = projeter(a, largeur, hauteur);
    const pb = projeter(b, largeur, hauteur);
    ctx.strokeStyle = "rgba(243, 240, 226, 0.22)";
    ctx.lineWidth = depart === "centre" ? 1.4 : 1;
    ctx.beginPath();
    ctx.moveTo(pa.x, pa.y);
    ctx.lineTo(pb.x, pb.y);
    ctx.stroke();
  }
  const ordre = scene.noeuds
    .map((noeud) => ({ noeud, p: projeter(noeud, largeur, hauteur) }))
    .sort((a, b) => b.p.z - a.p.z);
  for (const { noeud, p } of ordre) {
    const rayon = (noeud.kind === "rubrique" ? 11 : 5 + Math.min(7, Math.sqrt(noeud.nombre || 0))) * p.echelle;
    noeud._rayon = Math.max(2, rayon);
    noeud._p = p;
    ctx.fillStyle = noeud.teinte;
    ctx.globalAlpha = noeud.nombre ? 0.95 : 0.45;
    ctx.beginPath();
    ctx.arc(p.x, p.y, noeud._rayon, 0, Math.PI * 2);
    ctx.fill();
    if (V3.selection === noeud.id) {
      ctx.globalAlpha = 1;
      ctx.strokeStyle = "#f3f0e2";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
  const places = [];
  for (const { noeud, p } of [...ordre].reverse()) {
    if (p.echelle < 0.55) continue;
    const texte = noeud.kind === "rubrique"
      ? (noeud.nombre ? `${noeud.label} · ${noeud.nombre}` : noeud.label)
      : `${noeud.label}${noeud.nombre ? ` · ${noeud.nombre}` : ""}`;
    const x = noeud.kind === "rubrique" ? p.x : p.x + noeud._rayon + 6;
    const y = noeud.kind === "rubrique" ? p.y - noeud._rayon - 12 : p.y;
    const tropPres = places.some((place) => Math.hypot(place.x - x, place.y - y) < (noeud.kind === "rubrique" ? 18 : 26));
    if (tropPres && noeud.kind !== "rubrique") continue;
    places.push({ x, y });
    ctx.font = `${noeud.kind === "rubrique" ? 600 : 500} ${Math.round((noeud.kind === "rubrique" ? 15 : 12) * Math.min(p.echelle, 1.25))}px "Segoe UI", sans-serif`;
    ctx.textAlign = noeud.kind === "rubrique" ? "center" : "left";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#101208";
    ctx.strokeText(texte, x, y);
    ctx.fillStyle = noeud.kind === "rubrique" ? "#f3f0e2" : noeud.teinte;
    ctx.fillText(texte, x, y);
  }
  const titre = scene.titre;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = '600 42px "Palatino Linotype", Palatino, Georgia, serif';
  ctx.lineWidth = 6;
  ctx.strokeStyle = "rgba(8, 10, 6, 0.9)";
  ctx.strokeText(titre, largeur / 2, hauteur / 2);
  ctx.fillStyle = "#dff25a";
  ctx.fillText(titre, largeur / 2, hauteur / 2);
  ctx.font = '13px "Segoe UI", sans-serif';
  ctx.fillStyle = "#a3aa8c";
  ctx.fillText(`${scene.total} articles · ${scene.jours} jours`, largeur / 2, hauteur / 2 + 34);
}

function animerVue3d() {
  if (!V3.ouvert) return;
  const canvas = $("#vue3d-canvas");
  if (canvas && canvas.height < 10) ajusterCanvas3d();
  if (V3.auto && !V3.drag) V3.yaw += 0.004;
  dessinerVue3d();
  V3.frame = requestAnimationFrame(animerVue3d);
}

function ajusterCanvas3d() {
  const canvas = $("#vue3d-canvas");
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(1, 0, 0, 1, 0, 0);
}

async function chargerVue3d() {
  $("#vue3d-titre").textContent = "Vue 3D";
  $("#vue3d-meta").textContent = "Lecture de la veille…";
  const data = await api(`/api/synthese?profil=${encodeURIComponent(S.profil)}&jours=${S.jours}`);
  if (data.erreur) {
    $("#vue3d-meta").textContent = data.erreur;
    return;
  }
  V3.scene = sceneDepuis(data);
  V3.selection = "";
  cacherArticlesMot();
  $("#vue3d-titre").textContent = V3.scene.titre;
  const groupes = V3.scene.noeuds.filter((noeud) => noeud.kind === "rubrique").length;
  const mots = V3.scene.noeuds.filter((noeud) => noeud.kind === "mot").length;
  $("#vue3d-meta").textContent = `${groupes} rubriques · ${mots} mots-clés · ${V3.scene.total} articles`;
  dessinerVue3d();
}

function ouvrirVue3d() {
  V3.ouvert = true;
  $("#vue3d").hidden = false;
  $("#vue3d-ouvrir").classList.add("actif");
  ajusterCanvas3d();
  chargerVue3d();
  cancelAnimationFrame(V3.frame);
  V3.frame = requestAnimationFrame(animerVue3d);
}

function fermerVue3d() {
  V3.ouvert = false;
  V3.drag = false;
  V3.selection = "";
  cacherArticlesMot();
  $("#vue3d").hidden = true;
  $("#vue3d-ouvrir").classList.remove("actif");
  cancelAnimationFrame(V3.frame);
}

function cacherArticlesMot() {
  const liste = $("#vue3d-liste");
  const etait = liste && !liste.hidden;
  if (liste) liste.hidden = true;
  $("#vue3d-cartes")?.replaceChildren();
  if (etait) requestAnimationFrame(ajusterCanvas3d);
}

function montrerArticlesMot(noeud) {
  V3.selection = noeud.id;
  V3.auto = false;
  $("#vue3d-rotation").classList.remove("actif");
  const liste = $("#vue3d-liste");
  const cartes = $("#vue3d-cartes");
  liste.hidden = false;
  requestAnimationFrame(ajusterCanvas3d);
  $("#vue3d-mot").textContent = noeud.label;
  cartes.replaceChildren();
  const articles = noeud.articles || [];
  if (!articles.length) {
    cartes.append(el("p", "vide", "Aucun article pour ce mot dans la fenêtre."));
    return;
  }
  for (const article of articles) {
    const carte = el("article", "vue3d-carte");
    const titre = article.lien ? el("a", "", article.titre) : el("strong", "", article.titre);
    if (article.lien) {
      titre.href = article.lien;
      titre.target = "_blank";
      titre.rel = "noreferrer";
    }
    carte.append(titre);
    carte.append(el("p", "meta", [article.source, quand(article.date)].filter(Boolean).join(" · ")));
    if (article.resume) carte.append(el("p", "resume", article.resume));
    cartes.append(carte);
  }
}

function motSousPointeur(event) {
  const canvas = $("#vue3d-canvas");
  const scene = V3.scene;
  if (!canvas || !scene) return null;
  const rect = canvas.getBoundingClientRect();
  const ratioX = canvas.width / Math.max(rect.width, 1);
  const ratioY = canvas.height / Math.max(rect.height, 1);
  const x = (event.clientX - rect.left) * ratioX;
  const y = (event.clientY - rect.top) * ratioY;
  let choisi = null;
  let meilleur = Infinity;
  for (const noeud of scene.noeuds) {
    if (noeud.kind !== "mot" || !noeud._p || !noeud.nombre) continue;
    const distance = Math.hypot(noeud._p.x - x, noeud._p.y - y);
    const seuil = noeud._rayon + 14 * ratioX;
    if (distance <= seuil && distance < meilleur) {
      meilleur = distance;
      choisi = noeud;
    }
  }
  return choisi;
}

$("#vue3d-liste-fermer").addEventListener("click", () => {
  V3.selection = "";
  cacherArticlesMot();
});
$("#vue3d-ouvrir").addEventListener("click", () => {
  if (V3.ouvert) fermerVue3d();
  else ouvrirVue3d();
});
$("#vue3d-fermer").addEventListener("click", fermerVue3d);
$("#vue3d-rotation").addEventListener("click", () => {
  V3.auto = !V3.auto;
  $("#vue3d-rotation").classList.toggle("actif", V3.auto);
});
$("#vue3d-rotation").classList.add("actif");
$("#vue3d-canvas").addEventListener("pointerdown", (event) => {
  V3.drag = true;
  V3.bouge = false;
  V3.x = event.clientX;
  V3.y = event.clientY;
  event.currentTarget.setPointerCapture(event.pointerId);
});
$("#vue3d-canvas").addEventListener("pointermove", (event) => {
  if (!V3.drag) {
    event.currentTarget.style.cursor = motSousPointeur(event) ? "pointer" : "grab";
    return;
  }
  const dx = event.clientX - V3.x;
  const dy = event.clientY - V3.y;
  if (Math.hypot(dx, dy) > 4) {
    V3.bouge = true;
    V3.auto = false;
    $("#vue3d-rotation").classList.remove("actif");
  }
  if (!V3.bouge) return;
  V3.yaw += dx * 0.008;
  V3.pitch = Math.max(-1.2, Math.min(1.2, V3.pitch + dy * 0.008));
  V3.x = event.clientX;
  V3.y = event.clientY;
});
$("#vue3d-canvas").addEventListener("pointerup", (event) => {
  const clic = V3.drag && !V3.bouge;
  V3.drag = false;
  if (!clic) return;
  const noeud = motSousPointeur(event);
  if (noeud) montrerArticlesMot(noeud);
  else {
    V3.selection = "";
    cacherArticlesMot();
  }
});
$("#vue3d-canvas").addEventListener("pointercancel", () => {
  V3.drag = false;
});
$("#vue3d-canvas").addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    V3.zoom = Math.max(0.45, Math.min(2.4, V3.zoom * (event.deltaY > 0 ? 0.92 : 1.08)));
  },
  { passive: false },
);
window.addEventListener("resize", () => {
  if (!V3.ouvert) return;
  ajusterCanvas3d();
});
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && V3.ouvert) fermerVue3d();
});

document.querySelectorAll(".onglets button[data-onglet]").forEach((bouton) => {
  bouton.addEventListener("click", () => {
    S.onglet = bouton.dataset.onglet;
    document.querySelectorAll(".onglets button[data-onglet]").forEach((autre) => autre.classList.toggle("actif", autre === bouton));
    rendrePanneau();
  });
});

$("#nouvelle").addEventListener("submit", async (event) => {
  event.preventDefault();
  const titre = new FormData(event.target).get("titre");
  const resultat = await api("/api/profils", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titre, perimetre: "Veille créée dans la console." }),
  });
  if (resultat.erreur) return;
  event.target.reset();
  S.profil = resultat.id;
  await chargerProfils();
  choisirProfil(resultat.id);
});

chargerProfils().then(() => {
  chargerArticles();
  chargerMots();
  chargerEtat();
});
