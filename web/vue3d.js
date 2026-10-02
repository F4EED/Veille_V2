const params = new URLSearchParams(location.search);
const profil = params.get("profil") || "iot";
const jours = params.get("jours") || "7";

const $ = (sel) => document.querySelector(sel);

async function api(path) {
  const reponse = await fetch(path);
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

const V3 = {
  ouvert: true,
  yaw: 0.5,
  pitch: 0.28,
  zoom: 1,
  auto: true,
  drag: false,
  bouge: false,
  x: 0,
  y: 0,
  scene: null,
  frame: 0,
  selection: "",
};

const TEINTES = ["#dff25a", "#ff8a4c", "#9dffc3", "#f3f0e2", "#8eb4ff", "#f2c14e", "#e07a9a", "#c9b6ff"];

function placeOrbite(index, total, rayon) {
  const angle = (index / Math.max(total, 1)) * Math.PI * 2 - Math.PI / 2;
  const bande = Math.sin(angle * 2) * 0.42;
  const y = Math.sin(bande) * rayon;
  const anneau = Math.cos(bande) * rayon;
  return [Math.cos(angle) * anneau, y, Math.sin(angle) * anneau];
}

function sceneDepuis(data) {
  const noeuds = [];
  const liens = [];
  const rubriques = (data.rubriques || []).filter((rubrique) => rubrique.nombre || (rubrique.mots || []).length);
  const pieces = [];
  rubriques.forEach((rubrique, index) => {
    const teinte = TEINTES[index % TEINTES.length];
    const groupe = `r${index}`;
    pieces.push({
      id: groupe,
      kind: "rubrique",
      label: rubrique.label,
      nombre: rubrique.nombre || 0,
      teinte,
      parent: "centre",
    });
    (rubrique.mots || []).forEach((mot, ordre) => {
      pieces.push({
        id: `m${index}-${ordre}`,
        kind: "mot",
        label: mot.mot,
        nombre: mot.nombre || 0,
        articles: mot.articles || [],
        teinte,
        parent: "centre",
      });
    });
  });
  const rayon = 260 + Math.min(40, pieces.length * 2);
  pieces.forEach((piece, index) => {
    const [x, y, z] = placeOrbite(index, pieces.length, rayon);
    noeuds.push({ ...piece, x, y, z });
    liens.push([piece.parent, piece.id]);
  });
  return { titre: data.titre || "Veille", total: data.total || 0, jours: data.periode_jours || Number(jours), noeuds, liens };
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
  if (!canvas || !scene) return;
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
    ctx.strokeStyle = depart === "centre" ? "rgba(223, 242, 90, 0.28)" : "rgba(243, 240, 226, 0.22)";
    ctx.lineWidth = depart === "centre" ? 1.3 : 1;
    ctx.beginPath();
    ctx.moveTo(pa.x, pa.y);
    ctx.lineTo(pb.x, pb.y);
    ctx.stroke();
  }
  const ordre = scene.noeuds
    .map((noeud) => ({ noeud, p: projeter(noeud, largeur, hauteur) }))
    .sort((a, b) => b.p.z - a.p.z);
  for (const { noeud, p } of ordre) {
    const rayon = (noeud.kind === "rubrique" ? 8 : 5 + Math.min(7, Math.sqrt(noeud.nombre || 0))) * p.echelle;
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
  const milieu = projeter({ x: 0, y: 0, z: 0 }, largeur, hauteur);
  ctx.strokeStyle = "rgba(223, 242, 90, 0.55)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(milieu.x, milieu.y, 58 * V3.zoom, 0, Math.PI * 2);
  ctx.stroke();
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
  const data = await api(`/api/synthese?profil=${encodeURIComponent(profil)}&jours=${encodeURIComponent(jours)}`);
  if (data.erreur) {
    $("#vue3d-meta").textContent = data.erreur;
    return;
  }
  V3.scene = sceneDepuis(data);
  V3.selection = "";
  cacherArticlesMot();
  $("#vue3d-titre").textContent = V3.scene.titre;
  document.title = `${V3.scene.titre} — Vue 3D`;
  const groupes = V3.scene.noeuds.filter((noeud) => noeud.kind === "rubrique").length;
  const mots = V3.scene.noeuds.filter((noeud) => noeud.kind === "mot").length;
  $("#vue3d-meta").textContent = `${groupes} rubriques · ${mots} mots-clés · ${V3.scene.total} articles`;
  dessinerVue3d();
}

function fermerVue3d() {
  window.close();
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
$("#vue3d-fermer").addEventListener("click", fermerVue3d);
$("#vue3d-rotation").addEventListener("click", () => {
  V3.auto = !V3.auto;
  $("#vue3d-rotation").classList.toggle("actif", V3.auto);
});
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
window.addEventListener("resize", ajusterCanvas3d);
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") fermerVue3d();
});

ajusterCanvas3d();
chargerVue3d();
V3.frame = requestAnimationFrame(animerVue3d);
