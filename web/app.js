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
  const morceaux = [];
  if (data.version) morceaux.push(data.version);
  morceaux.push(`${data.articles || 0} articles`, `${data.sources || 0} sources`);
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

async function rendreCourriels() {
  const panneau = $("#panneau");
  panneau.replaceChildren();
  panneau.append(el("p", "meta", "Chaque adresse reçoit les veilles cochées. L'envoi part de la boîte déjà utilisée par la veille d'origine. Les liens PDF, HTML et Markdown sont ceux des Pages Perso."));
  const ajout = el("form", "ajout");
  const champ = el("input");
  champ.type = "email";
  champ.required = true;
  champ.placeholder = "adresse@exemple.fr";
  champ.autocomplete = "off";
  const bouton = el("button", "", "Ajouter");
  bouton.type = "submit";
  ajout.append(champ, bouton);
  const etat = el("p", "meta", "");
  const liste = el("div");
  panneau.append(ajout, etat, liste);
  const data = await api("/api/courriels");
  if (data.erreur) {
    etat.textContent = data.erreur;
    return;
  }
  etat.textContent = data.pret
    ? `Envoi depuis ${data.expediteur || "la boîte configurée"}.`
    : "La boîte d'envoi n'est pas prête : le mot de passe SMTP manque dans la veille d'origine.";
  ajout.addEventListener("submit", async (event) => {
    event.preventDefault();
    const resultat = await api("/api/courriels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: champ.value, profils: [] }),
    });
    if (resultat.erreur) {
      etat.textContent = resultat.erreur;
      return;
    }
    champ.value = "";
    rendreCourriels();
  });
  const tout = el("button", "tout", "Envoyer à toutes les adresses");
  tout.type = "button";
  tout.addEventListener("click", () => envoyerCourriel(""));
  for (const ligne of data.courriels || []) {
    const carte = el("article", "courriel");
    carte.append(el("strong", "", ligne.email));
    const choix = el("div", "courriel-choix");
    const coches = new Set(ligne.profils || []);
    for (const profil of S.profils) {
      const label = el("label");
      const casee = el("input");
      casee.type = "checkbox";
      casee.checked = coches.has(profil.id);
      casee.addEventListener("change", async () => {
        const profils = [...choix.querySelectorAll("input:checked")].map((item) => item.dataset.profil);
        const resultat = await api("/api/courriels", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: ligne.email, profils }),
        });
        if (resultat.erreur) etat.textContent = resultat.erreur;
      });
      casee.dataset.profil = profil.id;
      label.append(casee, document.createTextNode(profil.titre));
      choix.append(label);
    }
    const actions = el("div", "ligne-boutons");
    const envoyer = el("button", "", "Envoyer");
    envoyer.type = "button";
    envoyer.addEventListener("click", () => envoyerCourriel(ligne.email));
    const retirer = el("button", "secondaire", "Retirer");
    retirer.type = "button";
    retirer.addEventListener("click", async () => {
      await api("/api/courriels/retirer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: ligne.email }),
      });
      rendreCourriels();
    });
    actions.append(envoyer, retirer);
    carte.append(choix, actions);
    liste.append(carte);
  }
  if ((data.courriels || []).length) liste.append(tout);
}

async function envoyerCourriel(email) {
  const resultat = await api("/api/courriels/envoyer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (resultat.erreur) {
    const etat = $("#panneau .meta");
    if (etat) etat.textContent = resultat.erreur;
    return;
  }
  chargerEtat();
}

function rendrePanneau() {
  if (S.onglet === "mots") rendreMots();
  else if (S.onglet === "radar") rendreRadar();
  else if (S.onglet === "courriel") rendreCourriels();
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

$("#vue3d-ouvrir").addEventListener("click", () => {
  const url = `/vue3d?profil=${encodeURIComponent(S.profil)}&jours=${S.jours}`;
  window.open(url, "_blank", "noopener");
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
